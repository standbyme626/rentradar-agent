"""P3: add parsed Beike subway/room fields to listings

The crawler parser already emits these fields (subway line/station/distance,
bedroom counts, default-image flag, sign time, operation description). Without
the columns, any full ORM select of Listing fails, breaking agent search.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-04 20:55:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("subway_line", sa.String(length=64)))
    op.add_column("listings", sa.Column("subway_station", sa.String(length=64)))
    op.add_column("listings", sa.Column("subway_distance_m", sa.Integer()))
    op.add_column("listings", sa.Column("bedrooms", sa.Integer()))
    op.add_column("listings", sa.Column("halls", sa.Integer()))
    op.add_column("listings", sa.Column("bathrooms", sa.Integer()))
    op.add_column("listings", sa.Column("kitchens", sa.Integer()))
    op.add_column("listings", sa.Column("is_default_image", sa.Boolean()))
    op.add_column(
        "listings", sa.Column("sign_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "listings", sa.Column("operation_desc", sa.String(length=255))
    )


def downgrade() -> None:
    for column in (
        "operation_desc",
        "sign_at",
        "is_default_image",
        "kitchens",
        "bathrooms",
        "halls",
        "bedrooms",
        "subway_distance_m",
        "subway_station",
        "subway_line",
    ):
        op.drop_column("listings", column)
