"""P1: agent tool trace, cover images, reputation mentions, eval runs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-04 03:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column(
            "guardrails",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.create_table(
        "listing_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), server_default="cover", nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("local_path", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("brightness", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("phash", sa.String(length=16), nullable=True),
        sa.Column("phash_bucket", sa.String(length=4), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "kind", "url", name="uq_listing_image"),
    )
    op.create_index("listing_images_phash_bucket_idx", "listing_images", ["phash_bucket"])
    op.create_index("listing_images_listing_idx", "listing_images", ["listing_id", "kind"])

    op.create_table(
        "listing_image_analysis",
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column(
            "signals",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(length=16), server_default="unknown", nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column(
            "quality",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("needs_vision", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("listing_id"),
    )

    op.create_table(
        "reputation_mentions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("community_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=16), server_default="low", nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=2), server_default="0.5", nullable=False),
        sa.Column("match_status", sa.String(length=16), server_default="verified", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "reputation_mentions_community_idx",
        "reputation_mentions",
        ["community_id", "created_at"],
    )
    op.create_index(
        "reputation_mentions_status_idx",
        "reputation_mentions",
        ["match_status", "expires_at"],
    )

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tool", sa.String(length=32), nullable=False),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("result_summary", sa.String(length=255), server_default="", nullable=False),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("agent_tool_calls_session_idx", "agent_tool_calls", ["session_id", "step"])

    op.create_table(
        "agent_eval_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_version", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), server_default="rules", nullable=False),
        sa.Column("total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("passed", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "cases",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("agent_eval_runs")
    op.drop_index("agent_tool_calls_session_idx", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
    op.drop_index("reputation_mentions_status_idx", table_name="reputation_mentions")
    op.drop_index("reputation_mentions_community_idx", table_name="reputation_mentions")
    op.drop_table("reputation_mentions")
    op.drop_table("listing_image_analysis")
    op.drop_index("listing_images_listing_idx", table_name="listing_images")
    op.drop_index("listing_images_phash_bucket_idx", table_name="listing_images")
    op.drop_table("listing_images")
    op.drop_column("agent_sessions", "guardrails")
