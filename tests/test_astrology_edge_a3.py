"""ZAYCHE A3 (FINAL-LAUNCH-EXECUTION-PLAN): astrology edge cases —
midnight, date transitions, DST boundaries — cross-checked against raw
pyswisseph, deterministic and reproducible.

Baseline (already green): tests/test_astrology_golden_s12.py (tropical/
sidereal/DST/timezone/MC/ASC/houses/aspects/nodes/Lilith/Fortune).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["APP_ENV"] = "development"

import swisseph as swe  # noqa: E402
import pytest  # noqa: E402

from app.astrology.engine import BirthData, compute_chart  # noqa: E402

swe.set_ephe_path("/usr/share/swisseph")


def _bd(**kw) -> BirthData:
    base = dict(lat=35.689, lon=51.389, year=1994, month=8, day=23,
                hour=6, minute=10, tz_name="Asia/Tehran")
    base.update(kw)
    return BirthData(**base)


def _crosscheck(birth: BirthData, sidereal: bool = False) -> tuple[dict, dict]:
    app_chart = compute_chart(birth, {"zodiac": "sidereal"} if sidereal else None)
    local = birth.local_dt()
    import datetime as _dt
    from zoneinfo import ZoneInfo
    utc = local.replace(tzinfo=ZoneInfo(birth.tz_name)).astimezone(ZoneInfo("UTC"))
    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60.0)
    flag = swe.FLG_SWIEPH | swe.FLG_MOSEPH
    if sidereal:
        flag |= swe.FLG_SIDEREAL
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    pos = {}
    for planet in (swe.SUN, swe.MOON):
        p, _ = swe.calc_ut(jd, planet, flag)
        pos[planet] = p[0]
    return app_chart.chart_json, pos


EDGE_BIRTHS = [
    ("midnight-exact", _bd(hour=0, minute=0)),
    ("midnight-2359", _bd(day=22, hour=23, minute=59)),
    ("new-year-midnight", _bd(year=2000, month=1, day=1, hour=0, minute=1,
                              lat=51.507, lon=-0.128, tz_name="Europe/London")),
    ("leap-feb29", _bd(year=2024, month=2, day=29, hour=12, minute=30)),
    ("dst-spring-gap", _bd(year=2024, month=3, day=31, hour=2, minute=30,
                           lat=51.507, lon=-0.128, tz_name="Europe/London")),
    ("dst-fall-overlap", _bd(year=2024, month=10, day=27, hour=1, minute=30,
                             lat=51.507, lon=-0.128, tz_name="Europe/London")),
    ("tehran-dst-1403", _bd(year=2025, month=3, day=22, hour=0, minute=15)),
    ("southern-hemi", _bd(year=1990, month=7, day=15, hour=10, minute=0,
                          lat=-33.868, lon=151.209, tz_name="Australia/Sydney")),
    ("date-line-west", _bd(lat=21.307, lon=-157.858, tz_name="Pacific/Honolulu")),
    ("sidereal-lahiri", _bd()),
]


@pytest.mark.parametrize("label,birth", EDGE_BIRTHS, ids=[b[0] for b in EDGE_BIRTHS])
def test_edge_births_deterministic_and_consistent(label: str, birth: BirthData):
    sid = label == "sidereal-lahiri"
    c1 = compute_chart(birth, {"zodiac": "sidereal"} if sid else None).chart_json
    c2 = compute_chart(birth, {"zodiac": "sidereal"} if sid else None).chart_json
    assert c1["planets"]["Sun"]["longitude"] == c2["planets"]["Sun"]["longitude"]
    assert c1["angles"]["ASC"]["longitude"] == c2["angles"]["ASC"]["longitude"]
    for name, p in c1["planets"].items():
        assert "longitude" in p and "house" in p, f"{label}: {name} missing lon/house"
    assert len(c1["houses"]) == 12 and all(f"h{i}" in c1["houses"] for i in range(1, 13)), \
        f"{label}: houses != 12"


@pytest.mark.parametrize("label,birth", EDGE_BIRTHS, ids=[b[0] for b in EDGE_BIRTHS])
def test_edge_births_crosscheck_raw_swisseph(label: str, birth: BirthData):
    sid = label == "sidereal-lahiri"
    app_chart, raw = _crosscheck(birth, sidereal=sid)
    sun_app = app_chart["planets"]["Sun"]["longitude"]
    moon_app = app_chart["planets"]["Moon"]["longitude"]
    d_sun = abs(sun_app - raw[swe.SUN]) % 360
    d_moon = abs(moon_app - raw[swe.MOON]) % 360
    assert min(d_sun, 360 - d_sun) <= 0.1, f"{label}: Sun off (app={sun_app:.4f} raw={raw[swe.SUN]:.4f})"
    assert min(d_moon, 360 - d_moon) <= 0.1, f"{label}: Moon off (app={moon_app:.4f} raw={raw[swe.MOON]:.4f})"


def test_midnight_never_shifts_date_backward():
    late = compute_chart(_bd(day=22, hour=23, minute=59)).chart_json
    early = compute_chart(_bd(day=23, hour=0, minute=1)).chart_json
    m1 = late["planets"]["Moon"]["longitude"]
    m2 = early["planets"]["Moon"]["longitude"]
    step = (m2 - m1) % 360
    assert 0 < step < 1.5, f"Moon jumped {step:.3f}° across midnight"
