"""Tests verifying Workspace and User models, constraints, and relationships."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import Role, User
from app.modules.workspaces.models import Workspace


def test_insert_workspace_and_user_success(db_session: Session) -> None:
    """Verify successfully inserting a workspace and associated user."""
    workspace = Workspace(
        name="Acme Corp",
        slug="acme-corp",
        retention_days=45,
        timezone="America/New_York",
        monthly_budget_usd=Decimal("500.00"),
    )
    db_session.add(workspace)
    db_session.flush()

    user = User(
        workspace_id=workspace.id,
        email="operator@acme.com",
        password_hash="argon2id$hashedpassword",
        role=Role.ADMIN,
    )
    db_session.add(user)
    db_session.flush()

    assert workspace.id is not None
    assert isinstance(workspace.id, uuid.UUID)
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.workspace_id == workspace.id
    assert user.is_active is True
    assert user.role == "admin"
    assert workspace.created_at is not None
    assert user.created_at is not None


def test_duplicate_workspace_slug_rejected(db_session: Session) -> None:
    """Verify duplicate workspace slugs trigger a unique constraint violation."""
    w1 = Workspace(name="Workspace One", slug="shared-slug")
    db_session.add(w1)
    db_session.flush()

    w2 = Workspace(name="Workspace Two", slug="shared-slug")
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(w2)
        db_session.flush()


def test_duplicate_email_rejected(db_session: Session) -> None:
    """Verify duplicate user emails trigger a unique constraint violation."""
    ws = Workspace(name="Email Test WS", slug="email-test-ws")
    db_session.add(ws)
    db_session.flush()

    u1 = User(
        workspace_id=ws.id,
        email="developer@test.com",
        password_hash="hash1",
        role=Role.ADMIN,
    )
    db_session.add(u1)
    db_session.flush()

    u2 = User(
        workspace_id=ws.id,
        email="developer@test.com",
        password_hash="hash2",
        role=Role.VIEWER,
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(u2)
        db_session.flush()


def test_uppercase_email_rejected_by_check(db_session: Session) -> None:
    """Verify emails with uppercase letters violate the email_lowercase CHECK constraint."""
    ws = Workspace(name="Case WS", slug="case-ws")
    db_session.add(ws)
    db_session.flush()

    user = User(
        workspace_id=ws.id,
        email="UpperCase@Test.com",
        password_hash="hash",
        role=Role.ADMIN,
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(user)
        db_session.flush()


def test_invalid_role_rejected(db_session: Session) -> None:
    """Verify roles outside ('admin', 'viewer') violate the role_valid CHECK constraint."""
    ws = Workspace(name="Role WS", slug="role-ws")
    db_session.add(ws)
    db_session.flush()

    user = User(
        workspace_id=ws.id,
        email="role@test.com",
        password_hash="hash",
        role="superuser",
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(user)
        db_session.flush()


def test_negative_retention_days_rejected(db_session: Session) -> None:
    """Verify retention_days <= 0 violates retention_days_positive CHECK constraint."""
    ws = Workspace(name="Retention WS", slug="retention-ws", retention_days=0)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(ws)
        db_session.flush()


def test_negative_monthly_budget_rejected(db_session: Session) -> None:
    """Verify negative budget violates monthly_budget_non_negative CHECK constraint."""
    ws = Workspace(
        name="Budget WS",
        slug="budget-ws",
        monthly_budget_usd=Decimal("-10.00"),
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(ws)
        db_session.flush()


def test_user_with_nonexistent_workspace_rejected(db_session: Session) -> None:
    """Verify foreign key constraint rejects non-existent workspace_id."""
    user = User(
        workspace_id=uuid.uuid4(),
        email="orphan@test.com",
        password_hash="hash",
        role=Role.VIEWER,
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(user)
        db_session.flush()


def test_delete_workspace_with_users_rejected_restrict(db_session: Session) -> None:
    """Verify deleting a workspace with users is rejected by ON DELETE RESTRICT."""
    ws = Workspace(name="Parent WS", slug="parent-ws")
    db_session.add(ws)
    db_session.flush()

    user = User(
        workspace_id=ws.id,
        email="child@test.com",
        password_hash="hash",
        role=Role.ADMIN,
    )
    db_session.add(user)
    db_session.flush()

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(ws)
        db_session.flush()


def test_model_defaults_applied(db_session: Session) -> None:
    """Verify server and model defaults are correctly applied."""
    ws = Workspace(name="Default WS", slug="default-ws")
    db_session.add(ws)
    db_session.flush()

    user = User(
        workspace_id=ws.id,
        email="default@test.com",
        password_hash="hash",
        role=Role.VIEWER,
    )
    db_session.add(user)
    db_session.flush()

    # Query back to ensure server defaults populated
    persisted_ws = db_session.scalar(select(Workspace).where(Workspace.id == ws.id))
    persisted_user = db_session.scalar(select(User).where(User.id == user.id))

    assert persisted_ws is not None
    assert persisted_ws.retention_days == 30
    assert persisted_ws.timezone == "UTC"
    assert persisted_ws.created_at is not None
    assert persisted_ws.updated_at is not None

    assert persisted_user is not None
    assert persisted_user.is_active is True
    assert persisted_user.role == "viewer"
    assert persisted_user.created_at is not None
    assert persisted_user.updated_at is not None
    assert persisted_user.last_login_at is None
