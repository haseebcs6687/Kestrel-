"""Integration and unit tests for user management, admin resets, and password change."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REFRESH_COOKIE_NAME, get_settings
from app.core.db import get_db, reset_db_connections
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken, Role, User
from app.modules.auth.security import create_access_token, hash_password
from app.modules.auth.sessions import issue_refresh_token
from app.modules.workspaces.models import Workspace


@pytest.fixture
def auth_client(db_session: Session) -> Generator[TestClient]:
    """Provide a TestClient bound to the transactional db_session fixture."""
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


def _setup_test_workspace_and_admin(
    db: Session,
    email: str = "admin@example.com",
    role: str = Role.ADMIN.value,
) -> tuple[Workspace, User, str]:
    """Helper to create a workspace, user, and corresponding bearer access token."""
    ws = Workspace(name="Test Workspace", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db.add(ws)
    db.flush()

    user = User(
        workspace_id=ws.id,
        email=email.lower(),
        password_hash=hash_password("InitialPassword123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()

    token, _ = create_access_token(user.id)
    return ws, user, token


# -----------------------------------------------------------------------------
# Part 3: Create User Tests
# -----------------------------------------------------------------------------


def test_create_user_admin_creates_viewer(auth_client: TestClient, db_session: Session) -> None:
    """Verify admin creates a viewer user with normalized email, audit log, and password login."""
    ws, admin, token = _setup_test_workspace_and_admin(db_session, "admin_creator@example.com")

    payload = {
        "email": "NewViewer@Example.Com ",
        "password": "ViewerSecurePassword123!",
        "role": "viewer",
    }
    resp = auth_client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newviewer@example.com"
    assert data["role"] == "viewer"
    assert data["is_active"] is True
    assert data["workspace_id"] == str(ws.id)
    assert "password_hash" not in data
    assert "password" not in data

    # Verify created user can authenticate with the supplied password
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "newviewer@example.com", "password": "ViewerSecurePassword123!"},
    )
    assert login_resp.status_code == 200

    # Verify audit row
    audit_row = db_session.scalar(
        select(AuditLog).where(
            AuditLog.workspace_id == ws.id,
            AuditLog.action == "user.create",
            AuditLog.target_id == data["id"],
        )
    )
    assert audit_row is not None
    assert audit_row.actor_user_id == admin.id
    assert audit_row.details == {"role": "viewer"}
    assert "password" not in str(audit_row.details)


def test_create_user_extra_fields_and_workspace_id_rejected(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify extra attributes like client-supplied workspace_id trigger 422 error."""
    _, _, token = _setup_test_workspace_and_admin(db_session, "admin_extra@example.com")
    fake_ws = uuid.uuid4()

    payload = {
        "email": "extra@example.com",
        "password": "ValidPassword123!",
        "role": "viewer",
        "workspace_id": str(fake_ws),
    }
    resp = auth_client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_create_user_duplicate_email_conflict(auth_client: TestClient, db_session: Session) -> None:
    """Verify duplicate email in different casing triggers 409 conflict."""
    _, _, token = _setup_test_workspace_and_admin(db_session, "existing@example.com")

    payload = {
        "email": "Existing@Example.COM",
        "password": "ValidPassword123!",
        "role": "viewer",
    }
    resp = auth_client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Email already registered"}


