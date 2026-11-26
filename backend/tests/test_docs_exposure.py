"""Tests verifying API documentation endpoint exposure according to APP_ENV."""

import os
from collections.abc import Generator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def clean_env() -> Generator[None]:
    """Ensure environment and settings cache are restored after each test."""
    original_env = os.environ.get("APP_ENV")
    get_settings.cache_clear()
    yield
    if original_env is not None:
        os.environ["APP_ENV"] = original_env
    else:
        os.environ.pop("APP_ENV", None)
    get_settings.cache_clear()


def test_docs_hidden_in_prod() -> None:
    """Verify /docs, /redoc, and /openapi.json return 404 in prod while /health returns 200."""
    os.environ["APP_ENV"] = "prod"
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        assert client.get("/health").status_code == status.HTTP_200_OK
        assert client.get("/docs").status_code == status.HTTP_404_NOT_FOUND
        assert client.get("/redoc").status_code == status.HTTP_404_NOT_FOUND
        assert client.get("/openapi.json").status_code == status.HTTP_404_NOT_FOUND


def test_docs_exposed_in_dev() -> None:
    """Verify /docs returns 200 in dev."""
    os.environ["APP_ENV"] = "dev"
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        assert client.get("/docs").status_code == status.HTTP_200_OK
        assert client.get("/openapi.json").status_code == status.HTTP_200_OK
