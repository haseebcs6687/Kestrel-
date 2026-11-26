"""Audit log entity model for tracking operational and security actions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDPrimaryKeyMixin
from app.modules.workspaces.models import Workspace

if TYPE_CHECKING:
    from app.modules.auth.models import User


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """Immutable operational and security audit log (ADR-025)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="actor_type_valid",
        ),
        Index("ix_audit_logs_workspace_id", "workspace_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_workspace_id_created_at", "workspace_id", text("created_at DESC")),
        Index("ix_audit_logs_workspace_id_action", "workspace_id", "action"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship()
    actor: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[actor_id],
        lazy="selectin",
    )
