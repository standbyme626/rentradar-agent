"""agent llm trace columns

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-31 03:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column("model", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column(
        "agent_sessions",
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_sessions",
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_sessions",
        sa.Column(
            "cost", sa.Numeric(precision=10, scale=6), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "agent_sessions",
        sa.Column(
            "llm_fallback", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_sessions", "llm_fallback")
    op.drop_column("agent_sessions", "cost")
    op.drop_column("agent_sessions", "completion_tokens")
    op.drop_column("agent_sessions", "prompt_tokens")
    op.drop_column("agent_sessions", "model")
