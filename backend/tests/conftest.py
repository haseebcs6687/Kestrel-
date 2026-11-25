"""Shared test fixtures and configuration."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import reset_db_connections
from app.main import create_app


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
