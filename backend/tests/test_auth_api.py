"""Integration tests for authentication, user registration, profiles, and authorization."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db, reset_db_connections
from app.main import create_app
from app.modules.auth.models import Role, User
from app.modules.auth.security import hash_password
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


def test_register_success(auth_client: TestClient) -> None:
    """Verify registration creates user and workspace, normalizes email, and assigns admin role."""
    payload = {
        "email": "Owner@KestrelAI.com",
        "password": "SecurePassword123!",
        "workspace_name": "Kestrel Central",
    }
    resp = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201

    data = resp.json()
    assert data["email"] == "owner@kestrelai.com"
    assert data["role"] == "admin"
    assert data["is_active"] is True
    assert "workspace_id" in data
    assert "id" in data
    assert "password_hash" not in data


def test_register_duplicate_email_conflict(auth_client: TestClient) -> None:
    """Verify duplicate email registration returns 409 Conflict."""
    payload = {
        "email": "duplicate@test.com",
        "password": "Password123456!",
        "workspace_name": "First Org",
    }
    resp1 = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["detail"] == "Email already registered"


def test_register_validation_constraints(auth_client: TestClient) -> None:
    """Verify input validation rules: short password, short workspace, invalid email."""
    # 1. Short password (<12 chars)
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@test.com",
            "password": "short",
            "workspace_name": "Valid Org",
        },
    )
    assert resp.status_code == 422

    # 2. Short workspace name (<2 chars)
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid@test.com",
            "password": "ValidPassword123!",
            "workspace_name": "a",
        },
    )
    assert resp.status_code == 422

    # 3. Invalid email syntax
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "workspace_name": "Valid Org",
        },
    )
    assert resp.status_code == 422

    # 4. Long password (>128 chars)
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid@test.com",
            "password": "A" * 129,
            "workspace_name": "Valid Org",
        },
    )
    assert resp.status_code == 422


def test_register_mass_assignment_protection(auth_client: TestClient) -> None:
    """Verify extra attributes like role or is_active are rejected with 422."""
    payload = {
        "email": "attacker@test.com",
        "password": "Password123456!",
        "workspace_name": "Evil Corp",
        "role": "superadmin",
        "is_active": False,
        "workspace_id": str(uuid.uuid4()),
    }
    resp = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


def test_register_disabled_returns_403(db_session: Session) -> None:
    """Verify registration attempts return 403 when registration_enabled is False."""
    get_settings.cache_clear()
    reset_db_connections()
    app = create_app()

    def override_settings() -> Settings:
        current = get_settings()
        return current.model_copy(update={"registration_enabled": False})

    def override_get_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "disabled@test.com",
                "password": "Password123456!",
                "workspace_name": "Disabled Org",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Registration is currently disabled"


def test_login_success_and_headers(auth_client: TestClient) -> None:
    """Verify login issues bearer token and sets no-cache security headers."""
    register_payload = {
        "email": "login@test.com",
        "password": "MySecretPassword123!",
        "workspace_name": "Login Org",
    }
    auth_client.post("/api/v1/auth/register", json=register_payload)

    login_payload = {
        "email": "login@test.com",
        "password": "MySecretPassword123!",
    }
    resp = auth_client.post("/api/v1/auth/login", json=login_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert resp.headers.get("Cache-Control") == "no-store"
    assert resp.headers.get("Pragma") == "no-cache"


def test_login_invalid_password_returns_401(auth_client: TestClient) -> None:
    """Verify invalid password returns 401 with WWW-Authenticate header."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@test.com",
            "password": "CorrectPassword123!",
            "workspace_name": "Auth Org",
        },
    )

    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@test.com", "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_login_nonexistent_email_returns_401(auth_client: TestClient) -> None:
    """Verify nonexistent email returns identical 401 error."""
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "RandomPassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_login_inactive_user_returns_401(auth_client: TestClient, db_session: Session) -> None:
    """Verify inactive users are rejected during authentication with 401."""
    ws = Workspace(name="Inactive WS", slug="inactive-ws-001")
    db_session.add(ws)
    db_session.flush()

    user = User(
        workspace_id=ws.id,
        email="inactive@test.com",
        password_hash=hash_password("Password123456!"),
        role=Role.ADMIN.value,
        is_active=False,
    )
    db_session.add(user)
    db_session.flush()

    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@test.com", "password": "Password123456!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


