"""Audit log recording service with validation and structured logging."""

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session
from structlog.contextvars import get_contextvars

from app.modules.audit.models import AuditLog

logger = structlog.get_logger()

_FORBIDDEN_KEY_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "cookie",
    "authorization",
    "hash",
)


def _validate_details(details: dict[str, Any] | None) -> None:
    """Recursively validate details dictionary against forbidden security-sensitive keys."""
    if not details:
        return
    for key, value in details.items():
        lowered_key = str(key).lower()
        for forbidden in _FORBIDDEN_KEY_SUBSTRINGS:
            if forbidden in lowered_key:
                raise ValueError(f"Audit log details contain forbidden security key: {key}")
        if isinstance(value, dict):
            _validate_details(value)


def record(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    action: str,
    actor_type: str = "user",
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an audit event participating in the caller's database transaction.

    Enforces forbidden key defense-in-depth on details, extracts request_id from structlog,
    defensively truncates to 64 characters, flushes without committing, and emits a structured log.
    """
    _validate_details(details)

    sanitized_details = details if details is not None else {}
    request_id = get_contextvars().get("request_id")
    request_id_str = str(request_id)[:64] if request_id is not None else None

    entry = AuditLog(
        workspace_id=workspace_id,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=sanitized_details,
        request_id=request_id_str,
    )
    db.add(entry)
    db.flush()

    logger.info(
        "audit.recorded",
        action=action,
        workspace_id=str(workspace_id),
        actor_type=actor_type,
        target_type=target_type,
    )
    return entry
