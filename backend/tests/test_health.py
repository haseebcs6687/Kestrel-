"""Tests for liveness and readiness endpoints."""

from collections.abc import Generator

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_db


def test_liveness_endpoint(client: TestClient) -> None:
    """Verify /health returns 200 ok and includes X-Request-ID header."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_readiness_endpoint_real_database(client: TestClient) -> None:
    """Verify /health/ready returns 200 ready against the real running PostgreSQL container."""
    response = client.get("/health/ready")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}
    assert "X-Request-ID" in response.headers


def test_readiness_endpoint_unreachable_database(client: TestClient) -> None:
    """Verify /health/ready returns 503 without leaking host, port, or secret when DB fails."""
    unreachable_engine = create_engine(
        "postgresql+psycopg://kestrel:change_me@127.0.0.1:1/kestrel",
        connect_args={"connect_timeout": 1},
    )
    unreachable_session_factory = sessionmaker(
        bind=unreachable_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db() -> Generator[Session]:
        session = unreachable_session_factory()
        try:
            yield session
        finally:
            session.close()

    client.app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health/ready")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable", "checks": {"database": "fail"}}
    response_text = response.text
    assert "127.0.0.1" not in response_text
    assert ":1" not in response_text
    assert "change_me" not in response_text
    assert "Exception" not in response_text
    unreachable_engine.dispose()
