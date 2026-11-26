"""Tests for Alembic migration lifecycle and schema drift detection."""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
THROWAWAY_DB = "kestrel_migration_test"


@pytest.fixture(scope="module")
def throwaway_db() -> Generator[Engine]:
    """Create a temporary database for testing migrations and guarantee cleanup."""
    if not THROWAWAY_DB.endswith("_test"):
        raise RuntimeError(
            f"Safety guard violation: throwaway test database '{THROWAWAY_DB}' "
            "must end with '_test'"
        )

    base_settings = get_settings()
    maint_url = base_settings.get_database_url().set(database="postgres")
    maint_engine = create_engine(maint_url, isolation_level="AUTOCOMMIT")

    # Drop existing if left behind, then create fresh
    with maint_engine.connect() as conn:
        conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :dbname AND pid <> pg_backend_pid();
                """
            ),
            {"dbname": THROWAWAY_DB},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{THROWAWAY_DB}"'))
        conn.execute(text(f'CREATE DATABASE "{THROWAWAY_DB}"'))

    throwaway_url = base_settings.get_database_url().set(database=THROWAWAY_DB)
    engine = create_engine(throwaway_url, pool_pre_ping=True)

    try:
        yield engine
    finally:
        engine.dispose()
        with maint_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :dbname AND pid <> pg_backend_pid();
                    """
                ),
                {"dbname": THROWAWAY_DB},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{THROWAWAY_DB}"'))
        maint_engine.dispose()


def test_migration_lifecycle_upgrade_downgrade_upgrade(throwaway_db: Engine) -> None:
    """Verify upgrade head -> downgrade base -> upgrade head lifecycle."""
    alembic_ini_path = REPO_ROOT / "backend" / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    alembic_cfg.attributes["sqlalchemy_url"] = throwaway_db.url

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(throwaway_db)
    tables = inspector.get_table_names()
    assert "workspaces" in tables
    assert "users" in tables
    assert "refresh_tokens" in tables
    assert "audit_logs" in tables
    assert "alembic_version" in tables

    # Verify index on users, refresh_tokens, and audit_logs
    indexes_users = [idx["name"] for idx in inspector.get_indexes("users")]
    assert "ix_users_workspace_id" in indexes_users

    indexes_refresh = [idx["name"] for idx in inspector.get_indexes("refresh_tokens")]
    assert "ix_refresh_tokens_family_id" in indexes_refresh
    assert "ix_refresh_tokens_token_hash" in indexes_refresh

    indexes_audit = [idx["name"] for idx in inspector.get_indexes("audit_logs")]
    assert "ix_audit_logs_workspace_id_created_at" in indexes_audit

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(throwaway_db)
    remaining_tables = inspector.get_table_names()
    assert "workspaces" not in remaining_tables
    assert "users" not in remaining_tables
    assert "refresh_tokens" not in remaining_tables
    assert "audit_logs" not in remaining_tables
    assert remaining_tables == ["alembic_version"]

    # 3. Upgrade to head again
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(throwaway_db)
    recreated_tables = inspector.get_table_names()
    assert "workspaces" in recreated_tables
    assert "users" in recreated_tables
    assert "refresh_tokens" in recreated_tables
    assert "audit_logs" in recreated_tables


def test_migration_0002_step_downgrade_and_reupgrade(throwaway_db: Engine) -> None:
    """Verify migration 0002 applies, downgrades to 0001, and re-applies cleanly."""
    alembic_ini_path = REPO_ROOT / "backend" / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    alembic_cfg.attributes["sqlalchemy_url"] = throwaway_db.url

    # 1. Start from 0002 (head)
    command.upgrade(alembic_cfg, "0002")
    inspector = inspect(throwaway_db)
    tables = inspector.get_table_names()
    assert "refresh_tokens" in tables
    assert "audit_logs" in tables
    assert "workspaces" in tables
    assert "users" in tables

    # 2. Downgrade one step to 0001
    command.downgrade(alembic_cfg, "0001")
    inspector = inspect(throwaway_db)
    tables_step = inspector.get_table_names()
    assert "refresh_tokens" not in tables_step
    assert "audit_logs" not in tables_step
    assert "workspaces" in tables_step
    assert "users" in tables_step

    # 3. Re-upgrade to 0002
    command.upgrade(alembic_cfg, "0002")
    inspector = inspect(throwaway_db)
    tables_reup = inspector.get_table_names()
    assert "refresh_tokens" in tables_reup
    assert "audit_logs" in tables_reup


def test_alembic_check_no_schema_drift(throwaway_db: Engine) -> None:
    """Verify alembic check detects no drift between SQLAlchemy models and migrations."""
    alembic_ini_path = REPO_ROOT / "backend" / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    alembic_cfg.attributes["sqlalchemy_url"] = throwaway_db.url

    # Ensures throwaway DB is at head
    command.upgrade(alembic_cfg, "head")

    # command.check raises CommandError if drift is detected
    command.check(alembic_cfg)


def test_migration_0003_upgrade_downgrade_and_abort_with_rows(throwaway_db: Engine) -> None:
    """Verify migration 0003 aborts when audit_logs has rows, and downgrades/reupgrades cleanly."""
    alembic_ini_path = REPO_ROOT / "backend" / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    alembic_cfg.attributes["sqlalchemy_url"] = throwaway_db.url

    # 1. Start from 0002
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "0002")

    # 2. Insert dummy workspace and dummy audit_log row into 0002 schema
    with throwaway_db.connect() as conn:
        ws_id = uuid.uuid4()
        conn.execute(
            text(
                """
                INSERT INTO workspaces (id, name, slug)
                VALUES (:id, 'Test WS', 'test-ws-abort');
                """
            ),
            {"id": ws_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO audit_logs (id, workspace_id, actor_type, action, resource_type)
                VALUES (gen_random_uuid(), :ws, 'system', 'test.abort', 'test');
                """
            ),
            {"ws": ws_id},
        )
        conn.commit()

    # 3. Attempt upgrade to 0003 -> MUST raise RuntimeError (data loss protection)
    with pytest.raises(RuntimeError, match="Cannot rebuild audit_logs: table contains 1 row"):
        command.upgrade(alembic_cfg, "0003")

    # 4. Clean out audit_logs and workspaces
    with throwaway_db.connect() as conn:
        conn.execute(text("DELETE FROM audit_logs;"))
        conn.execute(text("DELETE FROM workspaces;"))
        conn.commit()

    # 5. Now upgrade to 0003 -> MUST succeed
    command.upgrade(alembic_cfg, "0003")

    # 6. Verify 0003 target schema columns
    inspector = inspect(throwaway_db)
    columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    expected = {
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
    assert columns == expected
    assert "ip_address" not in columns
    assert "user_agent" not in columns

    # 7. Downgrade to 0002
    command.downgrade(alembic_cfg, "0002")
    inspector_0002 = inspect(throwaway_db)
    cols_0002 = {col["name"] for col in inspector_0002.get_columns("audit_logs")}
    assert "actor_id" in cols_0002
    assert "ip_address" in cols_0002

    # 8. Downgrade to base, then re-upgrade to head
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
