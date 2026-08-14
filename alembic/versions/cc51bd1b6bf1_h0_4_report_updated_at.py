"""h0.4 report updated_at

Revision ID: cc51bd1b6bf1
Revises: (previous)
Create Date: 2026-08-14

Adds reports.updated_at — heartbeat for stale-job recovery (HARDENING H0.4):
a report stuck in 'running' for > STALE_AFTER minutes (worker crash / dead
queue) is re-enqueued by scripts/recover_stale_reports.py.
"""
from alembic import op
import sqlalchemy as sa

revision = "cc51bd1b6bf1"
down_revision = "9f1a5ac160e7"


def upgrade() -> None:
    op.add_column("reports", sa.Column("updated_at", sa.DateTime(timezone=True),
                                       server_default=sa.func.now(), nullable=False))
    op.create_index("ix_reports_status_updated", "reports", ["status", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_reports_status_updated", table_name="reports")
    op.drop_column("reports", "updated_at")
