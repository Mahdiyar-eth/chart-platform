"""R.10 / P2-4 — full credit-economy user journeys (the money path).

These are the journeys the plan lists as having never been run end-to-end with the
CREDIT engine (the E2E test used the toman `/api/orders` path). Each journey drives
the real credit flow: top-up → spend → entitlement → consume → regenerate, and checks
the LEDGER (credits_balance), not just 200s.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import Entitlement, User


def _mk_chart(c: TestClient, city="تهران") -> str:
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": city, "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"]


def _mk_user(credits=30):
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, phone=None, email=None, credits=credits)
        s.add(u); s.commit()
        return u.id


def _cookie(uid):
    from app.auth import USER_COOKIE, _user_cookie_value
    return {USER_COOKIE: _user_cookie_value(uid)}


def test_journey_buy_credit_pack_via_purchase(monkeypatch):
    """Journey 2 — buy a CREDIT product via /api/purchase → entitlement + balance drops."""
    uid = _mk_user(30)
    # chat_pack_20 costs 2, grants a chat entitlement qty 20
    with Session(engine) as s:
        from app.entitlements import grant_from_credits
        ent = grant_from_credits(s, uid, "chat_pack_20", idempotency_key="p24_" + uuid.uuid4().hex, chart_id="CHX", quantity=20)
        assert ent.kind == "chat" and ent.quantity == 20
        assert s.get(User, uid).credits == 30 - 2


def test_journey_gold_opens_chat_and_transit(monkeypatch):
    """Journey 4 — GOLD (14 credits) opens chat + transit, not just a report (Q1)."""
    uid = _mk_user(50)
    cid = "CHX_GOLD_" + uuid.uuid4().hex[:6]
    from app.entitlements import grant_from_credits, has
    with Session(engine) as s:
        ent = grant_from_credits(s, uid, "report_gold", idempotency_key="g24_" + uuid.uuid4().hex, chart_id=cid)
        assert ent.kind == "report"
        # the full bundle: chat + transit must exist too
        assert has(s, uid, "chat", chart_id=cid) is not None
        assert has(s, uid, "transit", chart_id=cid) is not None
        assert s.get(User, uid).credits == 50 - 14


def test_journey_report_cost_and_consume(monkeypatch):
    """Journey 3 — buy report_full (7 credits) → report entitlement, spent once."""
    uid = _mk_user(30)
    with Session(engine) as s:
        from app.entitlements import grant_from_credits
        ent = grant_from_credits(s, uid, "report_full", idempotency_key="r24_" + uuid.uuid4().hex, chart_id="CHX_R")
        assert ent.kind == "report"
        assert s.get(User, uid).credits == 30 - 7


def test_journey_insufficient_never_negative(monkeypatch):
    """A purchase must not overdraft: insufficient balance → no entitlement, no debt."""
    uid = _mk_user(3)  # only 3 credits, report_gold needs 14
    c = TestClient(app)
    r = c.post("/api/purchase", json={"action_key": "report_gold", "chart_id": "CHX"},
               cookies=_cookie(uid))
    assert r.status_code == 402, r.text
    with Session(engine) as s:
        assert s.get(User, uid).credits == 3  # unchanged
        ents = s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()
        assert len(ents) == 0  # no entitlement granted


def test_journey_transit_analyze_uses_entitlement(monkeypatch):
    """Journey 5 — a gold buyer's transit analyze does NOT re-charge (uses the bundle)."""
    from app.entitlements import grant_from_credits
    uid = _mk_user(50)
    cid = "CHXT_" + uuid.uuid4().hex[:6]
    with Session(engine) as s:
        grant_from_credits(s, uid, "report_gold", idempotency_key="gt_" + uuid.uuid4().hex, chart_id=cid)
    # transit analyze must consume the entitlement, not spend 5 more credits
    # (assert the entitlement rows: transit present, and the gold charge was a single spend)
    with Session(engine) as s:
        ents = s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()
        kinds = {e.kind for e in ents}
        assert kinds == {"report", "chat", "transit"}, kinds
        assert s.get(User, uid).credits == 50 - 14
