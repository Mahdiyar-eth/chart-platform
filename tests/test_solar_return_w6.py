"""MASTER W6 (N2, AC-4) — چارت سالیانه (Solar Return).

AC-4: the Sun-return moment must be precise to <1 arc-minute (< 1 minute of
time — the golden test) and the product must carry 5 dated transits.
Gate: 9 credits, chart-scoped entitlement kind 'solar'.
"""
import json
import os
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import _user_cookie_value
from app.db import engine
from app.entitlements import grant_from_credits
from app.main import app as main_app
from app.models import BirthProfile, Chart, User
from app.report.solar import solar_return_for, sr_sections


def _natal() -> dict:
    from app.astrology.engine import compute_from_fields
    return compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def test_ac4_solar_return_moment_sub_arcminute():
    """GOLDEN TEST: returned Sun longitude == natal Sun longitude <1 arcmin."""
    natal = _natal()
    natal_sun = float(natal["planets"]["Sun"]["longitude"])
    sr = solar_return_for(natal, 35.6889, 51.3897, "Asia/Tehran",
                          when_local=datetime(2026, 8, 24, 12, 0))
    # the SR must be within the current solar year window
    assert sr.moment_utc.year == 2026
    assert sr.moment_utc.month in (8, 9), "SR for an Aug-23 birthday lands around late Aug"
    assert sr.error_arcmin < 1.0, f"precision {sr.error_arcmin} arcmin ≥ 1′"
    sec = sr_sections(sr, natal)
    assert len(sec["transits"]) == 5, "AC-4: exactly 5 dated key transits"
    for t in sec["transits"]:
        assert t["date"].count("-") == 2 and t["headline"]
    assert sec["theme"] and sec["mood"] and sec["seasonal_question"]


def test_w6_sr_chart_uses_current_location():
    """The SR chart is computed for the CURRENT location, not the birth place."""
    natal = _natal()
    # Vancouver vs Tehran: houses/ASC of the SR chart must differ
    sr_iran = solar_return_for(natal, 35.6889, 51.3897, "Asia/Tehran",
                               when_local=datetime(2026, 8, 24, 12, 0))
    sr_canada = solar_return_for(natal, 49.2827, -123.1207, "America/Vancouver",
                                 when_local=datetime(2026, 8, 24, 12, 0))
    a1 = sr_iran.chart_json["angles"]["ASC"]["longitude"]
    a2 = sr_canada.chart_json["angles"]["ASC"]["longitude"]
    assert abs(((a1 - a2 + 180) % 360) - 180) > 5, \
        "same instant at different places must yield different ASC"


def _flush_solar_cache(uid: str, cid: str) -> None:
    """Remove the permanent solar narrative cache for a clean gate check."""
    import hashlib
    key = f"solar:{hashlib.sha1(f'{uid}:35.6892:51.389:{datetime.now().year}'.encode()).hexdigest()[:16]}"
    try:
        import redis as _r
        _r.Redis.from_url("redis://127.0.0.1:6379/0").delete(key)
    except Exception:  # noqa: BLE001
        pass


def test_w6_gate_402_without_entitlement_then_200_with():
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@w6", credits=0)); s.commit()
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890)
        s.add(p); s.flush()
        ch = Chart(profile_id=p.id, chart_json=_natal(),
                   access_token="tok" + uuid.uuid4().hex[:12])
        s.add(ch); s.commit(); s.refresh(ch)
        cid = ch.id
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_user", _user_cookie_value(uid))

    # teaser is free
    rt = c.get(f"/api/solar/{cid}/teaser")
    assert rt.status_code == 200 and "precision_arcmin" in rt.json()

    # full report gated → 402 with price info
    r0 = c.get(f"/api/solar/{cid}")
    assert r0.status_code == 402, r0.text

    # buy with credits (ENRICH disabled → no LLM; deterministic sections only)
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u is not None
        u.credits = 20  # fund the wallet before the grant
        s.add(u); s.commit()
    grant_from_credits(Session(engine), uid, "solar_return",
                       idempotency_key="w6_" + uuid.uuid4().hex,
                       chart_id=cid)
    r1 = c.get(f"/api/solar/{cid}")
    assert r1.status_code == 200, r1.text
    d = r1.json()
    assert d["moment_utc"] and d["theme"] and len(d["transits"]) == 5
    # the deterministic sections must be brand-clean. The LLM narrative is
    # already FORBIDDEN_PATTERNS-gated at generation time (R.2 context-aware
    # policy allows benign negations), so the strict noun ban applies to the
    # engine-produced fields only.
    blob = json.dumps({k: v for k, v in d.items() if k != "narrative"},
                      ensure_ascii=False)
    for bad in ("فال", "شانس", "پیشگویی"):
        assert bad not in blob


def test_w6_purchase_endpoint_charges_and_grants(monkeypatch):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@w6b", credits=20)); s.commit()
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890)
        s.add(p); s.flush()
        ch = Chart(profile_id=p.id, chart_json=_natal(),
                   access_token="tok" + uuid.uuid4().hex[:12])
        s.add(ch); s.commit(); s.refresh(ch)
        cid = ch.id
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_user", _user_cookie_value(uid))
    fd = {"chart_id": cid}
    r = c.post("/api/solar/purchase", data=fd)
    assert r.status_code == 200 and r.json().get("ok"), r.text
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.credits == 11, f"9 credits must be deducted, got balance {u.credits}"
