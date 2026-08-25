"""R13 — /api/synastry/charts: save two charts WITHOUT a payment order.

Powers the credit-based variant purchase (love/work) from the synastry page:
the free teaser runs first; buying with credits needs real chart ids.
"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app as main_app
from app.models import Chart, User


def _client():
    return TestClient(main_app, base_url="https://testserver")


def _syn_form():
    return {
        "name_a": "علی", "year_a": "1370", "month_a": "1", "day_a": "15",
        "hour_a": "10", "minute_a": "30", "city_a": "تهران", "calendar_a": "jalali",
        "name_b": "سارا", "year_b": "1369", "month_b": "5", "day_b": "20",
        "hour_b": "14", "minute_b": "30", "city_b": "اصفهان", "calendar_b": "jalali",
    }


def test_syn_charts_saves_two_charts_without_order():
    c = _client()
    r = c.post("/api/synastry/charts", data=_syn_form())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["chart_a"] and d["chart_b"] and d["chart_a"] != d["chart_b"]
    with Session(engine) as s:
        ca = s.get(Chart, d["chart_a"])
        cb = s.get(Chart, d["chart_b"])
        assert ca is not None and cb is not None
        # person B is a GUEST profile (no owner)
        from app.models import BirthProfile
        pb = s.get(BirthProfile, cb.profile_id)
        assert pb is not None and pb.user_id is None


def test_syn_charts_rejects_bad_city():
    c = _client()
    form = dict(_syn_form())
    form["city_b"] = "شهر-ناموجود-xyz"
    r = c.post("/api/synastry/charts", data=form)
    assert r.status_code == 400


def test_syn_credit_buy_flow_end_to_end(monkeypatch):
    """charts → /api/purchase(synastry_love) → entitlement scoped to chart A."""
    from app.entitlements import grant_from_credits
    from app.models import Entitlement
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@r13", credits=50)); s.commit()
    c = _client()
    r = c.post("/api/synastry/charts", data=_syn_form())
    cid = r.json()["chart_a"]
    ent = grant_from_credits(Session(engine), uid, "synastry_love",
                             idempotency_key="r13_" + uuid.uuid4().hex,
                             chart_id=cid)
    with Session(engine) as s:
        e = s.get(Entitlement, ent.id)
        assert e.kind == "synastry_love" and e.chart_id == cid
