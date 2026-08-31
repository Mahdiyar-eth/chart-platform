"""R13/N3 — drop the orders.plan_key FK to plans.key.

Credit-action orders (report_full, solar_return, …) don't reference
plans.key; retiring the legacy toman plans made that FK a landmine (any
order row with a credit action key would fail). plan_key stays as an
indexed plain column — legacy values keep working.

Revision ID: b7c4d9e21f05
Revises: ea82d92314de
Create Date: 2026-08-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b7c4d9e21f05'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5e6'  # the previous real head — no branch
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # find the actual FK name (naming convention varies across environments)
    fk = conn.execute(sa.text(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'orders'::regclass AND contype = 'f' "
        "AND pg_get_constraintdef(oid) LIKE '%plan_key%'"
    )).scalar()
    if fk:
        op.execute(f'ALTER TABLE orders DROP CONSTRAINT IF EXISTS "{fk}"')


def downgrade() -> None:
    # not reversible meaningfully: re-adding the FK would break credit-action
    # rows. Kept as no-op on purpose.
    pass