def test_get_me_profile_and_workspace(auth_client: TestClient) -> None:
    """Verify /auth/me returns user profile and nested workspace details."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@test.com",
            "password": "Password123456!",
            "workspace_name": "Me Workspace",
        },
    )
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "me@test.com", "password": "Password123456!"},
    )
    token = login_resp.json()["access_token"]

    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@test.com"
    assert data["role"] == "admin"
    assert "workspace" in data
    assert data["workspace"]["name"] == "Me Workspace"
    assert data["workspace"]["slug"].startswith("me-workspace-")


def test_get_me_unauthenticated_failures(auth_client: TestClient) -> None:
    """Verify /auth/me returns 401 on missing, malformed, or invalid tokens."""
    # 1. Missing Authorization header
    resp = auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"

    # 2. Bogus token
    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer bogus_token_string"},
    )
    assert resp.status_code == 401


def test_get_me_deactivated_user_rejected_dynamically(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify user deactivated after token issuance is rejected immediately (ADR-021)."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "dynamic@test.com",
            "password": "Password123456!",
            "workspace_name": "Dynamic Org",
        },
    )
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "dynamic@test.com", "password": "Password123456!"},
    )
    token = login_resp.json()["access_token"]

    # Deactivate the user directly in database
    user = db_session.query(User).filter_by(email="dynamic@test.com").one()
    user.is_active = False
    db_session.flush()

    # Even though JWT has valid signature and unexpired exp, live DB check must reject
    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


def test_list_users_admin_and_viewer_rbac(auth_client: TestClient, db_session: Session) -> None:
    """Verify /users endpoint permits Admins and rejects Viewers with 403."""
    # 1. Register admin
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin_user@test.com",
            "password": "Password123456!",
            "workspace_name": "RBAC Org",
        },
    )
    admin_login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_user@test.com", "password": "Password123456!"},
    )
    admin_token = admin_login.json()["access_token"]

    # Retrieve workspace id
    admin = db_session.query(User).filter_by(email="admin_user@test.com").one()

    # 2. Add a viewer user to the same workspace
    viewer = User(
        workspace_id=admin.workspace_id,
        email="viewer_user@test.com",
        password_hash=hash_password("Password123456!"),
        role=Role.VIEWER.value,
    )
    db_session.add(viewer)
    db_session.flush()

    viewer_login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "viewer_user@test.com", "password": "Password123456!"},
    )
    viewer_token = viewer_login.json()["access_token"]

    # 3. Admin call succeeds
    admin_resp = auth_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 200
    users_list = admin_resp.json()
    assert len(users_list) == 2
    emails = [u["email"] for u in users_list]
    assert "admin_user@test.com" in emails
    assert "viewer_user@test.com" in emails

    # 4. Viewer call is forbidden with 403
    viewer_resp = auth_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert viewer_resp.status_code == 403
    assert viewer_resp.json()["detail"] == "Insufficient permissions"


def test_list_users_cross_workspace_isolation(auth_client: TestClient, db_session: Session) -> None:
    """Verify /users never leaks users from other workspaces."""
    # 1. Register Org 1
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "org1_admin@test.com",
            "password": "Password123456!",
            "workspace_name": "Org 1",
        },
    )
    login1 = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "org1_admin@test.com", "password": "Password123456!"},
    )
    token1 = login1.json()["access_token"]

    # 2. Register Org 2
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "org2_admin@test.com",
            "password": "Password123456!",
            "workspace_name": "Org 2",
        },
    )

    # 3. Org 1 queries /users -> must contain ONLY Org 1 users
    resp = auth_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 1
    assert users[0]["email"] == "org1_admin@test.com"


def test_login_wrong_password_and_unknown_email_identical_responses(
    auth_client: TestClient,
) -> None:
    """Verify wrong password and unknown email return identical 401 status and body."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "registered@test.com",
            "password": "ValidPassword123!",
            "workspace_name": "Id Org",
        },
    )

    resp_wrong_pw = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "registered@test.com", "password": "WrongPassword123!"},
    )
    resp_unknown_email = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "AnyPassword123!"},
    )

    assert resp_wrong_pw.status_code == 401
    assert resp_unknown_email.status_code == 401
    assert resp_wrong_pw.headers.get("WWW-Authenticate") == "Bearer"
    assert resp_unknown_email.headers.get("WWW-Authenticate") == "Bearer"
    assert (
        resp_wrong_pw.json() == resp_unknown_email.json() == {"detail": "Invalid email or password"}
    )


