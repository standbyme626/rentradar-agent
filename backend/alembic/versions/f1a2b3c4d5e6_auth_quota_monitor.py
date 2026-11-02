"""auth sessions, audit log, monitor matches

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-10-31 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_hash", sa.String(length=128), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("audit_log_created_idx", "audit_log", ["created_at"])

    op.add_column(
        "agent_sessions",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_foreign_key(
        "fk_agent_sessions_user_id",
        "agent_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE agent_sessions SET user_id = 1 WHERE user_id IS NULL")

    op.add_column(
        "agent_monitors",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_monitors",
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    op.add_column(
        "agent_monitors",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_monitors",
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_monitors",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_monitors_user_id", "agent_monitors", ["user_id"])
    op.create_foreign_key(
        "fk_agent_monitors_user_id",
        "agent_monitors",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE agent_monitors SET user_id = 1 WHERE user_id IS NULL")

    op.create_table(
        "agent_monitor_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("monitor_id", sa.String(length=64), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("match_key", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("rent", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["agent_monitors.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "monitor_id", "match_key", name="uq_monitor_match_key"
        ),
    )
    op.create_index(
        "agent_monitor_matches_pending_idx",
        "agent_monitor_matches",
        ["notified_at", "created_at"],
    )
    op.create_index(
        "agent_monitor_matches_monitor_idx",
        "agent_monitor_matches",
        ["monitor_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "agent_monitor_matches_monitor_idx", table_name="agent_monitor_matches"
    )
    op.drop_index(
        "agent_monitor_matches_pending_idx", table_name="agent_monitor_matches"
    )
    op.drop_table("agent_monitor_matches")

    op.drop_constraint(
        "fk_agent_monitors_user_id", "agent_monitors", type_="foreignkey"
    )
    op.drop_index("ix_agent_monitors_user_id", table_name="agent_monitors")
    op.drop_column("agent_monitors", "updated_at")
    op.drop_column("agent_monitors", "last_notified_at")
    op.drop_column("agent_monitors", "last_checked_at")
    op.drop_column("agent_monitors", "enabled")
    op.drop_column("agent_monitors", "user_id")

    op.drop_constraint(
        "fk_agent_sessions_user_id", "agent_sessions", type_="foreignkey"
    )
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_column("agent_sessions", "user_id")

    op.drop_index("audit_log_created_idx", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
