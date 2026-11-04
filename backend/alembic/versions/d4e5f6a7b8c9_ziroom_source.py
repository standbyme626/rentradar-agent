"""P3: activate the Ziroom source metadata

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-04 13:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET name = '自如公开列表 API',
                kind = 'api',
                enabled = false,
                rate_limit = '{"qps": 0.2, "daily": 500}'::jsonb
            WHERE code = 'ziroom'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET name = '自如（预留，未接入）',
                kind = 'html',
                enabled = false
            WHERE code = 'ziroom'
            """
        )
    )