def test_login_spy_verify_password_called_for_unknown_email(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify timing equalization: verify_password is still called for an unknown email."""
    from app.modules.auth import service as auth_service

    calls = []
    original_verify = auth_service.verify_password

    def spy_verify(plain: str, hashed: str) -> bool:
        calls.append((plain, hashed))
        return original_verify(plain, hashed)

    monkeypatch.setattr(auth_service, "verify_password", spy_verify)

    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "Password123456!"},
    )
    assert resp.status_code == 401
    assert len(calls) == 1
    assert calls[0][0] == "Password123456!"
    assert calls[0][1].startswith("$argon2id$")


def test_login_email_lookup_is_case_insensitive(auth_client: TestClient) -> None:
    """Verify email login handles uppercase input correctly via normalization."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "case.sensitive@test.com",
            "password": "Password123456!",
            "workspace_name": "Case Org",
        },
    )

    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "CASE.SENSITIVE@TEST.COM", "password": "Password123456!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_get_me_token_user_deleted_from_db_returns_401(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify /me returns 401 if the user was deleted from the database after token issuance."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "to_be_deleted@test.com",
            "password": "Password123456!",
            "workspace_name": "Delete Org",
        },
    )
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "to_be_deleted@test.com", "password": "Password123456!"},
    )
    token = login_resp.json()["access_token"]

    user = db_session.query(User).filter_by(email="to_be_deleted@test.com").one()
    db_session.delete(user)
    db_session.flush()

    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_list_users_demoted_admin_takes_effect_immediately(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify demoting an admin to viewer takes effect on the next request with the same token."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "demote_admin@test.com",
            "password": "Password123456!",
            "workspace_name": "Demote Org",
        },
    )
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "demote_admin@test.com", "password": "Password123456!"},
    )
    token = login_resp.json()["access_token"]

    # Initial call as admin succeeds
    resp1 = auth_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200

    # Demote in database directly
    admin = db_session.query(User).filter_by(email="demote_admin@test.com").one()
    admin.role = Role.VIEWER.value
    db_session.flush()

    # Immediate next request fails with 403
    resp2 = auth_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 403
    assert resp2.json()["detail"] == "Insufficient permissions"


def test_list_users_pagination_limit_and_offset(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify limit/offset pagination on /api/v1/users."""
    auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "page_admin@test.com",
            "password": "Password123456!",
            "workspace_name": "Page Org",
        },
    )
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "page_admin@test.com", "password": "Password123456!"},
    )
    token = login_resp.json()["access_token"]
    admin = db_session.query(User).filter_by(email="page_admin@test.com").one()

    # Add 2 more users
    for i in range(2):
        u = User(
            workspace_id=admin.workspace_id,
            email=f"page_user_{i}@test.com",
            password_hash=hash_password("Password123456!"),
            role=Role.VIEWER.value,
        )
        db_session.add(u)
    db_session.flush()

    # Page 1: limit 2, offset 0 -> 2 users
    resp_p1 = auth_client.get(
        "/api/v1/users?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert len(data_p1) == 2

    # Page 2: limit 2, offset 2 -> 1 user
    resp_p2 = auth_client.get(
        "/api/v1/users?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2) == 1
    assert data_p2[0]["id"] not in [u["id"] for u in data_p1]


def test_log_safety_never_leaks_password_token_or_hash(
    auth_client: TestClient, caplog: pytest.LogCaptureFixture, db_session: Session
) -> None:
    """Verify log output during register + login never contains password, token, or hash."""
    import logging

    caplog.set_level(logging.DEBUG)
    known_password = "SuperSecretPlainTextPassword123!"

    reg_resp = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "safe_log@test.com",
            "password": known_password,
            "workspace_name": "Log Safe Org",
        },
    )
    assert reg_resp.status_code == 201

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "safe_log@test.com", "password": known_password},
    )
    assert login_resp.status_code == 200
    raw_token = login_resp.json()["access_token"]

    user = db_session.query(User).filter_by(email="safe_log@test.com").one()
    pw_hash = user.password_hash

    # Assert captured log text is strictly clean
    all_logs = caplog.text
    assert known_password not in all_logs
    assert raw_token not in all_logs
    assert pw_hash not in all_logs
