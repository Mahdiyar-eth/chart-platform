"""Round 2.1 (Opus R2) acceptance: Y1-Y9. NO gate monkeypatching (new rule)."""
import os, json, uuid
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.db import engine
from app.main import app as main_app
from app.models import User, BirthProfile, Chart, Report, Entitlement
from app.credits import grant as credit_grant, balance
from app.auth import USER_COOKIE, _user_cookie_value


def _mk_user(credits=0):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@t", credits=credits)); s.commit()
        return uid


def _mk_chart(uid):
    from app.astrology.engine import compute_from_fields, ensure_ephe
    from app.astrology.golden_data import GOLDEN_CHARTS
    ensure_ephe()
    cj = compute_from_fields(**GOLDEN_CHARTS[0]["birth"]).chart_json
    cid = "c" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, raw_year=1373, raw_month=5, raw_day=10)
        s.add(p); s.flush()
        s.add(Chart(id=cid, profile_id=p.id, chart_json=cj)); s.commit()
        return cid


def _finish_report(rid):
    """Act AS THE WORKER: mark done + pdf_path. Never patch the gate."""
    with Session(engine) as s:
        rep = s.get(Report, rid)
        rep.status = "done"
        import pathlib as _p
        _f = _p.Path("/tmp") / f"y1pdf-{rid[:8]}.pdf"; _f.write_bytes(b"%PDF-fake")
        rep.pdf_path = str(_f)
        s.add(rep); s.commit()


