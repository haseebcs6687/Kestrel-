"""Platform routing definitions for liveness and readiness probes."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.platform.schemas import HealthResponse, ReadyChecks, ReadyResponse

router = APIRouter(tags=["platform"])
logger = structlog.get_logger("kestrel.platform")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe indicating application process is running."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
def health_ready(db: Annotated[Session, Depends(get_db)]) -> ReadyResponse | JSONResponse:
    """Readiness probe verifying operational connectivity to backing datastores."""
    try:
        db.execute(text("SELECT 1"))
        return ReadyResponse(status="ready", checks=ReadyChecks(database="ok"))
    except Exception as exc:
        logger.warning(
            "database_readiness_check_failed",
            error_class=exc.__class__.__name__,
            message="Database connectivity check failed",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "checks": {"database": "fail"}},
        )
