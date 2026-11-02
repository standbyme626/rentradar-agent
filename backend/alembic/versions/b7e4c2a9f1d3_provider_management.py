"""provider management tables

Revision ID: b7e4c2a9f1d3
Revises: 0f186cdd3d57
Create Date: 2026-10-31 00:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e4c2a9f1d3"
down_revision: str | None = "0f186cdd3d57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_settings",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("provider"),
    )
    op.create_table(
        "provider_usage",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limit_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("provider", "period"),
    )
    op.create_table(
        "provider_health",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="unknown"
        ),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("provider"),
    )
    op.create_table(
        "provider_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "capability", sa.String(length=32), nullable=False, server_default="health_check"
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("quota_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "provider_calls_provider_time_idx",
        "provider_calls",
        ["provider", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_calls_provider"), "provider_calls", ["provider"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provider_calls_provider"), table_name="provider_calls")
    op.drop_index("provider_calls_provider_time_idx", table_name="provider_calls")
    op.drop_table("provider_calls")
    op.drop_table("provider_health")
    op.drop_table("provider_usage")
    op.drop_table("provider_settings")
