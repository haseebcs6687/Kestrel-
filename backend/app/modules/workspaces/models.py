"""Workspace domain entity model."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-tenant workspace boundary container."""

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("retention_days > 0", name="retention_days_positive"),
        CheckConstraint("monthly_budget_usd >= 0", name="monthly_budget_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    retention_days: Mapped[int] = mapped_column(
        nullable=False,
        server_default=text("30"),
        default=30,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'UTC'"),
        default="UTC",
    )
    monthly_budget_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
