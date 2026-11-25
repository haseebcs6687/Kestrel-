"""Pydantic schemas for platform and health endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    status: str


class ReadyChecks(BaseModel):
    """Component health check statuses."""

    database: str


class ReadyResponse(BaseModel):
    """Readiness probe response model."""

    status: str
    checks: ReadyChecks
