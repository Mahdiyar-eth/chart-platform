"""A3 — entitlement layer acceptance tests (hermetic, no LLM)."""
import os, uuid
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
os.environ["CREATE_ALL_ON_BOOT"] = "1"
from sqlmodel import Session, select
from app.db import engine
from app.models import User, Entitlement, Order, CreditTransaction
from app.entitlements import has, consume, grant_from_credits, grant_from_order
from app.credits import get_price


def _mk_user(credits=0):
    with Session(engine) as s:
        u = User(email=f"e{uuid.uuid4().hex}@t.com", credits=credits)
        s.add(u); s.commit(); s.refresh(u)
        return u.id


def _ent(user_id, kind="report", chart_id=None, ref_id=None, quantity=1, used=0,
         source="credit", expires_at=None):
    e = Entitlement(user_id=user_id, kind=kind, chart_id=chart_id, ref_id=ref_id,
                    quantity=quantity, used=used, source=source, expires_at=expires_at)
    with Session(engine) as s:
        s.add(e); s.commit(); s.refresh(e)
        return e.id


def test_has_returns_matching_kind():
    uid = _mk_user()
    eid = _ent(uid, kind="report")
    with Session(engine) as s:
        assert has(s, uid, "report") is not None
        assert has(s, uid, "chat") is None   # different kind


def test_has_never_crosses_chart():
    uid = _mk_user()
    _ent(uid, kind="report", chart_id="CHART_A")
    with Session(engine) as s:
        # entitlement for chart A is NOT valid for chart B
        assert has(s, uid, "report", chart_id="CHART_B") is None
        assert has(s, uid, "report", chart_id="CHART_A") is not None


def test_has_ignores_exhausted_and_expired():
    from datetime import datetime, timedelta, timezone
    uid = _mk_user()
    _ent(uid, kind="chat", quantity=2, used=2)                  # exhausted
    _ent(uid, kind="transit", quantity=1, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    with Session(engine) as s:
        assert has(s, uid, "chat") is None
        assert has(s, uid, "transit") is None
    _ent(uid, kind="synastry", quantity=1)                       # usable
    with Session(engine) as s:
        assert has(s, uid, "synastry") is not None


def test_consume_decrements_until_exhausted():
    uid = _mk_user()
    eid = _ent(uid, kind="chat", quantity=2)
    with Session(engine) as s:
        ent = s.get(Entitlement, eid)
        assert consume(s, ent) is True
        assert consume(s, ent) is True
        assert consume(s, ent) is False      # exhausts after 2
        assert ent.used == 2


def test_grant_from_credits_spends_and_creates_entitlement():
    uid = _mk_user(50)
    with Session(engine) as s:
        ent = grant_from_credits(s, uid, "report_gold", idempotency_key="gc_" + uuid.uuid4().hex)
        assert ent.kind == "report"
        assert s.get(User, uid).credits == 50 - get_price(s, "report_gold")


def test_grant_from_credits_idempotent_same_key():
    uid = _mk_user(50)
    key = "idem_" + uuid.uuid4().hex
    with Session(engine) as s:
        e1 = grant_from_credits(s, uid, "report_gold", idempotency_key=key)
        e2 = grant_from_credits(s, uid, "report_gold", idempotency_key=key)
        assert e1.id == e2.id
        assert s.get(User, uid).credits == 50 - get_price(s, "report_gold")


def test_grant_from_credits_binds_ref_id_per_report():
    uid = _mk_user(50)
    with Session(engine) as s:
        ent = grant_from_credits(s, uid, "report_gold", idempotency_key="r_" + uuid.uuid4().hex,
                                 chart_id="CHX", ref_id="REP_A")
        assert ent.ref_id == "REP_A" and ent.chart_id == "CHX" and ent.kind == "report"


def test_has_per_report_never_crosses_ref():
    uid = _mk_user()
    _ent(uid, kind="report", ref_id="REP_A", chart_id="CHX")
    with Session(engine) as s:
        assert has(s, uid, "report", ref_id="REP_A") is not None
        # buying report A must NOT unlock report B (per-report decision)
        assert has(s, uid, "report", ref_id="REP_B") is None


def test_grant_from_credits_chat_quantity():
    uid = _mk_user(50)
    with Session(engine) as s:
        ent = grant_from_credits(s, uid, "chat_pack_20", idempotency_key="c_" + uuid.uuid4().hex,
                                 chart_id="CHX", quantity=20)
        assert ent.kind == "chat" and ent.quantity == 20
        assert s.get(User, uid).credits == 50 - get_price(s, "chat_pack_20")


def test_grant_from_order_legacy_compat():
    uid = _mk_user()
    with Session(engine) as s:
        o = Order(id=uuid.uuid4().hex, user_id=uid, plan_key="gold",
                  chart_id=None, status="paid", amount_rial=1000)
        s.add(o); s.commit(); s.refresh(o)
        ent = grant_from_order(s, o)
        assert ent is not None and ent.kind == "report"
        # idempotent
        assert grant_from_order(s, o).id == ent.id
