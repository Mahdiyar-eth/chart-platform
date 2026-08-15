"""P6: orders.user_id (credit-pack orders without a chart).

Revision ID: a7c0c5d2e9f4
Revises: 7108139b90bd
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c0c5d2e9f4"
down_revision = "7108139b90bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("user_id", sa.String(), nullable=True))
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_foreign_key("orders_user_id_fkey", "orders", "users",
                          ["user_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("orders_user_id_fkey", "orders", type_="foreignkey")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_column("orders", "user_id")
