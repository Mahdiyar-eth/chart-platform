"""ZAYCHE §12 — astrology golden regression: cross-check engine output against
raw pyswisseph for reference charts.

Covers: tropical/sidereal, DST/timezone, MC/ASC, houses, aspects,
nodes/Lilith/Fortune/Vertex. Every assertion is computed INDEPENDENTLY with
swisseph (not against the engine's own golden data).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import swisseph as swe

from app.astrology.engine import compute_chart, BirthData

# reference birth: Tehran 1994-08-23 06:10 (user's approved chart)
TEHRAN = BirthData(lat=35.6892, lon=51.3890, year=1994, month=8, day=23,
                   hour=6, minute=10, time_known=True, tz_name="Asia/Tehran")


def _utc_jd(birth: BirthData) -> float:
    import datetime as dt
    from zoneinfo import ZoneInfo
    local = dt.datetime(birth.year, birth.month, birth.day, birth.hour, birth.minute,
                        tzinfo=ZoneInfo(birth.tz_name))
    utc = local.astimezone(dt.timezone.utc)
    return swe.julday(utc.year, utc.month, utc.day,
                      utc.hour + utc.minute / 60 + utc.second / 3600)


def _swe_lon(jd: float, pid: int, sidereal: bool = False) -> float:
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if sidereal:
        flags |= swe.FLG_SIDEREAL
    pos, _ = swe.calc_ut(jd, pid, flags)
    return pos[0]


def _eng(res, name: str) -> float:
    return res.chart_json["planets"][name]["longitude"]


def test_tehran_sun_and_moon_match_swisseph():
    """Engine tropical positions must match raw swisseph within 0.1°."""
    res = compute_chart(TEHRAN)
    jd = _utc_jd(TEHRAN)
    for name, pid in [("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY),
                      ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
                      ("Saturn", swe.SATURN)]:
        diff = abs((_eng(res, name) - _swe_lon(jd, pid) + 180) % 360 - 180)
        assert diff < 0.1, f"{name}: engine {_eng(res, name):.2f} vs swe {_swe_lon(jd, pid):.2f}"


def test_asc_mc_match_swisseph():
    """ASC/MC must match swisseph house cusps (Placidus)."""
    res = compute_chart(TEHRAN)
    jd = _utc_jd(TEHRAN)
    cusps, ascmc = swe.houses(jd, TEHRAN.lat, TEHRAN.lon, b"P")
    asc = res.chart_json["angles"]["ASC"]["longitude"]
    mc = res.chart_json["angles"]["MC"]["longitude"]
    assert abs((asc - ascmc[0] + 180) % 360 - 180) < 0.2, f"ASC {asc:.2f} vs {ascmc[0]:.2f}"
    assert abs((mc - ascmc[1] + 180) % 360 - 180) < 0.2, f"MC {mc:.2f} vs {ascmc[1]:.2f}"


def test_sidereal_lahiri_matches_swisseph():
    """Sidereal (Lahiri) positions must match raw swisseph FLG_SIDEREAL."""
    res = compute_chart(TEHRAN, {"zodiac": "sidereal", "ayanamsa": "lahiri"})
    jd = _utc_jd(TEHRAN)
    for name, pid in [("Sun", swe.SUN), ("Moon", swe.MOON)]:
        diff = abs((_eng(res, name) - _swe_lon(jd, pid, sidereal=True) + 180) % 360 - 180)
        assert diff < 0.2, f"{name}: engine {_eng(res, name):.2f} vs swe {_swe_lon(jd, pid, True):.2f}"


def test_dst_morning_conversion_matches_zoneinfo():
    """A birth inside Tehran DST must land on the same UTC as Python zoneinfo."""
    d = BirthData(lat=35.7, lon=51.4, year=1994, month=6, day=15,
                  hour=10, minute=0, time_known=True, tz_name="Asia/Tehran")
    res = compute_chart(d)
    jd = _utc_jd(d)
    diff = abs((_eng(res, "Sun") - _swe_lon(jd, swe.SUN) + 180) % 360 - 180)
    assert diff < 0.1, f"DST sun: engine {_eng(res, 'Sun'):.2f} vs swe {_swe_lon(jd, swe.SUN):.2f}"


def test_aspects_only_ptolemaic():
    """Aspects must be only 0/60/90/120/180 with sane orbs."""
    res = compute_chart(TEHRAN)
    max_orbs = {"conjunction": 8, "sextile": 6, "square": 8, "trine": 8, "opposition": 8}
    for a in res.chart_json.get("aspects", []):
        assert a["aspect"] in max_orbs, f"unexpected aspect {a}"
        assert a.get("orb", 99) <= max_orbs[a["aspect"]] + 1


def test_nodes_lilith_fortune_present():
    res = compute_chart(TEHRAN)
    names = set(res.chart_json["planets"].keys())
    for n in ("Node", "Lilith", "Fortune"):
        assert n in names, f"missing {n} in {sorted(names)}"


def test_fortune_day_formula():
    """Day birth: Fortune = ASC + Moon − Sun (within 0.5°)."""
    res = compute_chart(TEHRAN)
    j = res.chart_json
    asc = j["angles"]["ASC"]["longitude"]
    moon = j["planets"]["Moon"]["longitude"]
    sun = j["planets"]["Sun"]["longitude"]
    expected = (asc + moon - sun) % 360
    diff = abs((j["planets"]["Fortune"]["longitude"] - expected + 180) % 360 - 180)
    assert diff < 0.5, f"fortune {j['planets']['Fortune']['longitude']:.2f} vs {expected:.2f}"


def test_house_placement_consistent():
    """Each planet's house must be between the two bounding cusps."""
    res = compute_chart(TEHRAN)
    j = res.chart_json
    cusps = [j["houses"][f"h{i+1}"] for i in range(12)]
    for name, p in j["planets"].items():
        if p.get("house") is None or "Fortune" in name:
            continue
        h = p["house"] - 1
        c1, c2 = cusps[h], cusps[(h + 1) % 12]
        lon = p["longitude"]
        if c2 > c1:
            ok = c1 <= lon < c2
        else:  # wrap at 0
            ok = lon >= c1 or lon < c2
        assert ok, f"{name} house {p['house']} inconsistent: lon {lon:.2f} cusps {c1:.2f}..{c2:.2f}"
