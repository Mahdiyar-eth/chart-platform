"""H0.1 (HARDENING): real timezone resolution — the ACTUAL /api/charts path
must derive IANA tz from coordinates (not hardcode Tehran), and the utc_time
must match an INDEPENDENT zoneinfo computation (incl. DST summer/winter)."""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

CITIES = [
    # (label, lat, lon, expected_tz)
    ("tehran", 35.6892, 51.3890, "Asia/Tehran"),
    ("istanbul", 41.0138, 28.9497, "Europe/Istanbul"),
    ("dubai", 25.2048, 55.2708, "Asia/Dubai"),
    ("london", 51.5074, -0.1278, "Europe/London"),
    ("newyork", 40.7128, -74.0060, "America/New_York"),
]

DATES = [
    # (label, local dt) — summer (DST) and winter
    ("summer", datetime(2024, 7, 10, 12, 30)),
    ("winter", datetime(2024, 1, 10, 12, 30)),
]


def _expected_utc(lat: float, lon: float, local: datetime) -> str:
    from app.astrology.cities_world import tz_from_coords
    tz = tz_from_coords(lat, lon)
    return local.replace(tzinfo=ZoneInfo(tz)).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")


@pytest.mark.parametrize("label,lat,lon,exp_tz", CITIES)
def test_real_api_path_uses_correct_tz(label, lat, lon, exp_tz):
    c = TestClient(app)
    r = c.post("/api/charts", data={
        "calendar": "gregorian", "year": 2024, "month": 7, "day": 10,
        "time_known": "true", "hour": 12, "minute": 30,
        "lat": str(lat), "lon": str(lon), "name": label,
    })
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    # the response now carries the tz used for the computation (H0.1)
    assert body["tz_name"] == exp_tz, (
        f"{label}: tz mismatch — got {body['tz_name']}"
    )
    assert body["utc"] == _expected_utc(lat, lon, DATES[0][1])


@pytest.mark.parametrize("label,lat,lon,exp_tz", CITIES)
def test_dst_shift_changes_utc_correctly(label, lat, lon, exp_tz):
    """Same local wall-clock time must produce DIFFERENT utc in summer vs winter
    for DST zones (london, newyork) and the same for non-DST (dubai, tehran)."""
    c = TestClient(app)
    utcs = []
    for _, local in DATES:
        r = c.post("/api/charts", data={
            "calendar": "gregorian", "year": local.year, "month": local.month,
            "day": local.day, "time_known": "true", "hour": local.hour,
            "minute": local.minute, "lat": str(lat), "lon": str(lon), "name": label,
        })
        assert r.status_code == 200, r.text[:200]
        utcs.append(r.json()["utc"])
    # compare OFFSETS (utc - local), not strings — dates differ summer vs winter
    offsets = []
    for (_, local), u in zip(DATES, utcs):
        utc_dt = datetime.strptime(u, "%Y-%m-%d %H:%M:%S")
        local_dt = datetime(local.year, local.month, local.day, local.hour, local.minute)
        offsets.append((local_dt - utc_dt).total_seconds() / 3600)
    if exp_tz in ("Europe/London", "America/New_York"):
        # DST zones: same wall-clock maps to a different UTC offset
        assert offsets[0] != offsets[1], f"{label}: DST not applied — {offsets}"
    else:
        # no DST (Turkey abolished it in 2016; UAE/Iran fixed offsets)
        assert offsets[0] == offsets[1], f"{label}: unexpected DST — {offsets}"
    assert utcs[0] == _expected_utc(lat, lon, DATES[0][1])
    assert utcs[1] == _expected_utc(lat, lon, DATES[1][1])


def test_city_search_returns_world_cities_with_tz():
    c = TestClient(app)
    r = c.get("/api/cities", params={"q": "استانبول"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert res and res[0]["tz"] == "Europe/Istanbul", res
    r2 = c.get("/api/cities", params={"q": "Istanbul"})
    assert r2.json()["results"] and r2.json()["results"][0]["tz"] == "Europe/Istanbul"


def test_city_pick_flow_uses_city_tz():
    """Form flow: user picks Istanbul from /api/cities → form submits its
    coords → chart computed with Europe/Istanbul (not Tehran)."""
    c = TestClient(app)
    city = c.get("/api/cities", params={"q": "Istanbul"}).json()["results"][0]
    r = c.post("/api/charts", data={
        "calendar": "gregorian", "year": 2024, "month": 7, "day": 10,
        "time_known": "true", "hour": 12, "minute": 30,
        "lat": str(city["lat"]), "lon": str(city["lon"]),
        "city_fa": city["city_fa"], "name": "test",
    })
    assert r.status_code == 200
    assert r.json()["tz_name"] == "Europe/Istanbul"


def test_manual_coords_fallback_tehran_when_lookup_fails(monkeypatch):
    """If the timezone lookup itself fails (offline/broken), chart computation
    must still work and fall back to Asia/Tehran (never crash)."""
    monkeypatch.setattr("app.astrology.cities_world._TF", None)

    def _boom(*a, **k):
        raise RuntimeError("lookup unavailable")

    import timezonefinder
    monkeypatch.setattr(timezonefinder, "TimezoneFinder", _boom)
    c = TestClient(app)
    r = c.post("/api/charts", data={
        "calendar": "gregorian", "year": 2024, "month": 7, "day": 10,
        "time_known": "true", "hour": 12, "minute": 30,
        "lat": "25.2048", "lon": "55.2708", "name": "dubai-no-tz",
    })
    assert r.status_code == 200, r.text[:200]
    assert r.json()["tz_name"] == "Asia/Tehran"
