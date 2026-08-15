"""P3 fix: explorations.chart_id must be nullable (chart can be deleted).

Revision ID: 9f2c41e8b0d1
Revises: fd5cf11364ab
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa

revision = "9f2c41e8b0d1"
down_revision = "fd5cf11364ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("explorations", "chart_id",
                    existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("explorations", "chart_id",
                    existing_type=sa.String(), nullable=False)
