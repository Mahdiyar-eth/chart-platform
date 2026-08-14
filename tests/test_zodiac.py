"""Zodiac system (tropical/sidereal) — audit r3: choice must flow from form into
profile + engine_config, tropical stays the default."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlmodel import select
from app.main import app
from app.db import engine
from app.models import Chart, BirthProfile


def _mk_chart(client, zodiac):
    r = client.post("/api/charts", data={
        "calendar": "gregorian", "year": 1994, "month": 8, "day": 23,
        "time_known": "true", "hour": 6, "minute": 10,
        "city_fa": "تهران", "zodiac": zodiac,
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_default_zodiac_is_tropical():
    c = TestClient(app)
    d = _mk_chart(c, "tropical")
    assert d["engine_config"]["zodiac"] == "tropical"
    with engine.begin() as conn:
        prof = conn.execute(select(BirthProfile.zodiac).where(
            BirthProfile.id == d["profile_id"])).first()
    assert prof[0] == "tropical"


def test_sidereal_flows_into_profile_and_chart():
    c = TestClient(app)
    d = _mk_chart(c, "sidereal")
    assert d["engine_config"]["zodiac"] == "sidereal"
    with engine.begin() as conn:
        prof = conn.execute(select(BirthProfile.zodiac).where(
            BirthProfile.id == d["profile_id"])).first()
    assert prof[0] == "sidereal"


def test_invalid_zodiac_rejected():
    c = TestClient(app)
    r = c.post("/api/charts", data={
        "calendar": "gregorian", "year": 1994, "month": 8, "day": 23,
        "time_known": "true", "hour": 6, "minute": 10,
        "city_fa": "تهران", "zodiac": "weird",
    })
    assert r.status_code == 400
