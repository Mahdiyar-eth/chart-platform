"""A3 — entitlement layer. Gates check "does the user have an entitlement?"
instead of "does the user have a paid order?" Entitlements come from credits
(credit economy) OR from legacy paid orders (backfilled migration).

The critical rule: every gate must ALSO accept the legacy paid-order path so no
current customer loses access during the migration.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from app.credits import spend
from app.models import Entitlement, Order


def _now() -> datetime:
    """Naive UTC now — the DB stores DateTime columns naive (TIMESTAMP WITHOUT
    TIME ZONE), so comparisons must be naive-vs-naive to avoid tz-mismatch."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _usable(ent: Entitlement, now: datetime) -> bool:
    """An entitlement is usable if not expired and not exhausted."""
    if ent.expires_at and ent.expires_at < now:
        return False
    return (ent.quantity - ent.used) > 0


def has(session: Session, user_id: str, kind: str, *,
        chart_id: str | None = None, ref_id: str | None = None) -> Entitlement | None:
    """Return the first usable entitlement for (user, kind [, chart]/[ref]).

    Never cross-chart/cross-ref: an entitlement for chart X is NOT valid for
    chart Y (closed per plan A3)."""
    now = _now()
    ents = session.exec(
        select(Entitlement).where(
            Entitlement.user_id == user_id,
            Entitlement.kind == kind,
        )
    ).all()
    for ent in ents:
        # X5/R5: scope is MANDATORY. An unscoped entitlement (NULL chart_id /
        # ref_id) must never satisfy a scoped request — otherwise one purchase
        # would unlock every report/chart of the user. Both credit grants and
        # legacy order backfills are chart/report-scoped, so strict matching is
        # safe for existing customers.
        _user_level = kind in ("chat", "audio")  # packs usable across the user's own charts
        if not _user_level and chart_id is not None and ent.chart_id != chart_id:
            continue
        if ref_id is not None and ent.ref_id != ref_id:
            continue
        # A request WITH scope must match an entitlement that carries that scope;
        # unscoped ents only satisfy unscoped lookups (e.g. chat packs).
        if _usable(ent, now):
            return ent
    return None


def consume(session: Session, ent: Entitlement, n: int = 1) -> bool:
    """Atomically consume `n` units from a quantity bucket (chat pack).
    Guarded UPDATE — no read-modify-write race. Returns False when exhausted."""
    from sqlalchemy import text
    res = session.execute(text(
        "UPDATE entitlements SET used = used + :n WHERE id = :id AND used <= quantity - :n"
    ), params={"n": n, "id": ent.id})
    if res.rowcount == 0:
        return False
    session.refresh(ent)
    return True


_QUANTITY_BY_ACTION = {"chat_pack_20": 20, "chat_pack_100": 100}


def _action_quantity(action_key: str) -> int:
    return _QUANTITY_BY_ACTION.get(action_key, 1)


_EXPIRY_DAYS_BY_KIND = {"chat": 30}  # X6/R7: product promise "بستهٔ ۳۰ روزه"


def _expiry_for_kind(kind: str):
    """X6/R7 — entitlement expiry by kind. Returns naive UTC datetime or None."""
    from datetime import timedelta
    days = _EXPIRY_DAYS_BY_KIND.get(kind)
    if not days:
        return None
    return _now() + timedelta(days=days)