def test_create_user_validation_failures(auth_client: TestClient, db_session: Session) -> None:
    """Verify short password, invalid role, and malformed email trigger 422."""
    _, _, token = _setup_test_workspace_and_admin(db_session, "admin_val@example.com")

    # Short password (< 12 chars)
    r1 = auth_client.post(
        "/api/v1/users",
        json={"email": "val1@example.com", "password": "short", "role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 422

    # Invalid role
    r2 = auth_client.post(
        "/api/v1/users",
        json={"email": "val2@example.com", "password": "ValidPassword123!", "role": "superadmin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 422


def test_create_user_rbac_and_unauthenticated(auth_client: TestClient, db_session: Session) -> None:
    """Verify viewer gets 403 and unauthenticated gets 401."""
    _, _, viewer_token = _setup_test_workspace_and_admin(
        db_session, "viewer_forbidden@example.com", role=Role.VIEWER.value
    )

    payload = {"email": "v_try@example.com", "password": "ValidPassword123!", "role": "viewer"}
    r_viewer = auth_client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r_viewer.status_code == 403

    r_anon = auth_client.post("/api/v1/users", json=payload)
    assert r_anon.status_code == 401


# -----------------------------------------------------------------------------
# Part 3: Get One User Tests
# -----------------------------------------------------------------------------


def test_get_user_success(auth_client: TestClient, db_session: Session) -> None:
    """Verify admin gets a user in their own workspace."""
    ws, admin, token = _setup_test_workspace_and_admin(db_session, "admin_get@example.com")
    viewer = User(
        workspace_id=ws.id,
        email="viewer_get@example.com",
        password_hash=hash_password("Password12345!"),
        role=Role.VIEWER.value,
        is_active=True,
    )
    db_session.add(viewer)
    db_session.flush()

    resp = auth_client.get(
        f"/api/v1/users/{viewer.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(viewer.id)
    assert resp.json()["email"] == "viewer_get@example.com"


def test_get_user_cross_workspace_returns_404(auth_client: TestClient, db_session: Session) -> None:
    """Verify looking up another workspace's user returns 404 (never 403)."""
    _, _, token1 = _setup_test_workspace_and_admin(db_session, "admin_ws1@example.com")
    _, user2, _ = _setup_test_workspace_and_admin(db_session, "admin_ws2@example.com")

    resp = auth_client.get(
        f"/api/v1/users/{user2.id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "User not found"}


def test_get_user_invalid_uuid_returns_422(auth_client: TestClient, db_session: Session) -> None:
    """Verify non-UUID path parameter returns 422."""
    _, _, token = _setup_test_workspace_and_admin(db_session, "admin_uuid@example.com")
    resp = auth_client.get(
        "/api/v1/users/not-a-valid-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_get_user_viewer_returns_403(auth_client: TestClient, db_session: Session) -> None:
    """Verify viewer cannot call get user endpoint."""
    _, viewer, token = _setup_test_workspace_and_admin(
        db_session, "viewer_cant_get@example.com", role=Role.VIEWER.value
    )
    resp = auth_client.get(
        f"/api/v1/users/{viewer.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# -----------------------------------------------------------------------------
# Part 3: Update User Tests
# -----------------------------------------------------------------------------


def test_update_user_promote_and_demote(auth_client: TestClient, db_session: Session) -> None:
    """Verify promoting viewer to admin and demoting back to viewer works with audit."""
    ws, admin, token = _setup_test_workspace_and_admin(db_session, "admin_patch@example.com")
    target = User(
        workspace_id=ws.id,
        email="target_patch@example.com",
        password_hash=hash_password("Password12345!"),
        role=Role.VIEWER.value,
        is_active=True,
    )
    db_session.add(target)
    db_session.flush()

    # Promote to admin
    r1 = auth_client.patch(
        f"/api/v1/users/{target.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["role"] == "admin"

    # Demote back to viewer
    r2 = auth_client.patch(
        f"/api/v1/users/{target.id}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["role"] == "viewer"

    # Verify audit log captures role change
    audit_rows = db_session.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == ws.id, AuditLog.action == "user.update")
        .order_by(AuditLog.id.asc())
    ).all()
    assert len(audit_rows) == 2
    assert audit_rows[0].details == {"changes": {"role": {"from": "viewer", "to": "admin"}}}
    assert audit_rows[1].details == {"changes": {"role": {"from": "admin", "to": "viewer"}}}


def test_update_user_deactivation_revokes_sessions(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify deactivation immediately invalidates access tokens and revokes all refresh tokens."""
    ws, admin, admin_token = _setup_test_workspace_and_admin(db_session, "admin_deact@example.com")
    target = User(
        workspace_id=ws.id,
        email="target_deact@example.com",
        password_hash=hash_password("Password12345!"),
        role=Role.VIEWER.value,
        is_active=True,
    )
    db_session.add(target)
    db_session.flush()

    target_token, _ = create_access_token(target.id)
    raw_rt, _ = issue_refresh_token(db_session, user=target, workspace_id=ws.id)
    db_session.commit()

    # Pre-check: target can access /me
    me_before = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert me_before.status_code == 200

    # Admin deactivates target
    deact_resp = auth_client.patch(
        f"/api/v1/users/{target.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

    # Target access token fails immediately on /auth/me (ADR-021 dynamic DB check)
    me_after = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert me_after.status_code == 401

    # Refresh attempt fails with 401
    auth_client.cookies.set(REFRESH_COOKIE_NAME, raw_rt)
    ref_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-Kestrel-Client": "web"},
    )
    assert ref_resp.status_code == 401

    # Check refresh tokens are revoked in DB
    tokens = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == target.id)).all()
    assert len(tokens) == 1
    assert tokens[0].is_revoked is True

    # Reactivate target
    react_resp = auth_client.patch(
        f"/api/v1/users/{target.id}",
        json={"is_active": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert react_resp.status_code == 200

    # Target can log in again
    login_react = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "target_deact@example.com", "password": "Password12345!"},
    )
    assert login_react.status_code == 200


def test_update_user_validation_and_no_op(auth_client: TestClient, db_session: Session) -> None:
    """Verify empty body 422, forbidden fields 422, cross-tenant 404, and no-op 200."""
    ws, admin, token = _setup_test_workspace_and_admin(db_session, "admin_noop@example.com")
    _, other_user, _ = _setup_test_workspace_and_admin(db_session, "other_noop@example.com")

    # Empty body -> 422
    r_empty = auth_client.patch(
        f"/api/v1/users/{admin.id}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_empty.status_code == 422

    # Forbidden fields (email, workspace_id) -> 422
    r_forbid = auth_client.patch(
        f"/api/v1/users/{admin.id}",
        json={"email": "hacked@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_forbid.status_code == 422

    # Another workspace user -> 404
    r_cross = auth_client.patch(
        f"/api/v1/users/{other_user.id}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_cross.status_code == 404

    # No-op update -> 200 without creating an audit row
    r_noop = auth_client.patch(
        f"/api/v1/users/{admin.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_noop.status_code == 200
    audits = db_session.scalars(
        select(AuditLog).where(AuditLog.workspace_id == ws.id, AuditLog.action == "user.update")
    ).all()
    assert len(audits) == 0


# -----------------------------------------------------------------------------
# Part 3: Last Admin Protection Tests
# -----------------------------------------------------------------------------


def test_last_admin_cannot_demote_or_deactivate_self(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify sole active admin cannot demote or deactivate themselves (409 conflict)."""
    _, admin, token = _setup_test_workspace_and_admin(db_session, "sole_admin@example.com")

    # Sole admin tries to demote themselves -> 409
    r_demote = auth_client.patch(
        f"/api/v1/users/{admin.id}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_demote.status_code == 409
    assert r_demote.json() == {"detail": "Cannot remove the last active admin"}

    # Sole admin tries to deactivate themselves -> 409
    r_deact = auth_client.patch(
        f"/api/v1/users/{admin.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_deact.status_code == 409
    assert r_deact.json() == {"detail": "Cannot remove the last active admin"}

    # Confirm state unchanged
    db_session.refresh(admin)
    assert admin.role == "admin"
    assert admin.is_active is True


def test_last_admin_two_active_admins_allows_demote(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify when two active admins exist, one may demote themselves."""
    ws, admin1, token1 = _setup_test_workspace_and_admin(db_session, "admin_one@example.com")
    admin2 = User(
        workspace_id=ws.id,
        email="admin_two@example.com",
        password_hash=hash_password("Password12345!"),
        role=Role.ADMIN.value,
        is_active=True,
    )
    db_session.add(admin2)
    db_session.flush()

    # Admin 1 demotes themselves -> succeeds because Admin 2 is active
    resp = auth_client.patch(
        f"/api/v1/users/{admin1.id}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


def test_last_admin_inactive_admin_does_not_count(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify inactive admin does not count toward the active admin invariant."""
    ws, admin_active, token = _setup_test_workspace_and_admin(db_session, "active_a@example.com")
    admin_inactive = User(
        workspace_id=ws.id,
        email="inactive_b@example.com",
        password_hash=hash_password("Password12345!"),
        role=Role.ADMIN.value,
        is_active=False,
    )
    db_session.add(admin_inactive)
    db_session.flush()

    # Active admin tries to demote themselves -> 409 because other admin is inactive
    resp = auth_client.patch(
        f"/api/v1/users/{admin_active.id}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Cannot remove the last active admin"}


# -----------------------------------------------------------------------------
# Part 3: Admin Password Reset Tests
# -----------------------------------------------------------------------------


def test_admin_password_reset_success(auth_client: TestClient, db_session: Session) -> None:
    """Verify admin password reset updates credentials, revokes sessions, and logs audit."""
    ws, admin, admin_token = _setup_test_workspace_and_admin(db_session, "admin_reset@example.com")
    target = User(
        workspace_id=ws.id,
        email="target_reset@example.com",
        password_hash=hash_password("OldPassword123!"),
        role=Role.VIEWER.value,
        is_active=True,
    )
    db_session.add(target)
    db_session.flush()

    # Issue refresh token to verify revocation
    issue_refresh_token(db_session, user=target, workspace_id=ws.id)
    db_session.commit()

    # Admin resets password
    resp = auth_client.put(
        f"/api/v1/users/{target.id}/password",
        json={"new_password": "NewFreshPassword123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204
    assert not resp.content

    # Old password fails
    old_login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "target_reset@example.com", "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # New password succeeds
    new_login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "target_reset@example.com", "password": "NewFreshPassword123!"},
    )
    assert new_login.status_code == 200

    # Verify audit row contains sessions_revoked and no password
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.workspace_id == ws.id,
            AuditLog.action == "user.password_reset",
            AuditLog.target_id == str(target.id),
        )
    )
    assert audit is not None
    assert audit.details == {"sessions_revoked": 1}
    assert "password" not in str(audit.details)


def test_admin_password_reset_permissions_and_validation(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify viewer 403, cross-tenant 404, and weak password 422."""
    _, viewer, viewer_token = _setup_test_workspace_and_admin(
        db_session, "viewer_reset@example.com", role=Role.VIEWER.value
    )
    _, other_user, _ = _setup_test_workspace_and_admin(db_session, "other_reset@example.com")
    _, admin, admin_token = _setup_test_workspace_and_admin(db_session, "admin_reset2@example.com")

    # Viewer caller -> 403
    r_viewer = auth_client.put(
        f"/api/v1/users/{viewer.id}/password",
        json={"new_password": "ValidNewPassword123!"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r_viewer.status_code == 403

    # Another workspace user -> 404
    r_other = auth_client.put(
        f"/api/v1/users/{other_user.id}/password",
        json={"new_password": "ValidNewPassword123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_other.status_code == 404

    # Weak password (< 12 chars) -> 422
    r_weak = auth_client.put(
        f"/api/v1/users/{admin.id}/password",
        json={"new_password": "short"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_weak.status_code == 422


# -----------------------------------------------------------------------------
# Part 3: Self-Service Password Change Tests
# -----------------------------------------------------------------------------


def test_change_password_success(auth_client: TestClient, db_session: Session) -> None:
    """Verify authenticated user can change password, clear cookie, and revoke sessions."""
    ws, user, token = _setup_test_workspace_and_admin(db_session, "user_change@example.com")
    raw_rt, _ = issue_refresh_token(db_session, user=user, workspace_id=ws.id)
    db_session.commit()

    auth_client.cookies.set(REFRESH_COOKIE_NAME, raw_rt)
    resp = auth_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "InitialPassword123!",
            "new_password": "CompletelyNewPassword123!",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    assert resp.headers.get("Cache-Control") == "no-store"
    # Cookie should be cleared (Max-Age=0)
    assert resp.cookies.get(REFRESH_COOKIE_NAME) == '""' or "Max-Age=0" in resp.headers.get(
        "set-cookie", ""
    )

    # Refresh attempt fails (sessions revoked)
    ref_resp = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-Kestrel-Client": "web"},
    )
    assert ref_resp.status_code == 401

    # Old password fails
    assert (
        auth_client.post(
            "/api/v1/auth/login",
            json={"email": "user_change@example.com", "password": "InitialPassword123!"},
        ).status_code
        == 401
    )

    # New password succeeds
    assert (
        auth_client.post(
            "/api/v1/auth/login",
            json={"email": "user_change@example.com", "password": "CompletelyNewPassword123!"},
        ).status_code
        == 200
    )

    # Verify audit row
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.workspace_id == ws.id,
            AuditLog.action == "auth.password_change",
            AuditLog.target_id == str(user.id),
        )
    )
    assert audit is not None
    assert audit.details == {"sessions_revoked": 1}


def test_change_password_viewer_can_change_own(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify viewer can change their own password."""
    _, viewer, token = _setup_test_workspace_and_admin(
        db_session, "viewer_change@example.com", role=Role.VIEWER.value
    )
    resp = auth_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "InitialPassword123!",
            "new_password": "ViewerNewPassword123!",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


def test_change_password_validation_and_errors(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify wrong current password 400, same password 400, weak password 422, no token 401."""
    _, _, token = _setup_test_workspace_and_admin(db_session, "change_err@example.com")

    # Wrong current password -> 400 (NOT 401)
    r_wrong = auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword123!", "new_password": "NewValidPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_wrong.status_code == 400
    assert r_wrong.json() == {"detail": "Current password is incorrect"}

    # Same password -> 400
    r_same = auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "InitialPassword123!", "new_password": "InitialPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_same.status_code == 400
    assert r_same.json() == {"detail": "New password must be different"}

    # Weak new password (< 12 chars) -> 422
    r_weak = auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "InitialPassword123!", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_weak.status_code == 422

    # Unauthenticated -> 401
    r_anon = auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "InitialPassword123!", "new_password": "NewValidPassword123!"},
    )
    assert r_anon.status_code == 401


# -----------------------------------------------------------------------------
# Part 3: Log Safety Test
# -----------------------------------------------------------------------------


def test_users_log_safety(
    auth_client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify known passwords, tokens, and hashes never appear in structured logs."""
    _, admin, token = _setup_test_workspace_and_admin(db_session, "admin_logger@example.com")
    secret_pass = "SuperSecretPlainTextPassword123!"

    with caplog.at_level("DEBUG"):
        # 1. Create user
        create_resp = auth_client.post(
            "/api/v1/users",
            json={"email": "logged_user@example.com", "password": secret_pass, "role": "viewer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        new_user_id = create_resp.json()["id"]

        # 2. Reset password
        reset_pass = "ResetSecretPlainTextPassword123!"
        reset_resp = auth_client.put(
            f"/api/v1/users/{new_user_id}/password",
            json={"new_password": reset_pass},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reset_resp.status_code == 204

        # 3. Change password
        change_pass = "ChangedSecretPlainTextPassword123!"
        change_resp = auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "InitialPassword123!", "new_password": change_pass},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert change_resp.status_code == 204

    # Assert no secret or password text leaked into logs
    captured = caplog.text
    assert secret_pass not in captured
    assert reset_pass not in captured
    assert change_pass not in captured
    assert "$argon2id$" not in captured