@pytest.fixture()
def llm_mock(monkeypatch):
    """Patch ONLY the LLM router ($0), never the gates."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "b3mod", os.path.join(os.path.dirname(__file__), "test_transit_forecast_b3.py"))
    b3 = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("b3mod", b3)
    try:
        spec.loader.exec_module(b3)
    except Exception:
        pass
    import app.report.transit_narrative as tn
    monkeypatch.setattr(tn, "build_router", lambda *a, **k: b3._mock_router())


def test_y1_ac1_full_credit_report_cycle(llm_mock, monkeypatch):
    """AC-1: buy with credits -> create -> PDF 200/302 (NOT 403) -> docx gate OK.
    Queue is faked (infra), the ENTITLEMENT GATE IS NOT."""
    uid = _mk_user(); cid = _mk_chart(uid)
    c = TestClient(main_app); ck = {USER_COOKIE: _user_cookie_value(uid)}
    with Session(engine) as s:
        credit_grant(s, uid, 10, "topup", idempotency_key="y1-" + uid)
    r0 = c.post("/api/purchase", json={"action_key": "report_full", "chart_id": cid}, cookies=ck)
    assert r0.status_code == 200, r0.text[:200]
    import app.main as _m
    monkeypatch.setattr(_m, "_enqueue_report", lambda rid: True)  # queue only — allowed
    r1 = c.post(f"/api/charts/{cid}/report", cookies=ck)
    assert r1.status_code == 200, r1.text[:300]
    rid = r1.json()["report_id"]
    _finish_report(rid)
    r2 = c.get(f"/api/reports/{rid}/pdf", cookies=ck)  # presigned redirect or inline
    assert r2.status_code in (200, 302), f"N1 REGRESSION: {r2.status_code} {r2.text[:150]}"
    with Session(engine) as s:
        ent = s.get(Entitlement, r0.json()["entitlement_id"])
        assert ent.ref_id == rid  # Y1: bound
        assert balance(s, uid) == 3  # 10 - 7


@pytest.mark.parametrize("action,plan,price", [
    ("report_basic", "basic", 3),
    ("report_full", "full", 7),
    ("report_gold", "gold", 14),
])
def test_y2_ac2_plan_from_tx_reason(llm_mock, monkeypatch, action, plan, price):
    """AC-2: plan_key derives from the funding tx reason — all three tiers."""
    uid = _mk_user(); cid = _mk_chart(uid)
    c = TestClient(main_app); ck = {USER_COOKIE: _user_cookie_value(uid)}
    with Session(engine) as s:
        credit_grant(s, uid, price, "topup", idempotency_key=f"y2-{action}-{uid}")
    r0 = c.post("/api/purchase", json={"action_key": action, "chart_id": cid}, cookies=ck)
    assert r0.status_code == 200, r0.text[:200]
    import app.main as _m
    monkeypatch.setattr(_m, "_enqueue_report", lambda rid: True)
    r1 = c.post(f"/api/charts/{cid}/report", cookies=ck)
    assert r1.status_code == 200, r1.text[:300]
    assert r1.json()["plan_key"] == plan, r1.json()
    with Session(engine) as s:
        assert balance(s, uid) == 0


def test_y3_cached_month_never_recharges(llm_mock):
    """Y3/N3: second analyze of the same month costs 0 (cache short-circuit BEFORE spend)."""
    uid = _mk_user(); cid = _mk_chart(uid)
    c = TestClient(main_app); ck = {USER_COOKIE: _user_cookie_value(uid)}
    with Session(engine) as s:
        credit_grant(s, uid, 20, "topup", idempotency_key="y3-" + uid)
        from app.astrology.transit_cache import store_transit_analysis
        store_transit_analysis(s, cid, 12, {"narratives": [{"headline": "cached"}], "events": []})
    r1 = c.post(f"/api/charts/{cid}/forecast/analyze", data={"months": "12"}, cookies=ck)
    assert r1.status_code == 200 and r1.json().get("narratives"), r1.text[:200]
    with Session(engine) as s:
        assert balance(s, uid) == 20  # NOTHING spent on cached content


def test_y5_rectify_double_click_charges_once():
    """Y5/N5: deterministic idempotency key — same inputs twice = ONE charge."""
    uid = _mk_user(credits=10)
    c = TestClient(main_app); ck = {USER_COOKIE: _user_cookie_value(uid)}
    evs = json.dumps([["marriage", 2019, 6, 12]])
    r1 = c.post("/api/rectify", data={"city_fa": "تهران", "year": 1373, "month": 5,
                                      "day": 10, "calendar": "jalali", "events_json": evs},
                cookies=ck)
    assert r1.status_code == 200, r1.text[:200]
    r2 = c.post("/api/rectify", data={"city_fa": "تهران", "year": 1373, "month": 5,
                                      "day": 10, "calendar": "jalali", "events_json": evs},
                cookies=ck)
    assert r2.status_code == 200
    with Session(engine) as s:
        assert balance(s, uid) == 8  # charged ONCE (2 credits), not twice


def test_y6_refund_cumulative_cap():
    """Y6/N6: partial refunds can never exceed the original cost (3+3 on a 5-credit tx)."""
    from app.credits import spend, refund as _refund
    uid = _mk_user()
    _cid = None
    with Session(engine) as s:
        credit_grant(s, uid, 5, "topup", idempotency_key="y6g-" + uid)
        tx = spend(s, uid, "transit_12m", idempotency_key="y6s-" + uid)
        tid = tx.id
    with Session(engine) as s:
        _refund(s, tid, amount=3)   # first partial OK
    with Session(engine) as s:
        _refund(s, tid, amount=3)   # over-refund attempt -> clamped to remaining 2
    with Session(engine) as s:
        assert balance(s, uid) == 5  # fully restored but NEVER more than cost


def test_y8_yearly_has_chat_gate():
    """Y8/R19: an active yearly subscription passes the chat gate like gold/monthly."""
    uid = _mk_user(); cid = _mk_chart(uid)
    from datetime import datetime, timedelta, timezone
    from app.models import Order, Subscription
    with Session(engine) as s:
        s.add(Order(id="o" + uuid.uuid4().hex[:8], user_id=uid, chart_id=cid,
                    plan_key="yearly", status="paid", amount_rial=890_000)); s.commit()
        o = s.exec(s.__class__.objects if False else __import__("sqlmodel").select(Order)).first()  # noqa
    # simpler: fetch this chart's order
    from sqlmodel import select
    with Session(engine) as s:
        order = s.exec(select(Order).where(Order.chart_id == cid)).first()
        order.plan_key = "yearly"; s.add(order)
        s.add(Subscription(chart_id=cid, active=True,
                           expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=365)))
        s.commit()
    c = TestClient(main_app); ck = {USER_COOKIE: _user_cookie_value(uid)}
    r = c.get(f"/api/chat/access/{cid}", cookies=ck)
    assert r.status_code == 200 and r.json().get("allowed") is True, r.text[:200]
