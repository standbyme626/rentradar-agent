"""commute depart buckets and direction

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-11-04 01:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "commute_samples",
        sa.Column("depart_bucket", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "commute_samples",
        sa.Column(
            "direction",
            sa.String(length=32),
            nullable=False,
            server_default="community_to_destination",
        ),
    )
    op.create_index(
        "commute_community_bucket_idx",
        "commute_samples",
        ["community_id", "destination_key", "depart_bucket"],
    )


def downgrade() -> None:
    op.drop_index("commute_community_bucket_idx", table_name="commute_samples")
    op.drop_column("commute_samples", "direction")
    op.drop_column("commute_samples", "depart_bucket")
