"""subscription_expiry_unique

audit r4 A9/B8: subscriptions.chat_id becomes nullable (web purchases have no
chat identity) and a UNIQUE index on (chart_id, COALESCE(chat_id,'')) prevents
duplicate subscriptions for the same chart+account.

Revision ID: 3c92dac1a241
Revises: 9a3c5e7b1d2f
Create Date: 2026-08-14 08:38:31.666899

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel.sql.sqltypes  # noqa: F401 — SQLModel AutoString type

# revision identifiers, used by Alembic.
revision: str = '3c92dac1a241'
down_revision: Union[str, Sequence[str], None] = '9a3c5e7b1d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) chat_id must accept NULL (web monthly purchases)
    op.alter_column('subscriptions', 'chat_id', existing_type=sa.String(), nullable=True)
    # 2) dedupe before adding the unique index: keep the row with the latest expiry
    op.execute(
        """
        DELETE FROM subscriptions a
        USING subscriptions b
        WHERE a.id <> b.id
          AND a.chart_id = b.chart_id
          AND COALESCE(a.chat_id, '') = COALESCE(b.chat_id, '')
          AND (a.expires_at IS NULL OR b.expires_at IS NULL OR a.expires_at <= b.expires_at)
          AND a.id < b.id
        """
    )
    # 3) one subscription per (chart, account)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_sub_chart_account "
        "ON subscriptions (chart_id, COALESCE(chat_id, ''))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sub_chart_account")
    op.alter_column('subscriptions', 'chat_id', existing_type=sa.String(), nullable=False)
