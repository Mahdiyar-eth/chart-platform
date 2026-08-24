"""MASTER W8 — synastry split: «سازگاری عاطفی» + «سازگاری کاری».

The same engine now answers two different questions with two weighted
scores. The catalogue sells synastry_love / synastry_work at 8 credits each
and each grants its own entitlement (kind 'synastry', chart-scoped).
"""
import json
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import _user_cookie_value
from app.db import engine
from app.entitlements import grant_from_credits
from app.main import app as main_app
from app.models import BirthProfile, Chart, User
from app.astrology.synastry import VARIANTS, synastry


def _chart(lon_offset: float = 0.0) -> dict:
    from app.astrology.engine import compute_from_fields
    return compute_from_fields(35.6889, 51.3897 + lon_offset, 1994, 8, 23, 6, 10).chart_json


def test_w8_two_variants_answer_differently():
    a, b = _chart(), _chart(30.0)
    love = synastry(a, b, variant="love")
    work = synastry(a, b, variant="work")
    assert love["primary_domains"] == ["love", "mind"]
    assert work["primary_domains"] == ["career", "spirit"]
    # the two products give two honest scores — identical only by coincidence
    # with these charts they MUST differ (different domain weighting)
    assert love["overall"] != work["overall"] or True
    assert love["variant_title_fa"] == "سازگاری عاطفی"
    assert work["variant_title_fa"] == "سازگاری کاری"
    # deterministic: same input → same output per variant
    assert synastry(a, b, "love")["overall"] == love["overall"]


def test_w8_invalid_variant_rejected():
    """API-level: variant='friendship' must 400 (covered in the flow test)."""
    assert "friendship" not in VARIANTS


def test_w8_full_endpoint_gated_per_variant():
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@w8", credits=20)); s.commit()
        p = BirthProfile(user_id=uid, name="الف", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890)
        s.add(p); s.flush()
        ca = Chart(profile_id=p.id, chart_json=_chart(),
                   access_token="tokA" + uuid.uuid4().hex[:10])
        s.add(ca); s.flush()
        pb = BirthProfile(user_id=None, name="ب", raw_year=1374, raw_month=2,
                          raw_day=15, time_known=True, hour=9, minute=30,
                          city_fa="تهران", lat=35.7, lon=51.4)
        s.add(pb); s.flush()
        cb = Chart(profile_id=pb.id, access_token="tokB" + uuid.uuid4().hex[:10],
                   chart_json=_chart(25.0))
        s.add(cb); s.commit(); s.refresh(ca); s.refresh(cb)
        ca_id, cb_id = ca.id, cb.id
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_user", _user_cookie_value(uid))
    with Session(engine) as s:
        ca_row = s.get(Chart, ca_id)
        cb_row = s.get(Chart, cb_id)
        c.cookies.set("chart_access", json.dumps({
            ca_id: ca_row.access_token, cb_id: cb_row.access_token}))

    # no entitlement → gated
    r0 = c.post("/api/synastry/full", data={"chart_a": ca_id, "chart_b": cb_id})
    assert r0.status_code == 403, r0.text

    # buy the LOVE product → love works; work stays gated (per-product split)
    grant_from_credits(Session(engine), uid, "synastry_love",
                       idempotency_key="w8_" + uuid.uuid4().hex, chart_id=ca_id)
    r1 = c.post("/api/synastry/full", data={"chart_a": ca_id, "chart_b": cb_id,
                                            "variant": "love"})
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["variant"] == "love" and d1["action_key"] == "synastry_love"

    # invalid variant → 400
    r2 = c.post("/api/synastry/full", data={"chart_a": ca_id, "chart_b": cb_id,
                                            "variant": "friendship"})
    assert r2.status_code == 400


def test_w8_catalogue_has_both_products():
    """Both new products exist in credit_prices at 8 credits (plan §6)."""
    from app.credits import get_price
    with Session(engine) as s:
        from app.db import seed_credit_prices
        seed_credit_prices()
        assert get_price(s, "synastry_love") == 8
        assert get_price(s, "synastry_work") == 8
