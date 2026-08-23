"""A6 — entitlement backfill acceptance tests (hermetic, no LLM)."""
import os, uuid
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"]="1"

from sqlmodel import Session, select
from app.models import User, Order, Entitlement
from app.entitlements import backfill_entitlements
from app.db import engine


def _mk_user() -> str:
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, phone=None, email=None, credits=0)
        s.add(u); s.commit()
        return u.id


def _order(uid: str, plan: str, status: str = "paid") -> str:
    with Session(engine) as s:
        o = Order(id=uuid.uuid4().hex, user_id=uid, plan_key=plan, status=status,
                  chart_id=None, report_id=None, amount_rial=1000)
        s.add(o); s.commit()
        return o.id


def _ents_for(order_ids):
    with Session(engine) as s:
        if not order_ids:
            return []
        return s.exec(select(Entitlement).where(Entitlement.source_ref.in_(order_ids))).all()


def test_backfill_preserves_access_for_5_legacy_orders():
    uid = _mk_user()
    plans = {"basic": "report", "full": "report", "gold": "report",
             "synastry": "synastry", "monthly": "chat"}
    ids = {p: _order(uid, p, "paid") for p in plans}
    with Session(engine) as s:
        backfill_entitlements(s, dry_run=False)
    ents = _ents_for(list(ids.values()))
    assert len(ents) == 5, len(ents)
    kinds = {e.kind for e in ents}
    assert set(plans.values()) <= kinds, kinds


def test_backfill_idempotent_run_twice():
    uid = _mk_user()
    ids = [_order(uid, "gold", "paid"), _order(uid, "synastry", "paid")]
    with Session(engine) as s:
        _rep1 = backfill_entitlements(s, dry_run=False)
    n1 = len(_ents_for(ids))
    with Session(engine) as s:
        rep2 = backfill_entitlements(s, dry_run=False)
    n2 = len(_ents_for(ids))
    assert n1 == 2 and n2 == 2, (n1, n2)
    assert rep2["already"] >= 2, rep2


def test_backfill_skips_refunded_and_not_paid():
    uid = _mk_user()
    paid = _order(uid, "gold", "paid")
    refunded = _order(uid, "full", "refunded")
    pending = _order(uid, "basic", "pending")
    with Session(engine) as s:
        backfill_entitlements(s, dry_run=False)
    ents = _ents_for([paid, refunded, pending])
    assert len(ents) == 1 and ents[0].kind == "report", [(e.kind, e.source) for e in ents]