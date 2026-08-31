"""Y4/N7: unique (chart_id, months) on transit_forecasts

Revision ID: c7f1a2b9d4e6
Revises: b4a0de000004
Create Date: 2026-08-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7f1a2b9d4e6"
down_revision: Union[str, Sequence[str], None] = "b4a0de000004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # R23: prevent duplicate cache rows under concurrency.
    # 1) collapse existing duplicates keeping the newest row per (chart_id, months)
    op.execute("""
        DELETE FROM transit_forecasts a
        USING transit_forecasts b
        WHERE a.chart_id = b.chart_id
          AND a.months = b.months
          AND a.id < b.id
    """)
    op.create_unique_constraint(
        "uq_transit_chart_months", "transit_forecasts", ["chart_id", "months"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_transit_chart_months", "transit_forecasts", type_="unique")
