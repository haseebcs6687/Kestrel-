"""Integration tests for refresh token sessions, rotation, reuse detection, and logout."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
            AuditLog.actor_user_id == user.id,
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
            AuditLog.actor_user_id == user.id,
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


def test_refresh_tokens_unique_token_hash(db_session: Session) -> None:
    """Verify refresh_tokens enforces uniqueness on token_hash."""
    workspace, user = _create_user(db_session, "unique_hash@example.com")
    shared_hash = hash_refresh_token("dummy_token_for_hash_unique")
    now = datetime.now(UTC)

    t1 = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=shared_hash,
        family_id=uuid.uuid4(),
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(t1)
    db_session.flush()

    t2 = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=shared_hash,
        family_id=uuid.uuid4(),
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(t2)
            db_session.flush()


def test_refresh_tokens_expires_after_issued_constraint(db_session: Session) -> None:
    """Verify refresh_tokens enforces expires_at > issued_at via check constraint."""
    workspace, user = _create_user(db_session, "check_expires@example.com")
    now = datetime.now(UTC)

    bad_token = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=hash_refresh_token("bad_expires_token"),
        family_id=uuid.uuid4(),
        issued_at=now,
        expires_at=now - timedelta(seconds=1),
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(bad_token)
            db_session.flush()


def test_refresh_tokens_cascade_on_user_delete(db_session: Session) -> None:
    """Verify deleting a user cascades and deletes all associated refresh tokens."""
    workspace, user = _create_user(db_session, "cascade_user@example.com")
    now = datetime.now(UTC)
    t = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=hash_refresh_token("cascade_token"),
        family_id=uuid.uuid4(),
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(t)
    db_session.flush()
    token_id = t.id

    db_session.delete(user)
    db_session.flush()

    persisted = db_session.scalar(select(RefreshToken).where(RefreshToken.id == token_id))
    assert persisted is None


def test_refresh_tokens_replaced_by_fk_set_null(db_session: Session) -> None:
    """Verify deleting a replaced token sets replaced_by_id to NULL on predecessor."""
    workspace, user = _create_user(db_session, "replaced_fk@example.com")
    now = datetime.now(UTC)
    fam_id = uuid.uuid4()

    t2 = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=hash_refresh_token("token_successor"),
        family_id=fam_id,
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(t2)
    db_session.flush()

    t1 = RefreshToken(
        workspace_id=workspace.id,
        user_id=user.id,
        token_hash=hash_refresh_token("token_predecessor"),
        family_id=fam_id,
        issued_at=now,
        expires_at=now + timedelta(days=7),
        replaced_by_id=t2.id,
    )
    db_session.add(t1)
    db_session.flush()

    db_session.delete(t2)
    db_session.flush()

    db_session.refresh(t1)
    assert t1.replaced_by_id is None


def test_login_cookie_attributes_and_secure_flag(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify login cookie attributes including HttpOnly, SameSite, Path, and Secure."""
    _create_user(db_session, "cookie_attr@example.com")
    settings = get_settings()

    # Case 1: Default cookie_secure=False
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "cookie_attr@example.com", "password": "SuperSecretPassword123!"},
    )
    assert resp.status_code == 200
    cookie_header = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "SameSite=strict" in cookie_header or "samesite=strict" in cookie_header.lower()
    assert f"Path={REFRESH_COOKIE_PATH}" in cookie_header
    assert "Max-Age=" in cookie_header

    # Case 2: Forcing cookie_secure=True
    settings.cookie_secure = True
    try:
        resp_sec = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "cookie_attr@example.com", "password": "SuperSecretPassword123!"},
        )
        assert resp_sec.status_code == 200
        cookie_header_sec = resp_sec.headers.get("set-cookie", "")
        assert "secure" in cookie_header_sec.lower()
    finally:
        settings.cookie_secure = False


def test_raw_refresh_token_never_in_database(auth_client: TestClient, db_session: Session) -> None:
    """Verify raw refresh token strings never appear in any database column."""
    _create_user(db_session, "raw_leak_check@example.com")
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "raw_leak_check@example.com", "password": "SuperSecretPassword123!"},
    )
    raw_token = resp.cookies.get(REFRESH_COOKIE_NAME)
    assert raw_token is not None

    tokens = db_session.scalars(select(RefreshToken)).all()
    for tok in tokens:
        assert raw_token != tok.token_hash
        assert raw_token not in str(tok.__dict__)


