"""A3 — entitlement layer. Gates check "does the user have an entitlement?"
instead of "does the user have a paid order?" Entitlements come from credits
(credit economy) OR from legacy paid orders (backfilled migration).

The critical rule: every gate must ALSO accept the legacy paid-order path so no
current customer loses access during the migration.
"""
from __future__ import annotations

from datetime import datetime, timezone

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
        chart_id: str | None = None, ref_id: str | None = None,
        unbound_only: bool = False) -> Entitlement | None:
    """Return the first usable entitlement for (user, kind [, chart]/[ref]).

    Never cross-chart/cross-ref: an entitlement for chart X is NOT valid for
    chart Y (closed per plan A3).

    Z5 (Opus R3): when `unbound_only=True`, skip entitlements already bound to
    a report (ref_id set) so an upgrade/second purchase picks the NEWLY bought
    entitlement instead of recycling the first one (which made the regenerate
    path bind nothing and inherit the WRONG tier/ref)."""
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
        if unbound_only and ent.ref_id is not None:
            continue  # already spent on a report — not the upgrade target
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
        "UPDATE entitlements SET used = used + :n WHERE id = :id "
        "AND used <= quantity - :n AND (expires_at IS NULL OR expires_at >= :now)"
    ), params={"n": n, "id": ent.id,
              "now": datetime.now(timezone.utc).replace(tzinfo=None)})
    if res.rowcount == 0:
        return False
    session.refresh(ent)
    return True


_QUANTITY_BY_ACTION = {"chat_pack_20": 20, "chat_pack_100": 100}


def _action_quantity(action_key: str) -> int:
    return _QUANTITY_BY_ACTION.get(action_key, 1)


# R.9 / Q1 (P1): a single purchase may grant MULTIPLE entitlement kinds. The
# catalogue sells "report_gold" as «گزارش ۱۳بخشه + چت ۳۰روزه + گذر ۱۲ماهه», but
# _kind_for_action collapsed it to just "report" — so a gold buyer (14 credits)
# got only what a full (7 credits) buyer got, and had to RE-pay for transit.
# This maps a credit action to the full set of kinds it unlocks.
_MULTI_KIND_BY_ACTION = {
    "report_gold": ["report", "chat", "transit"],
}

# Kind → lifetime (days) for the gold-bundle entitlements. chat is a 30-day pack
# (existing promise); transit in the gold bundle is the 12-month forecast.
_EXPIRY_DAYS = {"chat": 30}
_EXPIRY_DAYS_BY_KIND = _EXPIRY_DAYS  # alias (back-compat)


def _kinds_for_action(action_key: str) -> list[str]:
    """Kinds granted by a credit action — may be >1 (e.g. report_gold)."""
    multi = _MULTI_KIND_BY_ACTION.get(action_key)
    if multi:
        return multi
    return [_kind_for_action(action_key)]


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
    # R.9 / Q1: one action may grant several kinds (report_gold → report+chat+transit).
    kinds = _kinds_for_action(action_key)
    first = None
    for kind in kinds:
        existing = session.exec(
            select(Entitlement).where(
                Entitlement.source == "credit",
                Entitlement.source_ref == tx.id,
                Entitlement.kind == kind,
            )
        ).first()
        if existing:
            if first is None:
                first = existing
            continue
        # chat in a bundle is a 30-day pack; transit is the single 12-month analysis
        qty = _action_quantity(action_key) if quantity is None else quantity
        ent = Entitlement(
            user_id=user_id, kind=kind, chart_id=chart_id,
            ref_id=ref_id, quantity=qty, used=0,
            source="credit", source_ref=tx.id,
            expires_at=_expiry_for_kind(kind),  # chat=30d; report/transit=None
        )
        session.add(ent)
        if first is None:
            first = ent
    try:
        session.commit()  # X4/R6: credits decrement + entitlement(s) in ONE commit
    except Exception:
        session.rollback()
        raise
    if first is not None:
        session.refresh(first)
    return first


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
    # R.10 / P3-2: report_audio is an ADD-ON (kind "audio"), NOT a report. The
    # `report_` prefix below would otherwise collapse it to "report" — a buyer of
    # the audio add-on got report access instead (catalog↔delivery mismatch the
    # gate caught). Check the more-specific key first.
    if action_key == "report_audio":
        return "audio"
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
    # MASTER W6/W7/W8 — the three new products get their OWN kinds so each
    # purchase unlocks exactly what its title promises (catalog↔delivery).
    if action_key in ("solar_return",):
        return "solar"
    if action_key == "relocation":
        return "relocation"
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
        "yearly": "chat",
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
