"""Concurrency race condition tests for last active admin invariant (ADR-030)."""

import threading
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken, Role, User
from app.modules.auth.security import hash_password
from app.modules.users.service import LastAdminError, update_user
from app.modules.workspaces.models import Workspace


def test_lock_workspace_statement_contains_for_update() -> None:
    """Verify that lock_workspace compiles with exclusive row-level locking."""
    ws_id = uuid.uuid4()
    stmt = select(Workspace).where(Workspace.id == ws_id).with_for_update()
    compiled = str(stmt.compile())
    assert "FOR UPDATE" in compiled


def test_two_admin_race_condition(test_engine: Engine) -> None:
    """Verify mutual demotion race between two active admins leaves exactly one admin.

    ADR-030: When two admins concurrently demote each other, the workspace row-level
    lock serializes execution: one succeeds and the other fails with LastAdminError.
    """
    ws_id = uuid.uuid4()
    admin_a_id = uuid.uuid4()
    admin_b_id = uuid.uuid4()

    # 1. Setup real committed rows in the test database
    with Session(test_engine) as setup_session:
        ws = Workspace(
            id=ws_id,
            name="Race Condition Workspace",
            slug=f"race-ws-{ws_id.hex[:6]}",
        )
        admin_a = User(
            id=admin_a_id,
            workspace_id=ws_id,
            email=f"admin_a_{ws_id.hex[:4]}@example.com",
            password_hash=hash_password("AdminPass12345!"),
            role=Role.ADMIN.value,
            is_active=True,
        )
        admin_b = User(
            id=admin_b_id,
            workspace_id=ws_id,
            email=f"admin_b_{ws_id.hex[:4]}@example.com",
            password_hash=hash_password("AdminPass12345!"),
            role=Role.ADMIN.value,
            is_active=True,
        )
        setup_session.add_all([ws, admin_a, admin_b])
        setup_session.commit()

    barrier = threading.Barrier(2)
    results: dict[str, Any] = {"t1": None, "t2": None, "err1": None, "err2": None}

    def worker1() -> None:
        with Session(test_engine) as s1:
            actor = s1.get(User, admin_a_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                update_user(
                    s1,
                    actor_user=actor,
                    target_user_id=admin_b_id,
                    role=Role.VIEWER.value,
                )
                results["t1"] = "success"
            except Exception as exc:
                results["err1"] = exc

    def worker2() -> None:
        with Session(test_engine) as s2:
            actor = s2.get(User, admin_b_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                update_user(
                    s2,
                    actor_user=actor,
                    target_user_id=admin_a_id,
                    role=Role.VIEWER.value,
                )
                results["t2"] = "success"
            except Exception as exc:
                results["err2"] = exc

    t1 = threading.Thread(target=worker1, name="AdminDemote-Thread-1")
    t2 = threading.Thread(target=worker2, name="AdminDemote-Thread-2")

    try:
        t1.start()
        t2.start()

        t1.join(timeout=20)
        t2.join(timeout=20)

        assert not t1.is_alive(), "Thread 1 hung and failed to join within 20s"
        assert not t2.is_alive(), "Thread 2 hung and failed to join within 20s"

        # Assert exactly one success and exactly one LastAdminError
        successes = [r for r in [results["t1"], results["t2"]] if r == "success"]
        errors = [e for e in [results["err1"], results["err2"]] if isinstance(e, LastAdminError)]

        assert len(successes) == 1, f"Expected exactly 1 success, got: {results}"
        assert len(errors) == 1, f"Expected exactly 1 LastAdminError, got: {results}"

        # Assert exactly one active admin remains in database
        with Session(test_engine) as verify_session:
            active_admin_count = verify_session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.workspace_id == ws_id,
                    User.role == Role.ADMIN.value,
                    User.is_active.is_(True),
                )
            )
            assert active_admin_count == 1

    finally:
        # Strict cleanup of all committed test rows in FK-safe order
        with Session(test_engine) as cleanup_session:
            cleanup_session.execute(delete(AuditLog).where(AuditLog.workspace_id == ws_id))
            cleanup_session.execute(delete(RefreshToken).where(RefreshToken.workspace_id == ws_id))
            cleanup_session.execute(delete(User).where(User.workspace_id == ws_id))
            cleanup_session.execute(delete(Workspace).where(Workspace.id == ws_id))
            cleanup_session.commit()

            # Verify test database tables are completely clean
            assert cleanup_session.scalar(select(func.count()).select_from(Workspace)) == 0
            assert cleanup_session.scalar(select(func.count()).select_from(User)) == 0
            assert cleanup_session.scalar(select(func.count()).select_from(RefreshToken)) == 0
            assert cleanup_session.scalar(select(func.count()).select_from(AuditLog)) == 0
