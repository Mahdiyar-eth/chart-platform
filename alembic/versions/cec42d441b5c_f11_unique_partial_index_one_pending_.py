"""f11 unique partial index: one pending withdrawal per user

Revision ID: cec42d441b5c
Revises: 9d34ed9201c2
Create Date: 2026-08-14 17:11:36.602738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel.sql.sqltypes  # noqa: F401 — SQLModel AutoString type

# revision identifiers, used by Alembic.
revision: str = 'cec42d441b5c'
down_revision: Union[str, Sequence[str], None] = '9d34ed9201c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """F-11 (audit v6 P0): at most ONE pending withdrawal per user — the
    atomic enforcement of the application-level 'one pending at a time' rule
    under concurrent requests."""
    op.create_index(
        "uq_withdrawal_one_pending",
        "withdrawal_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_withdrawal_one_pending", table_name="withdrawal_requests")
