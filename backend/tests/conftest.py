"""Shared test fixtures and database configuration."""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import reset_db_connections
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DB_NAME = "kestrel_test"


@pytest.fixture
def client() -> Generator[TestClient]:
    """Provide a clean FastAPI TestClient for each test."""
    get_settings.cache_clear()
    reset_db_connections()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    reset_db_connections()


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine]:
    """Session-scoped fixture preparing kestrel_test database via Alembic migrations."""
    # Hard safety guard: ensure target database name ends with '_test'
    if not TEST_DB_NAME.endswith("_test"):
        raise RuntimeError(
            f"Safety guard violation: target test database '{TEST_DB_NAME}' must end with '_test'"
        )

    base_settings = get_settings()

    # 1. Connect to postgres maintenance DB and ensure kestrel_test exists
    maint_url = base_settings.get_database_url().set(database="postgres")
    maint_engine = create_engine(maint_url, isolation_level="AUTOCOMMIT")
    with maint_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": TEST_DB_NAME},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    maint_engine.dispose()

    # 2. Run Alembic migrations programmatically against kestrel_test
    test_db_url = base_settings.get_database_url().set(database=TEST_DB_NAME)
    alembic_ini_path = REPO_ROOT / "backend" / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    alembic_cfg.attributes["sqlalchemy_url"] = test_db_url

    command.upgrade(alembic_cfg, "head")

    # 3. Create engine for tests
    engine = create_engine(test_db_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session]:
    """Function-scoped fixture providing a transactional session rolled back after every test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
