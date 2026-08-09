"""initial schema: places, photos, reviews

Revision ID: 0001
Revises:
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # enabled now (cheap, idempotent) so a future migration can add a pgvector column
    # to `reviews` without needing its own "enable extension" step
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "places",
        sa.Column("place_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("maps_url", sa.String(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_places_lat_lng", "places", ["lat", "lng"])

    op.create_table(
        "photos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "place_id",
            sa.String(),
            sa.ForeignKey("places.place_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("is_good", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_photos_place_id", "photos", ["place_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "place_id",
            sa.String(),
            sa.ForeignKey("places.place_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
    )
    op.create_index("ix_reviews_place_id", "reviews", ["place_id"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("photos")
    op.drop_table("places")
