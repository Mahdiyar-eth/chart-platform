"""Golden chart test suite — every engine change must pass these (plan v3.1 §5.4).

Run: venv/bin/python -m pytest tests/test_golden_charts.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.astrology.engine import compute_from_fields, fmt_lon
from app.astrology.golden_data import GOLDEN_CHARTS

TOLERANCE = 1 / 60.0  # 1 arc-minute


def _chart(g):
    # audit r3: pass the chart's own zodiac system (tropical|sidereal)
    zodiac = (g.get("engine_config") or {}).get("zodiac", "tropical")
    return compute_from_fields(**g["birth"], zodiac=zodiac)


def test_golden_count():
    assert len(GOLDEN_CHARTS) >= 8, "Golden suite must have at least 8 charts"


@pytest.mark.parametrize("g", GOLDEN_CHARTS, ids=[g["id"] for g in GOLDEN_CHARTS])
def test_chart_computes(g):
    c = _chart(g).chart_json
    assert c["engine_config"]["zodiac"] == (g.get("engine_config") or {}).get("zodiac", "tropical")
    assert len(c["planets"]) >= 13  # 10 planets + node + lilith + chiron + fortune
    if g["birth"].get("time_known", True):
        # audit P0: houses/angles ONLY exist when birth time is known
        assert len(c["houses"]) == 12
        assert "ASC" in c["angles"]
        assert "Fortune" in c["planets"]
    else:
        assert c["houses"] == {}
        assert c["angles"] == {}
        assert "Fortune" not in c["planets"]
    assert c["birth"]["julian_day_ut"] > 0


@pytest.mark.parametrize("g", GOLDEN_CHARTS, ids=[g["id"] for g in GOLDEN_CHARTS])
def test_utc_conversion(g):
    """zoneinfo must produce the expected UTC for every DST era (no manual tables)."""
    if "verify_utc" not in g.get("expected", {}):
        pytest.skip("no UTC expectation")
    c = _chart(g).chart_json
    assert c["birth"]["utc_time"] == g["expected"]["verify_utc"], (
        f"UTC mismatch: {c['birth']['utc_time']} != {g['expected']['verify_utc']}"
    )


# ── Chart 1: MaHDi's verified chart (expert agreement) ──────────────

def test_chart1_mahdi_positions():
    g = GOLDEN_CHARTS[0]
    c = _chart(g).chart_json
    p, a = c["planets"], c["angles"]
    exp = g["expected"]
    assert abs(p["Sun"]["longitude"] - exp["Sun"]) <= TOLERANCE, (
        f"Sun {fmt_lon(p['Sun']['longitude'])} != {fmt_lon(exp['Sun'])}")
    assert abs(p["Moon"]["longitude"] - exp["Moon"]) <= TOLERANCE
    assert abs(a["ASC"]["longitude"] - exp["ASC"]) <= TOLERANCE
    assert abs(a["MC"]["longitude"] - exp["MC"]) <= TOLERANCE
    assert p["Sun"]["sign_index"] == exp["sun_sign"]
    assert p["Moon"]["sign_index"] == exp["moon_sign"]
    assert p["Sun"]["house"] == exp["sun_house"]
    assert p["Moon"]["house"] == exp["moon_house"]
    assert c["moon_phase"] == exp["moon_phase"]
    assert abs(c["moon_phase_deg"] - exp["moon_phase_deg"]) < 1.0
    assert p["Saturn"]["retrograde"] is exp["saturn_retrograde"]
    assert p["Saturn"]["house"] == exp["saturn_house"]


def test_chart1_saturn_mercury_opposition():
    """Report claim: Mercury opp Saturn orb 0°26′ — engine must reproduce it."""
    g = GOLDEN_CHARTS[0]
    c = _chart(g).chart_json
    mer, sat = c["planets"]["Mercury"], c["planets"]["Saturn"]
    d = abs(mer["longitude"] - sat["longitude"])
    d = min(d, 360 - d)
    assert abs(d - 180) < 0.5, f"Mercury-Saturn should be opposition, got {d:.2f}°"


def test_chart7_sidereal_lahiri_positions():
    """audit r3: sidereal chart — positions shifted ~24° (Lahiri ayanamsa),
    Moon & ASC cross sign boundaries vs tropical chart-1."""
    g = GOLDEN_CHARTS[-1]
    c = _chart(g).chart_json
    p, a = c["planets"], c["angles"]
    exp = g["expected"]
    assert c["engine_config"]["zodiac"] == "sidereal"
    assert abs(p["Sun"]["longitude"] - exp["Sun"]) <= TOLERANCE
    assert abs(p["Moon"]["longitude"] - exp["Moon"]) <= TOLERANCE
    assert abs(a["ASC"]["longitude"] - exp["ASC"]) <= TOLERANCE
    assert abs(a["MC"]["longitude"] - exp["MC"]) <= TOLERANCE
    assert p["Sun"]["sign_index"] == exp["sun_sign"]
    assert p["Moon"]["sign_index"] == exp["moon_sign"]
    assert p["Sun"]["house"] == exp["sun_house"]
    assert p["Moon"]["house"] == exp["moon_house"]
    assert c["moon_phase"] == exp["moon_phase"]
    assert abs(c["moon_phase_deg"] - exp["moon_phase_deg"]) < 1.0
    assert p["Saturn"]["retrograde"] is exp["saturn_retrograde"]
    assert p["Saturn"]["house"] == exp["saturn_house"]
    # cross-check: sidereal ≈ tropical − ayanamsa (~23.78° for 1994)
    trop = compute_from_fields(**GOLDEN_CHARTS[0]["birth"]).chart_json
    delta = (trop["planets"]["Sun"]["longitude"] - p["Sun"]["longitude"]) % 360
    assert 23.5 < delta < 24.1, f"Lahiri ayanamsa delta {delta:.3f}° out of range"


def test_chart1_noon_fortune():
    g = GOLDEN_CHARTS[0]
    c = _chart(g).chart_json
    assert c["planets"]["Fortune"]["sign_index"] == 11  # Pisces


# ── Chart 2: unknown birth time ─────────────────────────────────────

def test_chart2_no_time():
    g = GOLDEN_CHARTS[1]
    c = _chart(g).chart_json
    assert c["birth"]["time_known"] is False
    # Sun must stay in Leo (29-30° by convention we use noon)
    sun = c["planets"]["Sun"]
    assert sun["sign_index"] == 4
    assert 29.0 <= sun["degree"] < 30.0


# ── DST-era UTC checks (charts 3-6) handled by test_utc_conversion ──

# ── Chart 7: Jalali leap year conversion ────────────────────────────

def test_chart7_jalali_leap():
    g = GOLDEN_CHARTS[6]
    c = _chart(g).chart_json
    # 1 Esfand 1399 = 19 Feb 2021
    assert c["birth"]["local_time"].startswith("2021-02-19")


# ── Chart 8: retrograde presence ────────────────────────────────────

def test_chart8_has_retrograde():
    g = GOLDEN_CHARTS[7]
    c = _chart(g).chart_json
    any_retro = any(p["retrograde"] for k, p in c["planets"].items() if k != "Fortune")
    assert any_retro, "2020-05-15 chart must contain at least one retrograde planet"


# ── determinism ─────────────────────────────────────────────────────

def test_determinism():
    """Same input → byte-identical JSON (deterministic engine requirement)."""
    g = GOLDEN_CHARTS[0]
    a = compute_from_fields(**g["birth"]).to_json()
    b = compute_from_fields(**g["birth"]).to_json()
    assert a == b
