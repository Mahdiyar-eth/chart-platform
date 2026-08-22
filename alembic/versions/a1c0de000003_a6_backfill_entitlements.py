"""A6 — backfill entitlements from existing paid orders (legacy compat).

Creates an Entitlement (source='order', source_ref=order.id) for every paid,
non-anonymous order whose Plan key maps to a gated kind, so existing customers
retain access after the credit-economy gate rewrite.

SAFETY (user rule): this data migration must be run against a detached/QA DB,
never production. Use `scripts/migrate_entitlements.py --dry-run` to preview the
count, then `--apply --yes` against the QA DB, then validate there. The alembic
migration (below) mirrors the same backfill and is idempotent (checks source_ref).

Revision ID: a1c0de000003_a6_backfill_entitlements
Revises: a1c0de000002
Create Date: 2026-08-22
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "a1c0de000003"
down_revision = "a1c0de000002"
branch_labels = None
depends_on = None

_KIND_BY_PLAN = {
    "basic": "report", "full": "report", "gold": "report",
    "report_basic": "report", "report_full": "report", "report_gold": "report",
    "report_audio": "audio", "synastry": "synastry", "synastry_full": "synastry",
    "transit_12m": "transit", "transit_3m": "transit",
    "chat_pack_20": "chat", "monthly": "chat", "rectify": "rectify",
}


def upgrade() -> None:
    bind = op.get_bind()
    meta = sa.MetaData()
    orders = sa.Table("orders", meta, autoload_with=bind)
    ents = sa.Table("entitlements", meta, autoload_with=bind)

    sel = sa.select(orders).where(orders.c.status == "paid")
    inserted = 0
    for row in bind.execute(sel).mappings():
        kind = _KIND_BY_PLAN.get(row["plan_key"])
        if not kind or not row["user_id"]:
            continue  # not gated, or anonymous order with no owner
        exists = bind.execute(
            sa.select(ents.c.id).where(ents.c.source_ref == row["id"])
        ).first()
        if exists:
            continue  # idempotent
        bind.execute(
            ents.insert().values(
                id=uuid.uuid4().hex,
                user_id=row["user_id"],
                kind=kind,
                chart_id=row.get("chart_id"),
                ref_id=row.get("report_id"),
                quantity=1,
                used=0,
                source="order",
                source_ref=row["id"],
            )
        )
        inserted += 1
    print(f"A6 backfill: created {inserted} entitlement(s) for paid orders.")


def downgrade() -> None:
    # Entitlements are derived data; keep it simple — remove migration-source rows.
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM entitlements WHERE source = 'order'"))
