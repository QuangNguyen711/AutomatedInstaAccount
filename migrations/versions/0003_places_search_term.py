"""places.search_term

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("places", sa.Column("search_term", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "search_term")
