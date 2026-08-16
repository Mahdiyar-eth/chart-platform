"""A2b — advanced claim validation: house, degree, aspect, MC, retrograde."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.claim_validation import (
    aspect_between,
    degree_of,
    house_of,
    validate_advanced,
)

# ASC at 15° Leo = 135°; sun 135° (Leo 0°) → sun in house 1.
# moon at 135+27=162° (Virgo 12°) → house ((162-135)%360)//30+1 = 1.
# venus at 162+27=189° (Libra 9°) → house ((189-135)//30)+1 = 2.
CHART = {
    "planets": {
        "sun": {"longitude": 135.0},
        "moon": {"longitude": 162.0},
        "venus": {"longitude": 189.0},
        "mars": {"longitude": 216.0},   # Scorpio 6°
        "mercury": {"longitude": 243.0},
        "jupiter": {"longitude": 270.0},
        "saturn": {"longitude": 24.0},
        "uranus": {"longitude": 51.0},
        "neptune": {"longitude": 78.0},
        "pluto": {"longitude": 255.0},
        "mars_retro": {"longitude": 216.0},
    },
    "angles": {
        "asc": {"longitude": 135.0},
        "mc": {"longitude": 45.0},   # 15° Taurus
    },
}


def test_house_computation():
    assert house_of("sun", CHART) == 1
    assert house_of("venus", CHART) == 2
    assert house_of("saturn", CHART) == 9  # (24-135)%360=249 → 249//30+1=9
    assert house_of("uranus", CHART) == 10  # (51-135)%360=276 → 276//30=9+1=10


def test_degree_computation():
    assert degree_of("sun", CHART) == 15.0
    assert degree_of("moon", CHART) == 12.0


def test_aspect_detection():
    # sun 135 vs venus 189 → diff 54 → sextile orb 6 → sextile
    k, orb = aspect_between("sun", "venus", CHART)
    assert k == "sextile" and orb <= 6.0
    # sun 135 vs saturn 24 → diff 111 → trine orb 9 → None (>6)
    assert aspect_between("sun", "saturn", CHART) is None


def test_house_claim_mismatch_flagged():
    out = "مریخ در خانهٔ هفتم قرار دارد و بر روابط اثر میگذارد."
    rep = validate_advanced("career", out, CHART)
    assert rep.critical_hallucination
    assert any("mars" in m[0] for m in rep.house_mismatches)


def test_degree_claim_mismatch_flagged():
    out = "خورشید در ۲۹ درجه قرار گرفته است."
    rep = validate_advanced("identity", out, CHART)
    assert rep.critical_hallucination
    assert any("sun" in m[0] for m in rep.degree_mismatches)


def test_aspect_claim_graph_valid():
    # sun sextile venus is real in this chart
    out = "خورشید در سکستایل با زهره قرار دارد و این به جذابیت میافزاید."
    rep = validate_advanced("identity", out, CHART)
    assert rep.ok, rep


def test_aspect_claim_false_flagged():
    out = "خورشید در تقابل با زهره قرار دارد."
    rep = validate_advanced("identity", out, CHART)
    assert rep.critical_hallucination
    assert len(rep.aspect_mismatches) >= 1


def test_mc_claim_validated():
    out = "میانهٔ آسمان در برج ثور است."
    rep = validate_advanced("career", out, CHART)
    assert rep.ok, rep


def test_retrograde_unverifiable_note_and_safe_false():
    out = "زحل در حالت رتروگراد حرکت میکند."
    rep = validate_advanced("identity", out, CHART)
    # chart has no retrograde flags → unverifiable note, not hallucination
    assert not rep.critical_hallucination
    assert any("retrograde-unverifiable" in n for n in rep.notes)


def test_transit_keepaway_note():
    out = "ترانزیت مشتری در این ماه تأثیر دارد."
    rep = validate_advanced("identity", out, CHART)
    assert any("transit" in n for n in rep.notes)
    assert not rep.critical_hallucination