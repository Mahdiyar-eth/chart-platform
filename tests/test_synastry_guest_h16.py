"""H1.6 rewritten for R14-D3 — the toman synastry order is retired.

Guest-person semantics now live on /api/synastry/charts (saves both charts,
B as guest, returns B's capability token) + /api/purchase(synastry_love|
synastry_work). The old /api/synastry/order must 410.
"""
import json
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import BirthProfile, Chart, User


def _mk_user_cookie(c: TestClient) -> str:
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@h16", credits=20)); s.commit()
    from app.auth import _user_cookie_value
    c.cookies.set("chart_user", _user_cookie_value(uid))
    return uid


def _syn_form() -> dict:
    return {
        "name_a": "الف", "year_a": "1373", "month_a": "6", "day_a": "1",
        "hour_a": "6", "minute_a": "10", "city_a": "تهران",
        "name_b": "ب", "year_b": "1369", "month_b": "3", "day_b": "15",
        "hour_b": "14", "minute_b": "30", "city_b": "اصفهان",
    }


def test_old_toman_order_endpoint_is_410():
    c = TestClient(app)
    _mk_user_cookie(c)
    r = c.post("/api/synastry/order", data=_syn_form())
    assert r.status_code == 410, r.text


def test_charts_endpoint_saves_person_b_as_guest_with_token():
    c = TestClient(app)
    _mk_user_cookie(c)
    r = c.post("/api/synastry/charts", data=_syn_form())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["token_b"] and len(d["token_b"]) >= 20
    with Session(engine) as s:
        cb = s.get(Chart, d["chart_b"])
        prof = s.get(BirthProfile, cb.profile_id)
        assert prof is not None and prof.user_id is None, "person B must be a guest"
        ca = s.get(Chart, d["chart_a"])
        assert ca.profile_id and s.get(BirthProfile, ca.profile_id).user_id is not None


def test_credit_purchase_then_full_variant_works_with_guest_token():
    """The full R14 path: charts → purchase love → full(love) 200."""
    c = TestClient(app)
    _mk_user_cookie(c)  # credits=20 — enough for an 8cr variant
    d = c.post("/api/synastry/charts", data=_syn_form()).json()
    ck = {"chart_access": json.dumps({d["chart_b"]: d["token_b"]})}
    c.cookies.update(ck)
    pr = c.post("/api/purchase", json={"action_key": "synastry_love",
                                       "chart_id": d["chart_a"]})
    assert pr.status_code == 200, pr.text
    fr = c.post("/api/synastry/full", data={"chart_a": d["chart_a"],
                                            "chart_b": d["chart_b"], "variant": "love"})
    assert fr.status_code == 200, fr.text
    j = fr.json()
    assert j["variant"] == "love" and "overall" in j
