"""reviews.posted_at/embedding, places.summary

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reviews", sa.Column("embedding", Vector(1024), nullable=True))
    op.add_column("places", sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "summary")
    op.drop_column("reviews", "embedding")
    op.drop_column("reviews", "posted_at")
