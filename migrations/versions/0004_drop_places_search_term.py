"""drop places.search_term

Caching moved from per-(location+search-query) to per-place-id: the listing search now always
runs fresh, and only a place's own detail data (photos/reviews) gets reused if cached and still
within TTL, regardless of what query found it. search_term is no longer read anywhere.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("places", "search_term")


def downgrade() -> None:
    op.add_column("places", sa.Column("search_term", sa.String(), nullable=True))
