"""Tests verifying multi-tenant isolation and workspace-scoped repository queries (ADR-022)."""

from sqlalchemy.orm import Session

from app.modules.auth.models import Role, User
from app.modules.auth.repository import (
    UserRepository,
    get_user_by_email,
    get_user_by_id,
)
from app.modules.workspaces.models import Workspace


def test_workspace_scoped_repository_isolates_users(db_session: Session) -> None:
    """Verify UserRepository strictly partitions queries across workspace boundaries."""
    # 1. Create Workspace A and User A
    ws_a = Workspace(name="Acme Corp", slug="acme-corp-123456")
    db_session.add(ws_a)
    db_session.flush()

    user_a = User(
        workspace_id=ws_a.id,
        email="alice@acme.com",
        password_hash="hash_a",
        role=Role.ADMIN.value,
    )
    db_session.add(user_a)

    # 2. Create Workspace B and User B
    ws_b = Workspace(name="Beta Labs", slug="beta-labs-654321")
    db_session.add(ws_b)
    db_session.flush()

    user_b = User(
        workspace_id=ws_b.id,
        email="bob@beta.com",
        password_hash="hash_b",
        role=Role.VIEWER.value,
    )
    db_session.add(user_b)
    db_session.flush()

    # 3. Test Repository bound to Workspace A
    repo_a = UserRepository(session=db_session, workspace_id=ws_a.id)
    users_a = repo_a.list_users()

    assert len(users_a) == 1
    assert users_a[0].id == user_a.id
    assert users_a[0].email == "alice@acme.com"
    assert repo_a.get(user_a.id) is not None
    # Cross-tenant read attempt must return None
    assert repo_a.get(user_b.id) is None

    # 4. Test Repository bound to Workspace B
    repo_b = UserRepository(session=db_session, workspace_id=ws_b.id)
    users_b = repo_b.list_users()

    assert len(users_b) == 1
    assert users_b[0].id == user_b.id
    assert users_b[0].email == "bob@beta.com"
    assert repo_b.get(user_b.id) is not None
    # Cross-tenant read attempt must return None
    assert repo_b.get(user_a.id) is None


def test_unscoped_lookups_resolve_across_workspaces(db_session: Session) -> None:
    """Verify unscoped lookups resolve user by email and ID for login/token auth."""
    ws = Workspace(name="Test Org", slug="test-org-999")
    db_session.add(ws)
    db_session.flush()

    user = User(
        workspace_id=ws.id,
        email="unscoped@test.com",
        password_hash="test_hash",
        role=Role.ADMIN.value,
    )
    db_session.add(user)
    db_session.flush()

    assert get_user_by_email(db_session, "unscoped@test.com") is not None
    assert get_user_by_email(db_session, "missing@test.com") is None
    assert get_user_by_id(db_session, user.id) is not None
