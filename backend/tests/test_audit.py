"""Integration tests for audit service, validation defense-in-depth, and audit log endpoints."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
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
    res_id = str(uuid.uuid4())

    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="user.update",
        target_type="user",
        actor_user_id=user.id,
        actor_type="user",
        target_id=res_id,
        details={"updated_field": "timezone"},
    )
    assert entry.id is not None

    db_entry = db_session.scalar(select(AuditLog).where(AuditLog.id == entry.id))
    assert db_entry is not None
    assert db_entry.workspace_id == workspace.id
    assert db_entry.actor_user_id == user.id
    assert db_entry.actor_type == "user"
    assert db_entry.action == "user.update"
    assert db_entry.target_type == "user"
    assert db_entry.target_id == res_id
    assert db_entry.details == {"updated_field": "timezone"}


def test_audit_record_forbidden_keys(db_session: Session) -> None:
    """Verify defense-in-depth guard rejects audit details containing sensitive credential keys."""
    workspace, _ = _create_workspace_and_user(db_session, email="forbidden_keys@example.com")

    forbidden_payloads = [
        {"user_password": "plain_password"},
        {"nested": {"auth_token": "token_string"}},
        {"level1": {"level2": {"deep_secret": "value"}}},
        {"list_payload": [{"item_cookie": "cookie_data"}]},
        {"nested_list": {"items": [{"inner_hash": "hash_val"}]}},
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
                target_type="test",
                details=payload,
            )


def test_audit_record_allowed_keys(db_session: Session) -> None:
    """Verify allowed keys like changes, role, from, to, is_active, sessions_revoked pass."""
    workspace, _ = _create_workspace_and_user(db_session, email="allowed_keys@example.com")
    allowed_details = {
        "changes": {
            "role": {"from": "viewer", "to": "admin"},
            "is_active": {"from": True, "to": False},
        },
        "sessions_revoked": 3,
    }
    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="test.allowed",
        target_type="test",
        details=allowed_details,
    )
    assert entry.id is not None
    assert entry.details == allowed_details


def test_audit_participates_in_transaction_rollback(db_session: Session) -> None:
    """Verify audit log row is rolled back when participating in a failed transaction."""
    workspace, _ = _create_workspace_and_user(db_session, email="rollback_audit@example.com")

    # Start nested savepoint
    savepoint = db_session.begin_nested()
    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="transaction.fail",
        target_type="test",
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
        target_type="alpha",
        actor_user_id=admin_a.id,
    )

    # Record events in Workspace B
    audit_service.record(
        db_session,
        workspace_id=ws_b.id,
        action="beta.action",
        target_type="beta",
        actor_user_id=admin_b.id,
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
        db_session, workspace_id=workspace.id, action="auth.login", target_type="user"
    )
    audit_service.record(
        db_session, workspace_id=workspace.id, action="auth.logout", target_type="user"
    )
    audit_service.record(
        db_session, workspace_id=workspace.id, action="auth.refresh", target_type="user"
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
            target_type="step",
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


def test_audit_log_order_newest_first(auth_client: TestClient, db_session: Session) -> None:
    """Verify audit log endpoint returns entries ordered newest first (created_at DESC, id DESC)."""
    workspace, admin = _create_workspace_and_user(db_session, email="newest_first@example.com")

    for i in range(3):
        audit_service.record(
            db_session,
            workspace_id=workspace.id,
            action=f"order.step.{i}",
            target_type="step",
        )

    token, _ = create_access_token(admin.id)
    resp = auth_client.get(
        "/api/v1/audit-logs?limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    actions = [item["action"] for item in items]
    assert actions[:3] == ["order.step.2", "order.step.1", "order.step.0"]


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


def test_audit_logs_bigint_identity_increments(db_session: Session) -> None:
    """Verify audit_logs id column is a BigInteger Identity that increments monotonically."""
    workspace, _ = _create_workspace_and_user(db_session, email="identity_test@example.com")

    e1 = audit_service.record(
        db_session, workspace_id=workspace.id, action="test.step1", target_type="test"
    )
    e2 = audit_service.record(
        db_session, workspace_id=workspace.id, action="test.step2", target_type="test"
    )
    assert isinstance(e1.id, int)
    assert isinstance(e2.id, int)
    assert e2.id > e1.id


def test_audit_logs_actor_type_constraint(db_session: Session) -> None:
    """Verify actor_type check constraint accepts valid values and rejects invalid values."""
    workspace, _ = _create_workspace_and_user(db_session, email="actortype_test@example.com")

    # Valid actor types
    for valid_type in ("user", "api_key", "system"):
        entry = audit_service.record(
            db_session,
            workspace_id=workspace.id,
            action=f"test.{valid_type}",
            actor_type=valid_type,
            target_type="test",
        )
        assert entry.actor_type == valid_type

    # Invalid actor type rejected by check constraint
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            audit_service.record(
                db_session,
                workspace_id=workspace.id,
                action="test.invalid",
                actor_type="robot",
                target_type="test",
            )


def test_audit_logs_details_not_null_and_default(db_session: Session) -> None:
    """Verify details is NOT NULL and defaults to an empty JSON object."""
    workspace, _ = _create_workspace_and_user(db_session, email="details_test@example.com")

    # Service call with details=None defaults to {}
    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="test.default_details",
        target_type="test",
        details=None,
    )
    assert entry.details == {}

    # Raw SQL inserting NULL for details raises IntegrityError
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    INSERT INTO audit_logs (workspace_id, actor_type, action, details)
                    VALUES (:ws, 'system', 'test.null_details', NULL)
                    """
                ),
                {"ws": workspace.id},
            )


def test_audit_logs_workspace_fk_restrict(db_session: Session) -> None:
    """Verify foreign key on workspace_id is ON DELETE RESTRICT (audit logs cannot be orphaned)."""
    workspace, _ = _create_workspace_and_user(db_session, email="fk_restrict@example.com")
    audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="workspace.created",
        target_type="workspace",
        target_id=str(workspace.id),
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.delete(workspace)
            db_session.flush()


def test_audit_logs_actor_user_fk_set_null(db_session: Session) -> None:
    """Verify foreign key on actor_user_id is ON DELETE SET NULL when user is deleted."""
    workspace, user = _create_workspace_and_user(db_session, email="fk_setnull@example.com")
    entry = audit_service.record(
        db_session,
        workspace_id=workspace.id,
        action="user.action",
        actor_type="user",
        actor_user_id=user.id,
        target_type="user",
    )
    assert entry.actor_user_id == user.id

    db_session.delete(user)
    db_session.flush()

    db_session.refresh(entry)
    assert entry.actor_user_id is None


def test_audit_logs_schema_inspector(db_session: Session) -> None:
    """Verify audit_logs table schema matches target specification via SQLAlchemy inspector."""
    inspector = inspect(db_session.bind)
    columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    expected_columns = {
        "id",
        "workspace_id",
        "actor_type",
        "actor_user_id",
        "action",
        "target_type",
        "target_id",
        "request_id",
        "details",
        "created_at",
    }
    assert columns == expected_columns
    assert "ip_address" not in columns
    assert "user_agent" not in columns
    assert "actor_id" not in columns
    assert "resource_type" not in columns
    assert "resource_id" not in columns

    indexes = {idx["name"] for idx in inspector.get_indexes("audit_logs")}
    assert "ix_audit_logs_workspace_id_created_at" in indexes
    assert "ix_audit_logs_workspace_id_action" in indexes
    assert "ix_audit_logs_workspace_id" not in indexes
    assert "ix_audit_logs_created_at" not in indexes
