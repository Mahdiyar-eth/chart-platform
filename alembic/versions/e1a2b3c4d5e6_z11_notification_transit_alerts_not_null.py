"""Z11 (Opus R3 P2-1): notification_prefs.transit_alerts NOT NULL with backfill.

c8d2e3f4a5b6 had flipped this column to nullable=True to satisfy `alembic check`
against an underspecified model. Per the new rule ("never resolve drift by
weakening the DB"), the MODEL is now nullable=False (Z11) and this migration
makes the schema match: backfill any NULL rows to true, then set NOT NULL.

revision: e1a2b3c4d5e6
down_revision: d9e3f4a5b6c7
"""
from alembic import op
import sqlalchemy as sa

revision = "e1a2b3c4d5e6"
down_revision = "d9e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("notification_prefs")}
    if cols.get("transit_alerts") and cols["transit_alerts"].get("nullable", False):
        # backfill any existing NULLs, then enforce NOT NULL
        op.execute("UPDATE notification_prefs SET transit_alerts = true "
                   "WHERE transit_alerts IS NULL")
        op.alter_column("notification_prefs", "transit_alerts",
                        existing_type=sa.Boolean(), nullable=False,
                        server_default=sa.true())


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("notification_prefs")}
    if cols.get("transit_alerts") and not cols["transit_alerts"].get("nullable", True):
        op.alter_column("notification_prefs", "transit_alerts",
                        existing_type=sa.Boolean(), nullable=True,
                        server_default=sa.true())
