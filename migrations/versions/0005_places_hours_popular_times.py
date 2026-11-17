"""add places.opening_hours and places.popular_times

Both scraped from a place's Maps detail page and used by the LLM ranker (open-now / nearby /
avoid-busy reasoning) and shown on the card. JSON, nullable — existing cached rows simply carry
NULL until re-crawled.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("places", sa.Column("opening_hours", sa.JSON(), nullable=True))
    op.add_column("places", sa.Column("popular_times", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "popular_times")
    op.drop_column("places", "opening_hours")
