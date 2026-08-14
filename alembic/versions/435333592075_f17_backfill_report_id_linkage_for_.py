"""f17 backfill report_id linkage for legacy paid reports

Revision ID: 435333592075
Revises: cec42d441b5c
Create Date: 2026-08-14 17:42:49.045367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel.sql.sqltypes  # noqa: F401 — SQLModel AutoString type

# revision identifiers, used by Alembic.
revision: str = '435333592075'
down_revision: Union[str, Sequence[str], None] = 'cec42d441b5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """F-17 (audit v7 P1): backfill order→report linkage for LEGACY reports.

    Reports created before the report_id linkage existed have
    orders.report_id = NULL. The download gate now requires the PAID order
    that OWNS the report (orders.report_id = reports.id); without this
    backfill, every legacy report would be locked forever.

    Rule: link each unlinked report to the ONLY paid order of its chart.
    Charts with 0 or 2+ paid orders are left untouched (ambiguous — must be
    resolved manually; a refunded order stays unlinked so the report stays
    locked, which is the correct entitlement outcome).
    """
    op.execute(sa.text(
        "UPDATE orders o SET report_id = r.id "
        "FROM reports r "
        "WHERE o.report_id IS NULL "
        "  AND o.status = 'paid' "
        "  AND r.chart_id = o.chart_id "
        "  AND NOT EXISTS (SELECT 1 FROM orders o2 "
        "                  WHERE o2.chart_id = o.chart_id AND o2.status = 'paid' "
        "                    AND o2.id <> o.id) "
        "  AND NOT EXISTS (SELECT 1 FROM orders o3 WHERE o3.report_id = r.id) "
        "  AND (SELECT count(*) FROM reports r2 "
        "       WHERE r2.chart_id = o.chart_id "
        "         AND NOT EXISTS (SELECT 1 FROM orders o4 WHERE o4.report_id = r2.id)) = 1"
    ))


def downgrade() -> None:
    # no-op: backfill is not reversible (and does not need to be)
    pass
