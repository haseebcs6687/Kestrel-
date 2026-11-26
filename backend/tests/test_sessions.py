"""Integration tests for refresh token sessions, rotation, reuse detection, and logout."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    get_settings,
)
from app.core.db import get_db, reset_db_connections
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken, Role, User
from app.modules.auth.security import hash_password, hash_refresh_token
from app.modules.workspaces.models import Workspace


@pytest.fixture
def auth_client(db_session: Session) -> Generator[TestClient]:
    """TestClient wired directly to the transactional db_session fixture."""
    get_settings.cache_clear()
    reset_db_connections()
    app = create_app()

    def override_get_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    reset_db_connections()


def _create_user(
    db: Session,
    email: str = "session_user@example.com",
    role: str = Role.ADMIN.value,
    is_active: bool = True,
) -> tuple[Workspace, User]:
    """Helper to persist a test workspace and user."""
    workspace = Workspace(name="Session Org", slug=f"session-org-{uuid.uuid4().hex[:6]}")
    db.add(workspace)
    db.flush()

    user = User(
        workspace_id=workspace.id,
        email=email,
        password_hash=hash_password("SuperSecretPassword123!"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return workspace, user


def test_login_sets_refresh_cookie(auth_client: TestClient, db_session: Session) -> None:
    """Verify login issues bearer token and sets HttpOnly refresh cookie with strict attributes."""
    _create_user(db_session, "login_cookie@example.com")

    payload = {"email": "login_cookie@example.com", "password": "SuperSecretPassword123!"}
    resp = auth_client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    set_cookie_header = resp.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert f"{REFRESH_COOKIE_NAME}=" in set_cookie_header
    assert f"Path={REFRESH_COOKIE_PATH}" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "SameSite=strict" in set_cookie_header or "samesite=strict" in set_cookie_header.lower()
    assert "Max-Age=" in set_cookie_header


def test_refresh_success(auth_client: TestClient, db_session: Session) -> None:
    """Verify refresh rotation issues new token pair and revokes previous refresh token."""
    _create_user(db_session, "refresh_user@example.com")

    # 1. Login sets cookie in client jar automatically
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_user@example.com", "password": "SuperSecretPassword123!"},
    )
    assert login_resp.status_code == 200
    raw_cookie_1 = login_resp.cookies.get(REFRESH_COOKIE_NAME)
    assert raw_cookie_1 is not None

    # 2. Refresh with valid CSRF header and cookie in jar
    refresh_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

    raw_cookie_2 = refresh_resp.cookies.get(REFRESH_COOKIE_NAME)
    assert raw_cookie_2 is not None
    assert raw_cookie_2 != raw_cookie_1

    # 3. Check DB state for token rotation
    hash_1 = hash_refresh_token(raw_cookie_1)
    hash_2 = hash_refresh_token(raw_cookie_2)

    t1 = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_1))
    t2 = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_2))

    assert t1 is not None and t2 is not None
    assert t1.is_revoked is True
    assert t1.replaced_by_id == t2.id
    assert t2.is_active is True
    assert t1.family_id == t2.family_id


def test_refresh_without_csrf_header_rejected(auth_client: TestClient, db_session: Session) -> None:
    """Verify refresh requests lacking valid CSRF client header are rejected with 403."""
    _create_user(db_session, "csrf_user@example.com")

    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "csrf_user@example.com", "password": "SuperSecretPassword123!"},
    )

    # Missing header
    resp_missing = auth_client.post("/api/v1/auth/refresh")
    assert resp_missing.status_code == 403

    # Invalid header
    resp_invalid = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: "malicious_client"},
    )
    assert resp_invalid.status_code == 403


def test_refresh_without_cookie_rejected(auth_client: TestClient) -> None:
    """Verify refresh requests missing the refresh cookie return 401."""
    auth_client.cookies.clear()
    resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert resp.status_code == 401
    assert "Missing refresh token cookie" in resp.json()["detail"]


def test_refresh_reuse_detection(auth_client: TestClient, db_session: Session) -> None:
    """Verify token reuse invalidates the entire token family and logs security audit event."""
    _, user = _create_user(db_session, "reuse_user@example.com")

    # 1. Login -> Token A
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "reuse_user@example.com", "password": "SuperSecretPassword123!"},
    )
    token_a = login_resp.cookies.get(REFRESH_COOKIE_NAME)
    assert token_a is not None

    # 2. Legitimate Refresh -> Token B (Token A is now revoked)
    refresh_1 = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert refresh_1.status_code == 200
    token_b = refresh_1.cookies.get(REFRESH_COOKIE_NAME)
    assert token_b is not None

    # 3. Attacker presents Token A again -> Reuse detected!
    auth_client.cookies.set(REFRESH_COOKIE_NAME, token_a, path=REFRESH_COOKIE_PATH)
    reuse_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert reuse_resp.status_code == 401
    assert "Invalid or expired refresh token" in reuse_resp.json()["detail"]

    # 4. Check DB: Entire family must be revoked
    hash_a = hash_refresh_token(token_a)
    hash_b = hash_refresh_token(token_b)

    rec_a = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_a))
    rec_b = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_b))

    assert rec_a is not None and rec_b is not None
    assert rec_a.is_revoked is True
    assert rec_b.is_revoked is True

    # 5. Check Audit log row
    audit_row = db_session.scalar(
        select(AuditLog).where(
            AuditLog.actor_id == user.id,
            AuditLog.action == "auth.refresh_reuse_detected",
        )
    )
    assert audit_row is not None
    assert audit_row.details is not None
    assert audit_row.details.get("family_id") == str(rec_a.family_id)

    # 6. Token B presented subsequently must also fail
    auth_client.cookies.set(REFRESH_COOKIE_NAME, token_b, path=REFRESH_COOKIE_PATH)
    subsequent_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert subsequent_resp.status_code == 401


def test_refresh_expired_token(auth_client: TestClient, db_session: Session) -> None:
    """Verify expired refresh tokens are rejected and marked revoked."""
    workspace, user = _create_user(db_session, "expired_token_user@example.com")

    raw_token = "expired_raw_token_value_abc123"
    token_hash = hash_refresh_token(raw_token)
    past = datetime.now(UTC) - timedelta(hours=2)

    expired_record = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=token_hash,
        family_id=uuid.uuid4(),
        issued_at=past - timedelta(days=7),
        expires_at=past,
    )
    db_session.add(expired_record)
    db_session.flush()

    auth_client.cookies.set(REFRESH_COOKIE_NAME, raw_token, path=REFRESH_COOKIE_PATH)
    resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert resp.status_code == 401
    assert "Invalid or expired refresh token" in resp.json()["detail"]

    # Re-fetch from DB and confirm revoked
    db_session.refresh(expired_record)
    assert expired_record.is_revoked is True


def test_refresh_inactive_user(auth_client: TestClient, db_session: Session) -> None:
    """Verify refreshing tokens for deactivated accounts is rejected."""
    _, user = _create_user(db_session, "inactive_refresh_user@example.com")

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive_refresh_user@example.com", "password": "SuperSecretPassword123!"},
    )
    assert login_resp.status_code == 200

    # Deactivate user in database
    user.is_active = False
    db_session.flush()

    refresh_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert refresh_resp.status_code == 401
    assert "Invalid or expired refresh token" in refresh_resp.json()["detail"]


def test_logout_clears_cookie_and_revokes(auth_client: TestClient, db_session: Session) -> None:
    """Verify logout revokes the token family, records audit log, and clears client cookie."""
    _, user = _create_user(db_session, "logout_user@example.com")

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "logout_user@example.com", "password": "SuperSecretPassword123!"},
    )
    token = login_resp.cookies.get(REFRESH_COOKIE_NAME)
    assert token is not None

    logout_resp = auth_client.post(
        "/api/v1/auth/logout",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert logout_resp.status_code == 204

    # Verify cookie clearance in response
    set_cookie_header = logout_resp.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert f"{REFRESH_COOKIE_NAME}=" in set_cookie_header
    assert "max-age=0" in set_cookie_header.lower()

    # Verify DB token is revoked
    token_hash = hash_refresh_token(token)
    token_record = db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    assert token_record is not None
    assert token_record.is_revoked is True

    # Verify Audit log
    audit_row = db_session.scalar(
        select(AuditLog).where(
            AuditLog.actor_id == user.id,
            AuditLog.action == "auth.logout",
        )
    )
    assert audit_row is not None


def test_logout_without_csrf_rejected(auth_client: TestClient) -> None:
    """Verify logout without CSRF header is rejected with 403 Forbidden."""
    resp = auth_client.post("/api/v1/auth/logout")
    assert resp.status_code == 403


def test_logout_idempotent(auth_client: TestClient) -> None:
    """Verify logout without cookie or with unknown cookie returns 204 safely."""
    # Without cookie
    auth_client.cookies.clear()
    resp1 = auth_client.post(
        "/api/v1/auth/logout",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert resp1.status_code == 204

    # With unknown cookie
    auth_client.cookies.set(
        REFRESH_COOKIE_NAME, "unknown_cookie_value_xyz", path=REFRESH_COOKIE_PATH
    )
    resp2 = auth_client.post(
        "/api/v1/auth/logout",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert resp2.status_code == 204
