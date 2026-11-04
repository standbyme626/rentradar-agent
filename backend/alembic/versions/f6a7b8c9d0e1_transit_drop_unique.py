"""P3: allow duplicate station codes on a transit line

Some SZMC line files reuse a station id for not-yet-open/renamed stops
(e.g. line 8's 大梅沙/溪涌). Keep the rows but drop the per-line station
uniqueness; sync still deletes and reinserts a line atomically.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-04 20:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_transit_station", "transit_stations", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_transit_station", "transit_stations", ["line_key", "station_code"]
    )
