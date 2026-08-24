"""MASTER W7 (N3, AC-5) — چارت مهاجرت (Relocation).

AC-5: two destination cities must produce DIFFERENT houses, a side-by-side
comparison, and the explicit disclaimer. Gate: 6 credits.
"""
import json
import os
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import _user_cookie_value
from app.db import engine
from app.entitlements import grant_from_credits
from app.main import app as main_app
from app.models import BirthProfile, Chart, User
from app.report.relocation import compare_cities, relocation_chart


def _natal() -> dict:
    from app.astrology.engine import compute_from_fields
    return compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


CITIES = [
    {"name_fa": "تورنتو", "lat": 43.6532, "lon": -79.3832},
    {"name_fa": "برلین", "lat": 52.5200, "lon": 13.4050},
    {"name_fa": "دبی", "lat": 25.2048, "lon": 55.2708},
]


def test_ac5_cities_produce_different_houses():
    natal = _natal()
    r_teh = relocation_chart(natal, 35.6889, 51.3897)
    r_tor = relocation_chart(natal, CITIES[0]["lat"], CITIES[0]["lon"])
    # birth place vs far destination → ASC must differ and houses must move
    assert r_teh["asc_sign_fa"] != r_tor["asc_sign_fa"]
    assert r_tor["changed_count"] > 0
    cmp = compare_cities(natal, CITIES)
    assert len(cmp["cities"]) == 3
    # at least two cities differ in dominant area or moved count
    sig = {(c["focus_area"], c["asc_sign_fa"]) for c in cmp["cities"]}
    assert len(sig) >= 2, f"cities look identical: {sig}"
    # side-by-side fields + disclaimer present
    for c in cmp["cities"]:
        assert c["city"] and c["focus_area"]
    assert "توصیهٔ مهاجرت" in cmp["disclaimer"], "the explicit disclaimer is mandatory"


def test_w7_planets_keep_signs_but_houses_move():
    """Relocation moves HOUSES; planet SIGNS stay identical (time unchanged)."""
    natal = _natal()
    rc = relocation_chart(natal, CITIES[0]["lat"], CITIES[0]["lon"])
    for name, p in natal["planets"].items():
        if name in rc["moved"]:
            assert rc["moved"][name]["sign_fa"] == p.get("sign_fa"), \
                "planet signs must NOT change under relocation"


def test_w7_gate_and_full_flow(monkeypatch):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@w7", credits=20)); s.commit()
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
    cities = json.dumps(CITIES[:2], ensure_ascii=False)

    # gated → 402
    r0 = c.get(f"/api/relocation/{cid}?cities_json={cities}")
    assert r0.status_code == 402, r0.text
    # purchase charges exactly 6
    rp = c.post("/api/relocation/purchase", data={"chart_id": cid})
    assert rp.status_code == 200 and rp.json().get("ok")
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.credits == 14, f"expected 20-6=14, got {u.credits}"
    # now the comparison works
    r1 = c.get(f"/api/relocation/{cid}?cities_json={cities}")
    assert r1.status_code == 200, r1.text
    d = r1.json()
    assert len(d["cities"]) == 2 and d["disclaimer"]
    blob = json.dumps(d, ensure_ascii=False)
    for bad in ("فال", "شانس", "پیشگویی"):
        assert bad not in blob


def test_w7_rejects_more_than_three_cities():
    natal = _natal()
    many = CITIES + [{"name_fa": "اکسترا", "lat": 1.0, "lon": 2.0}]
    cmp = compare_cities(natal, many)
    assert len(cmp["cities"]) <= 3
