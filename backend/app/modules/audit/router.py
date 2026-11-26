"""Audit log endpoints for administrative visibility into workspace activity."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.schemas import AuditLogRead
from app.modules.auth.dependencies import AdminUser

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=list[AuditLogRead],
    summary="List workspace audit logs with optional action filtering",
)
def list_audit_logs(
    current_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, max_length=64),
) -> list[AuditLog]:
    """Retrieve audit logs strictly scoped to the administrator's workspace."""
    repo = AuditLogRepository(db, current_user.workspace_id)
    return list(repo.list(limit=limit, offset=offset, action=action))
