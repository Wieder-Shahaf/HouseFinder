"""Initial schema — listings table

Revision ID: 0001
Revises:
Create Date: 2026-04-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # Infrastructure columns (D-02)
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("is_seen", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_favorited", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        sa.Column("dedup_fingerprint", sa.String(64), nullable=True),
        # Listing data columns (D-03)
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("rooms", sa.Float(), nullable=True),
        sa.Column("size_sqm", sa.Integer(), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("contact_info", sa.String(500), nullable=True),
        sa.Column("post_date", sa.DateTime(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("source_badge", sa.String(50), nullable=True),
        # Metadata columns (D-04)
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        # D-05: Dedup constraint
        sa.UniqueConstraint("source", "source_id", name="uq_listing_source_source_id"),
    )


def downgrade() -> None:
    op.drop_table("listings")
