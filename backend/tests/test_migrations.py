"""Tests for Alembic migration lifecycle and schema drift detection."""

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
    assert "alembic_version" in tables

    # Verify index on users
    indexes = [idx["name"] for idx in inspector.get_indexes("users")]
    assert "ix_users_workspace_id" in indexes

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(throwaway_db)
    remaining_tables = inspector.get_table_names()
    assert "workspaces" not in remaining_tables
    assert "users" not in remaining_tables
    assert remaining_tables == ["alembic_version"]

    # 3. Upgrade to head again
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(throwaway_db)
    recreated_tables = inspector.get_table_names()
    assert "workspaces" in recreated_tables
    assert "users" in recreated_tables


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