def test_refresh_garbage_cookie_returns_401(auth_client: TestClient) -> None:
    """Verify refresh with a completely garbage cookie value returns 401."""
    auth_client.cookies.set(REFRESH_COOKIE_NAME, "totally_invalid_garbage_token_value")
    resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert resp.status_code == 401
    assert "Invalid or expired refresh token" in resp.json()["detail"]


def test_refresh_inactive_user_revokes_entire_family(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify refreshing tokens for a deactivated user rejects and revokes the entire family."""
    _, user = _create_user(db_session, "inactive_family@example.com")
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive_family@example.com", "password": "SuperSecretPassword123!"},
    )
    raw_token = login_resp.cookies.get(REFRESH_COOKIE_NAME)
    tok_hash = hash_refresh_token(raw_token)
    tok_row = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == tok_hash))
    assert tok_row is not None
    family_id = tok_row.family_id

    # Deactivate user
    user.is_active = False
    db_session.flush()

    resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert resp.status_code == 401

    # Confirm all tokens in this family are revoked
    fam_tokens = db_session.scalars(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    assert len(fam_tokens) >= 1
    assert all(t.is_revoked for t in fam_tokens)


def test_multi_session_logout_isolation(auth_client: TestClient, db_session: Session) -> None:
    """Verify logging out one session leaves another session of the same user functioning."""
    _, user = _create_user(db_session, "multi_session@example.com")

    # Session 1 login
    resp1 = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "multi_session@example.com", "password": "SuperSecretPassword123!"},
    )
    token1 = resp1.cookies.get(REFRESH_COOKIE_NAME)

    # Session 2 login
    resp2 = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "multi_session@example.com", "password": "SuperSecretPassword123!"},
    )
    token2 = resp2.cookies.get(REFRESH_COOKIE_NAME)
    assert token1 != token2

    # Logout Session 1
    auth_client.cookies.set(REFRESH_COOKIE_NAME, token1, path=REFRESH_COOKIE_PATH)
    logout_resp = auth_client.post(
        "/api/v1/auth/logout",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert logout_resp.status_code == 204

    # Session 1 is revoked
    hash1 = hash_refresh_token(token1)
    tok1 = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash1))
    assert tok1.is_revoked is True

    # Session 2 is still valid and can rotate successfully
    auth_client.cookies.set(REFRESH_COOKIE_NAME, token2, path=REFRESH_COOKIE_PATH)
    refresh_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()


def test_session_log_safety_never_leaks_token_or_hash(
    auth_client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify raw refresh tokens and token hashes are never emitted in structured logs."""
    _create_user(db_session, "log_safety_session@example.com")
    import logging

    caplog.set_level(logging.DEBUG)

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "log_safety_session@example.com", "password": "SuperSecretPassword123!"},
    )
    raw_token = login_resp.cookies.get(REFRESH_COOKIE_NAME)
    tok_hash = hash_refresh_token(raw_token)

    auth_client.post(
        "/api/v1/auth/refresh",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )

    auth_client.post(
        "/api/v1/auth/logout",
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )

    all_logs = caplog.text
    assert raw_token not in all_logs
    assert tok_hash not in all_logs


def test_revoke_all_user_tokens(db_session: Session) -> None:
    """Verify revoke_all_user_tokens revokes only target user's tokens and leaves others intact."""
    from app.modules.auth.sessions import issue_refresh_token, revoke_all_user_tokens

    ws1, u1 = _create_user(db_session, "user1_revoke@example.com")
    ws2, u2 = _create_user(db_session, "user2_revoke@example.com")

    # Issue 2 tokens for u1 and 2 tokens for u2
    issue_refresh_token(db_session, user=u1, workspace_id=ws1.id)
    issue_refresh_token(db_session, user=u1, workspace_id=ws1.id)
    issue_refresh_token(db_session, user=u2, workspace_id=ws2.id)
    issue_refresh_token(db_session, user=u2, workspace_id=ws2.id)
    db_session.flush()

    count = revoke_all_user_tokens(db_session, u1.id)
    assert count == 2
    db_session.flush()

    # Verify u1 tokens are revoked with replaced_by_id None
    u1_tokens = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == u1.id)).all()
    assert len(u1_tokens) == 2
    for t in u1_tokens:
        assert t.revoked_at is not None
        assert t.replaced_by_id is None

    # Verify u2 tokens remain active
    u2_tokens = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == u2.id)).all()
    assert len(u2_tokens) == 2
    for t in u2_tokens:
        assert t.revoked_at is None
