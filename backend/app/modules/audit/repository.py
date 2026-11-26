"""Audit log data access repository implementing workspace-scoped queries."""

from collections.abc import Sequence

from sqlalchemy import select

from app.core.tenancy import WorkspaceScopedRepository
from app.modules.audit.models import AuditLog


class AuditLogRepository(WorkspaceScopedRepository):
    """Tenant-scoped repository for querying audit logs within a workspace (ADR-022)."""

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
    ) -> Sequence[AuditLog]:
        """Fetch audit logs scoped to the current workspace ordered newest first."""
        stmt = self.scope(select(AuditLog), AuditLog)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        stmt = stmt.limit(limit).offset(offset)
        return self.session.scalars(stmt).all()
