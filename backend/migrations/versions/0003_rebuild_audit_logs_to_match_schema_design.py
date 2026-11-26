"""rebuild audit_logs to match schema design

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26 15:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Safe rebuild guard: abort if existing audit records exist to prevent data loss
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT count(*) FROM audit_logs")).scalar()
    if count is not None and count > 0:
        raise RuntimeError(
            f"Cannot rebuild audit_logs: table contains {count} row(s). Data loss prevented."
        )

    # 1. Drop existing 0002 audit_logs table and indexes
    op.drop_index("ix_audit_logs_workspace_id_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_workspace_id_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_workspace_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    # 2. Create target audit_logs table matching approved schema design
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'api_key', 'system')",
            name=op.f("ck_audit_logs_actor_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_audit_logs_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        "ix_audit_logs_workspace_id_created_at",
        "audit_logs",
        ["workspace_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_workspace_id_action",
        "audit_logs",
        ["workspace_id", "action"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Drop target audit_logs table and indexes
    op.drop_index("ix_audit_logs_workspace_id_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_workspace_id_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    # 2. Recreate 0002 shape exactly (copied from 0002 upgrade)
    op.create_table(
        "audit_logs",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name=op.f("ck_audit_logs_actor_type_valid")
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_audit_logs_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"], unique=False)
    op.create_index(
        "ix_audit_logs_workspace_id_action", "audit_logs", ["workspace_id", "action"], unique=False
    )
    op.create_index(
        "ix_audit_logs_workspace_id_created_at",
        "audit_logs",
        ["workspace_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
