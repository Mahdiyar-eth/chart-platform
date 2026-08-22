"""B1+B4 — transit forecast cache, alert log, notification_prefs.transit_alerts.

Revision ID: b4a0de000004
Revises: a1c0de000003
Create Date: 2026-08-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4a0de000004"
down_revision = "a1c0de000003"
branch_labels = None
depends_on = None


def _exists(name: str) -> bool:
    return op.get_bind().execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:n"
    ), {"n": name}).scalar() is not None


def _has_column(table: str, column: str) -> bool:
    return op.get_bind().execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=:t AND column_name=:c"
    ), {"t": table, "c": column}).scalar() is not None


def upgrade() -> None:
    # Idempotent: test DBs were created via SQLModel.metadata.create_all and already
    # carry these objects — apply only what is missing (prod starts empty).
    if not _exists("transit_forecasts"):
        op.create_table(
            "transit_forecasts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("chart_id", sa.String(36), sa.ForeignKey("charts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("months", sa.Integer(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_transit_forecasts_chart_id", "transit_forecasts", ["chart_id"])

    if not _exists("transit_alert_log"):
        op.create_table(
            "transit_alert_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_key", sa.String(128), nullable=False),
            sa.Column("chart_id", sa.String(64), nullable=False),
            sa.Column("week", sa.String(10), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_transit_alert_log_user_key", "transit_alert_log", ["user_key"], unique=True)
        op.create_index("ix_transit_alert_log_week", "transit_alert_log", ["week"])
        op.create_index("ix_transit_alert_log_chart_id", "transit_alert_log", ["chart_id"])

    if not _has_column("notification_prefs", "transit_alerts"):
        op.add_column("notification_prefs", sa.Column("transit_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    if _has_column("notification_prefs", "transit_alerts"):
        op.drop_column("notification_prefs", "transit_alerts")
    if _exists("transit_alert_log"):
        for ix in ("ix_transit_alert_log_chart_id", "ix_transit_alert_log_week",
                   "ix_transit_alert_log_user_key", "ix_transit_alert_log_user_week"):
            op.get_bind().execute(sa.text(f"DROP INDEX IF EXISTS {ix}"))
        op.drop_table("transit_alert_log")
    if _exists("transit_forecasts"):
        op.get_bind().execute(sa.text("DROP INDEX IF EXISTS ix_transit_forecasts_chart_id"))
        op.drop_table("transit_forecasts")
