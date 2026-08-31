"""Z2/Z3 (Opus R3): restore transit_forecasts.chart_id FK + create subscribers table.

Direction fix: c8d2e3f4a5b6 had DROPPED the FK to make `alembic check` pass.
Per the new rule ("never resolve drift by destruction"), the model is the truth:
- transit_forecasts.chart_id gets its FK back (ON DELETE CASCADE) — the table
  stores PAID narratives (personal data) and must die with the chart.
- subscribers is created (model existed since G3; prod was patched manually).

Revision: d9e3f4a5b6c7 (head after c8d2e3f4a5b6)
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e3f4a5b6c7"
down_revision = "c8d2e3f4a5b6"
branch_labels = None
depends_on = None


def _has_fk(bind, table, name) -> bool:
    insp = sa.inspect(bind)
    return any(fk.get("name") == name for fk in insp.get_foreign_keys(table))


def _has_table(bind, table) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    # Z2: restore the FK (guarded — some envs may already have it under a name)
    if not _has_fk(bind, "transit_forecasts", "transit_forecasts_chart_id_fkey"):
        op.create_foreign_key(
            "transit_forecasts_chart_id_fkey", "transit_forecasts", "charts",
            ["chart_id"], ["id"], ondelete="CASCADE",
        )
    else:
        # wrong shape (no cascade)? recreate properly
        insp = sa.inspect(bind)
        fk = next(f for f in insp.get_foreign_keys("transit_forecasts")
                  if f.get("name") == "transit_forecasts_chart_id_fkey")
        if not (fk.get("ondelete") == "CASCADE"):
            op.drop_constraint("transit_forecasts_chart_id_fkey", "transit_forecasts",
                               type_="foreignkey")
            op.create_foreign_key(
                "transit_forecasts_chart_id_fkey", "transit_forecasts", "charts",
                ["chart_id"], ["id"], ondelete="CASCADE",
            )
    # Z3: subscribers (G3 lead magnet) — idempotent
    if not _has_table(bind, "subscribers"):
        op.create_table(
            "subscribers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("contact", sa.String(length=200), nullable=False),
            sa.Column("channel", sa.String(length=20), server_default="sms",
                      nullable=False),
            sa.Column("source", sa.String(length=40), server_default="guide",
                      nullable=False),
            sa.Column("token", sa.String(length=64), server_default="", nullable=False),
            sa.Column("unsubscribed_at", sa.DateTime(), nullable=True),
            sa.Column("consent_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_subscribers_contact", "subscribers", ["contact"])
        op.create_index("ix_subscribers_token", "subscribers", ["token"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "subscribers"):
        for ix in ("ix_subscribers_token", "ix_subscribers_contact"):
            try:
                op.drop_index(ix, table_name="subscribers")
            except Exception:  # noqa: BLE001 — may not exist on older shapes
                pass
        op.drop_table("subscribers")
    if _has_fk(bind, "transit_forecasts", "transit_forecasts_chart_id_fkey"):
        op.drop_constraint("transit_forecasts_chart_id_fkey", "transit_forecasts",
                           type_="foreignkey")
