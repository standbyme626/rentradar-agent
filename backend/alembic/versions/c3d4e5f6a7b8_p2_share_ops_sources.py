"""P2: share links, reference rents, multi-source seed

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-04 04:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), server_default="", nullable=False),
        sa.Column("label", sa.String(length=64), server_default="只读看板", nullable=False),
        sa.Column("scope", sa.String(length=32), server_default="dashboard", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("share_links_token_idx", "share_links", ["token_hash"])

    op.create_table(
        "reference_rents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("city_id", sa.Integer(), nullable=False),
        sa.Column("community_id", sa.Integer(), nullable=True),
        sa.Column("community_name", sa.String(length=128), nullable=True),
        sa.Column("district", sa.String(length=64), nullable=True),
        sa.Column("layout", sa.String(length=32), server_default="", nullable=False),
        sa.Column("monthly_rent", sa.Integer(), nullable=False),
        sa.Column("reference_month", sa.String(length=7), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=2), server_default="0.8", nullable=False),
        sa.Column(
            "raw",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "city_id",
            "community_id",
            "layout",
            "reference_month",
            "source",
            name="uq_reference_rent_scope",
        ),
    )
    op.create_index(
        "reference_rents_lookup_idx",
        "reference_rents",
        ["city_id", "community_id", "layout"],
    )
    op.create_index(
        "listings_city_community_rent_idx",
        "listings",
        ["city_id", "community_id", "rent"],
    )

    # Multi-source: manual import is a first-class, independently switchable
    # source. It is disabled by default so an operator must explicitly enable
    # it on the admin Sources page before scheduled imports run.
    op.execute(
        """
        INSERT INTO sources (code, name, kind, enabled, rate_limit)
        VALUES ('manual', '手动导入（品牌公寓/线下房源）', 'json', false, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO sources (code, name, kind, enabled, rate_limit)
        VALUES ('ziroom', '自如（预留，未接入）', 'html', false, '{"qps": 0.2, "daily": 500}'::jsonb)
        ON CONFLICT (code) DO NOTHING
        """
    )
    # Ensure at least two city configs exist for independent city scheduling.
    op.execute(
        """
        INSERT INTO cities (code, name, domain_template, center_lng, center_lat, enabled)
        VALUES
          ('sz', '深圳', 'https://sz.zu.ke.com', 114.057868, 22.543099, true),
          ('sh', '上海', 'https://sh.zu.ke.com', 121.473701, 31.230416, false)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("listings_city_community_rent_idx", table_name="listings")
    op.drop_index("reference_rents_lookup_idx", table_name="reference_rents")
    op.drop_table("reference_rents")
    op.drop_index("share_links_token_idx", table_name="share_links")
    op.drop_table("share_links")
