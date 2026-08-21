"""a1: add credit_prices + entitlements + credit_transactions.idempotency_key

HERMES-PLAN-v1 · A1 (credit economy data model). Adds the per-action credit
price catalog, the user-scoped entitlement grants, and an idempotency key on
the credit ledger. Author-driven (no autogenerate): the test/CI DB is built via
create_all, so the migration is hand-authored to match the SQLModel metadata.

Revision ID: a1c0de000001
Revises: 10958fde8752
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from sqlmodel.sql.sqltypes import AutoString

revision = "a1c0de000001"
down_revision = "10958fde8752"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # credit_prices — per-action credit cost (unit-of-money = credit)
    op.create_table(
        "credit_prices",
        sa.Column("action_key", AutoString(), nullable=False),
        sa.Column("title_fa", AutoString(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("action_key"),
    )

    # entitlements — user-scoped grants (NOT chart-scoped; fixes F2)
    op.create_table(
        "entitlements",
        sa.Column("id", AutoString(), nullable=False),
        sa.Column("user_id", AutoString(), nullable=False),
        sa.Column("kind", AutoString(), nullable=False),
        sa.Column("chart_id", AutoString(), nullable=True),
        sa.Column("ref_id", AutoString(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("source", AutoString(), nullable=False),
        sa.Column("source_ref", AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entitlements_user_kind", "entitlements",
                    ["user_id", "kind"])
    op.create_index("ix_entitlements_chart_kind", "entitlements",
                    ["chart_id", "kind"])

    # credit_transactions.idempotency_key + unique index (A1)
    op.add_column("credit_transactions",
                  sa.Column("idempotency_key", AutoString(), nullable=True))
    op.create_index("uq_credit_tx_idem_key", "credit_transactions",
                    ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_credit_tx_idem_key", table_name="credit_transactions")
    op.drop_column("credit_transactions", "idempotency_key")
    op.drop_index("ix_entitlements_chart_kind", table_name="entitlements")
    op.drop_index("ix_entitlements_user_kind", table_name="entitlements")
    op.drop_table("entitlements")
    op.drop_table("credit_prices")
