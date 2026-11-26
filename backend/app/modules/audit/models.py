"""Audit log entity model for tracking operational and security actions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Identity

from app.core.base import Base
from app.modules.workspaces.models import Workspace

if TYPE_CHECKING:
    from app.modules.auth.models import User


class AuditLog(Base):
    """Immutable operational and security audit log (ADR-025, ADR-027)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'api_key', 'system')",
            name="actor_type_valid",
        ),
        Index("ix_audit_logs_workspace_id_created_at", "workspace_id", text("created_at DESC")),
        Index("ix_audit_logs_workspace_id_action", "workspace_id", "action"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship()
    actor: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[actor_user_id],
        lazy="selectin",
    )