def grant_from_credits(session: Session, user_id: str, action_key: str, *,
                       idempotency_key: str,
                       chart_id: str | None = None,
                       ref_id: str | None = None,
                       quantity: int | None = None) -> Entitlement:
    """spend() then create the entitlement, atomically.

    Per-report decision (user, 2026-08): for reports the entitlement is tied to
    ref_id=report.id so buying one report can't unlock another."""

    tx = spend(session, user_id, action_key, idempotency_key=idempotency_key,
               chart_id=chart_id, commit=False)  # X4/R6: single atomic commit below
    # kind is derived from the action_key (e.g. report_full -> 'report')
    kind = _kind_for_action(action_key)
    existing = session.exec(
        select(Entitlement).where(
            Entitlement.source == "credit",
            Entitlement.source_ref == tx.id,
        )
    ).first()
    if existing:
        return existing
    ent = Entitlement(
        user_id=user_id, kind=kind, chart_id=chart_id,
        ref_id=ref_id, quantity=_action_quantity(action_key) if quantity is None else quantity, used=0,
        source="credit", source_ref=tx.id,
        expires_at=_expiry_for_kind(kind),  # X6/R7: packs expire (chat pack = 30d)
    )
    session.add(ent)
    try:
        session.commit()  # X4/R6: credits decrement + entitlement in ONE commit
    except Exception:
        session.rollback()
        raise
    session.refresh(ent)
    return ent


def grant_from_order(session: Session, order: Order) -> Entitlement | None:
    """Legacy path (migration compat): an already-paid order grants an
    entitlement keyed by the order so the gate accepts old customers."""
    kind = _kind_for_plan(order.plan_key)
    if not kind:
        return None
    existing = session.exec(
        select(Entitlement).where(
            Entitlement.source == "order",
            Entitlement.source_ref == order.id,
        )
    ).first()
    if existing:
        return existing
    ent = Entitlement(
        user_id=order.user_id, kind=kind,
        chart_id=order.chart_id, ref_id=order.report_id,
        quantity=1, used=0, source="order", source_ref=order.id,
    )
    session.add(ent)
    session.commit()
    session.refresh(ent)
    return ent


def _kind_for_action(action_key: str) -> str:
    """Map a credit action_key to an entitlement kind."""
    if action_key.startswith("report_"):
        return "report"
    if action_key.startswith("transit_"):
        return "transit"
    if action_key.startswith("chat_"):
        return "chat"
    if action_key.startswith("synastry_"):
        return "synastry"
    if action_key == "rectify":
        return "rectify"
    if action_key.startswith("explore"):
        return "explore"
    return "credit"  # generic


def _kind_for_plan(plan_key: str) -> str | None:
    """Map a legacy Plan key to an entitlement kind (or None if not gated)."""
    return {
        "basic": "report",
        "full": "report",
        "gold": "report",
        "report_basic": "report",
        "report_full": "report",
        "report_gold": "report",
        "report_audio": "audio",
        "synastry": "synastry",
        "synastry_full": "synastry",
        "transit_12m": "transit",
        "transit_3m": "transit",
        "chat_pack_20": "chat",
        "monthly": "chat",
        "rectify": "rectify",
    }.get(plan_key)

def backfill_entitlements(session: Session, dry_run: bool = True) -> dict:
    """A6 — backfill entitlements from existing paid orders so legacy customers
    keep access after the credit-economy gate rewrite.

    - Idempotent: skips orders whose entitlement already exists (source_ref).
    - Refunded/cancelled/not-paid are not selected (status == 'paid' filter).
    - dry_run=True returns a report WITHOUT writing; dry_run=False applies via
      grant_from_order (source='order', keyed by order.id).
    Returns a summary dict for the dry-run / apply report.
    """
    orders = session.exec(
        select(Order).where(Order.status == "paid")
    ).all()
    created = already = skipped = 0
    skipped_kinds = []
    for o in orders:
        # anonymous orders (user_id IS NULL) cannot own an entitlement — skip
        if not o.user_id:
            skipped += 1
            continue
        if session.exec(
            select(Entitlement).where(Entitlement.source_ref == o.id)
        ).first():
            already += 1
            continue
        if not _kind_for_plan(o.plan_key):
            skipped += 1
            skipped_kinds.append(o.plan_key)
            continue
        created += 1
        if not dry_run:
            grant_from_order(session, o)
    return {
        "paid_orders": len(orders),
        "created": created,
        "already": already,
        "skipped": skipped,
        "skipped_kinds": skipped_kinds,
        "dry_run": dry_run,
    }
