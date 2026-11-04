"""P3: cache SZMC subway lines/stations in Postgres

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-04 20:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transit_lines",
        sa.Column("line_key", sa.String(length=64), nullable=False),
        sa.Column("city_code", sa.String(length=16), server_default="sz", nullable=False),
        sa.Column("line_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=16), server_default="2f7d5b", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("line_key"),
        sa.UniqueConstraint("city_code", "line_code", name="uq_transit_line"),
    )
    op.create_table(
        "transit_stations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("line_key", sa.String(length=64), nullable=False),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column(
            "coord_system", sa.String(length=16), server_default="GCJ02", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["line_key"], ["transit_lines.line_key"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("line_key", "station_code", name="uq_transit_station"),
    )
    op.create_index(
        "transit_stations_line_seq_idx", "transit_stations", ["line_key", "seq"]
    )


def downgrade() -> None:
    op.drop_index("transit_stations_line_seq_idx", table_name="transit_stations")
    op.drop_table("transit_stations")
    op.drop_table("transit_lines")
