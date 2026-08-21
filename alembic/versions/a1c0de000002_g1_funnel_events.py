"""g1: add funnel_events (anonymous funnel tracking)

HERMES-PLAN-v1 · G1 (funnel measurement). Append-only, anonymous funnel event
log backing the admin conversion-funnel dashboard. Backed by track.js ->
/api/track. Hand-authored (no autogenerate): test/CI DB is built via create_all.

Revision ID: a1c0de000002
Revises: a1c0de000001
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from sqlmodel.sql.sqltypes import AutoString

revision = "a1c0de000002"
down_revision = "a1c0de000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funnel_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event", AutoString(length=64), nullable=False),
        sa.Column("session_id", AutoString(length=64), nullable=False,
                  server_default=""),
        sa.Column("path", AutoString(length=255), nullable=False,
                  server_default=""),
        sa.Column("ref", AutoString(length=64), nullable=False,
                  server_default=""),
        sa.Column("props", AutoString(length=1024), nullable=False,
                  server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funnel_events_event_time", "funnel_events",
                    ["event", "created_at"])
    op.create_index("ix_funnel_events_session", "funnel_events",
                    ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_funnel_events_session", table_name="funnel_events")
    op.drop_index("ix_funnel_events_event_time", table_name="funnel_events")
    op.drop_table("funnel_events")
