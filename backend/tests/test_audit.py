"""Integration tests for audit service, validation defense-in-depth, and audit log endpoints."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, reset_db_connections
from app.main import create_app
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditLog
from app.modules.auth.models import Role, User
from app.modules.auth.security import create_access_token, hash_password
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


def _create_workspace_and_user(
    db: Session,
    name: str = "Audit Org",
    email: str = "audit_admin@example.com",
    role: str = Role.ADMIN.value,
) -> tuple[Workspace, User]:
    """Helper to persist a test workspace and user."""
    workspace = Workspace(name=name, slug=f"audit-org-{uuid.uuid4().hex[:6]}")
    db.add(workspace)
    db.flush()

    user = User(
        workspace_id=workspace.id,
        email=email,
        password_hash=hash_password("SuperSecretPassword123!"),
        role=role,
    )
    db.add(user)
    db.flush()
    return workspace, user


def test_audit_record_success(db_session: Session) -> None:
    """Verify audit_service.record writes complete event data to database."""
    workspace, user = _create_workspace_and_user(db_session)
    res_id = uuid.uuid4()

    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="user.update",
        resource_type="user",
        actor_id=user.id,
        actor_type="user",
        resource_id=res_id,
        details={"updated_field": "timezone"},
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 TestBrowser",
    )
    assert entry.id is not None

    db_entry = db_session.scalar(select(AuditLog).where(AuditLog.id == entry.id))
    assert db_entry is not None
    assert db_entry.workspace_id == workspace.id
    assert db_entry.actor_id == user.id
    assert db_entry.actor_type == "user"
    assert db_entry.action == "user.update"
    assert db_entry.resource_type == "user"
    assert db_entry.resource_id == res_id
    assert db_entry.details == {"updated_field": "timezone"}
    assert db_entry.ip_address == "192.168.1.100"
    assert db_entry.user_agent == "Mozilla/5.0 TestBrowser"


def test_audit_record_forbidden_keys(db_session: Session) -> None:
    """Verify defense-in-depth guard rejects audit details containing sensitive credential keys."""
    workspace, _ = _create_workspace_and_user(db_session, email="forbidden_keys@example.com")

    forbidden_payloads = [
        {"user_password": "plain_password"},
        {"nested": {"auth_token": "token_string"}},
        {"secret_key": "jwt_secret"},
        {"session_cookie": "cookie_data"},
        {"password_hash": "argon_hash"},
        {"authorization_header": "Bearer xyz"},
    ]

    for payload in forbidden_payloads:
        with pytest.raises(ValueError, match="forbidden security key"):
            audit_service.record(
                db_session,
                workspace_id=workspace.id,
                action="test.sensitive",
                resource_type="test",
                details=payload,
            )


def test_audit_participates_in_transaction_rollback(db_session: Session) -> None:
    """Verify audit log row is rolled back when participating in a failed transaction."""
    workspace, _ = _create_workspace_and_user(db_session, email="rollback_audit@example.com")

    # Start nested savepoint
    savepoint = db_session.begin_nested()
    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="transaction.fail",
        resource_type="test",
        details={"attempt": 1},
    )
    recorded_id = entry.id
    # Explicitly rollback the savepoint
    savepoint.rollback()

    # Verify not persisted
    persisted = db_session.scalar(select(AuditLog).where(AuditLog.id == recorded_id))
    assert persisted is None


def test_audit_log_endpoint_admin_only(auth_client: TestClient, db_session: Session) -> None:
    """Verify audit-logs endpoint requires administrative credentials (RBAC)."""
    workspace, admin_user = _create_workspace_and_user(
        db_session, email="admin_endpoint@example.com", role=Role.ADMIN.value
    )
    viewer_user = User(
        workspace_id=workspace.id,
        email="viewer_endpoint@example.com",
        password_hash=hash_password("SuperSecretPassword123!"),
        role=Role.VIEWER.value,
    )
    db_session.add(viewer_user)
    db_session.flush()

    admin_token, _ = create_access_token(admin_user.id)
    viewer_token, _ = create_access_token(viewer_user.id)

    # 1. Unauthenticated -> 401
    resp_unauth = auth_client.get("/api/v1/audit-logs")
    assert resp_unauth.status_code == 401

    # 2. Viewer -> 403
    resp_viewer = auth_client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp_viewer.status_code == 403

    # 3. Admin -> 200
    resp_admin = auth_client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    assert isinstance(resp_admin.json(), list)


def test_audit_log_workspace_isolation(auth_client: TestClient, db_session: Session) -> None:
    """Verify audit logs are strictly isolated by workspace boundary (ADR-022)."""
    ws_a, admin_a = _create_workspace_and_user(
        db_session, name="Workspace Alpha", email="admin_alpha@example.com"
    )
    ws_b, admin_b = _create_workspace_and_user(
        db_session, name="Workspace Beta", email="admin_beta@example.com"
    )

    # Record events in Workspace A
    audit_service.record(
        db_session,
        workspace_id=ws_a.id,
        action="alpha.action",
        resource_type="alpha",
        actor_id=admin_a.id,
    )

    # Record events in Workspace B
    audit_service.record(
        db_session,
        workspace_id=ws_b.id,
        action="beta.action",
        resource_type="beta",
        actor_id=admin_b.id,
    )

    token_a, _ = create_access_token(admin_a.id)
    token_b, _ = create_access_token(admin_b.id)

    # Admin A query
    resp_a = auth_client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a.status_code == 200
    actions_a = [item["action"] for item in resp_a.json()]
    assert "alpha.action" in actions_a
    assert "beta.action" not in actions_a

    # Admin B query
    resp_b = auth_client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    actions_b = [item["action"] for item in resp_b.json()]
    assert "beta.action" in actions_b
    assert "alpha.action" not in actions_b


def test_audit_log_action_filter(auth_client: TestClient, db_session: Session) -> None:
    """Verify audit log endpoint accurately filters by action parameter."""
    workspace, admin = _create_workspace_and_user(db_session, email="filter_admin@example.com")

    audit_service.record(
        db_session, workspace_id=workspace.id, action="auth.login", resource_type="user"
    )
    audit_service.record(
        db_session, workspace_id=workspace.id, action="auth.logout", resource_type="user"
    )
    audit_service.record(
        db_session, workspace_id=workspace.id, action="auth.refresh", resource_type="user"
    )

    token, _ = create_access_token(admin.id)
    resp = auth_client.get(
        "/api/v1/audit-logs?action=auth.login",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert all(item["action"] == "auth.login" for item in items)


def test_audit_log_pagination(auth_client: TestClient, db_session: Session) -> None:
    """Verify audit log endpoint limit and offset query pagination."""
    workspace, admin = _create_workspace_and_user(db_session, email="pagination_admin@example.com")

    for i in range(5):
        audit_service.record(
            db_session,
            workspace_id=workspace.id,
            action=f"action.step.{i}",
            resource_type="step",
        )

    token, _ = create_access_token(admin.id)

    # Page 1: limit 2, offset 0
    resp_p1 = auth_client.get(
        "/api/v1/audit-logs?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p1.status_code == 200
    items_p1 = resp_p1.json()
    assert len(items_p1) == 2

    # Page 2: limit 2, offset 2
    resp_p2 = auth_client.get(
        "/api/v1/audit-logs?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p2.status_code == 200
    items_p2 = resp_p2.json()
    assert len(items_p2) == 2

    # Verify no overlapping IDs across pages
    ids_p1 = {item["id"] for item in items_p1}
    ids_p2 = {item["id"] for item in items_p2}
    assert ids_p1.isdisjoint(ids_p2)


def test_register_with_64_char_request_id(auth_client: TestClient, db_session: Session) -> None:
    """Verify registration with 64-character valid X-Request-ID stores the full ID."""
    req_id_64 = "A" * 32 + "_" + "B" * 29 + "-1"
    assert len(req_id_64) == 64
    payload = {
        "email": "req64@example.com",
        "password": "SuperSecretPassword123!",
        "workspace_name": "Req64 Org",
    }
    resp = auth_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers={"X-Request-ID": req_id_64},
    )
    assert resp.status_code == 201
    audit_row = db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.register"))
    assert audit_row is not None
    assert audit_row.request_id == req_id_64


def test_login_with_37_char_request_id(auth_client: TestClient, db_session: Session) -> None:
    """Verify login with 37-character valid X-Request-ID stores the full ID."""
    _create_workspace_and_user(db_session, email="req37@example.com")
    req_id_37 = "X" * 36 + "1"
    assert len(req_id_37) == 37
    payload = {
        "email": "req37@example.com",
        "password": "SuperSecretPassword123!",
    }
    resp = auth_client.post(
        "/api/v1/auth/login",
        json=payload,
        headers={"X-Request-ID": req_id_37},
    )
    assert resp.status_code == 200
    audit_row = db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.login"))
    assert audit_row is not None
    assert audit_row.request_id == req_id_37
