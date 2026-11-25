"""Tests for request-ID middleware behavior."""

from fastapi import status
from fastapi.testclient import TestClient


def test_valid_request_id_echoed(client: TestClient) -> None:
    """Verify valid incoming X-Request-ID is preserved and echoed in response."""
    custom_id = "custom-req-id_123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Request-ID"] == custom_id


def test_invalid_request_id_replaced_when_illegal_chars(client: TestClient) -> None:
    """Verify invalid incoming X-Request-ID with illegal characters is replaced by uuid4."""
    invalid_id = "invalid id with spaces!@#"
    response = client.get("/health", headers={"X-Request-ID": invalid_id})
    assert response.status_code == status.HTTP_200_OK
    assigned_id = response.headers["X-Request-ID"]
    assert assigned_id != invalid_id
    assert len(assigned_id) == 32


def test_invalid_request_id_replaced_when_too_long(client: TestClient) -> None:
    """Verify incoming X-Request-ID exceeding 64 characters is replaced by uuid4."""
    too_long_id = "a" * 65
    response = client.get("/health", headers={"X-Request-ID": too_long_id})
    assert response.status_code == status.HTTP_200_OK
    assigned_id = response.headers["X-Request-ID"]
    assert assigned_id != too_long_id
    assert len(assigned_id) == 32


def test_distinct_request_ids_generated(client: TestClient) -> None:
    """Verify two sequential requests without header receive distinct request IDs."""
    resp1 = client.get("/health")
    resp2 = client.get("/health")
    id1 = resp1.headers["X-Request-ID"]
    id2 = resp2.headers["X-Request-ID"]
    assert id1 != id2
