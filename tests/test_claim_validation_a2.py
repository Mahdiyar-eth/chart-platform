"""A2 — deterministic claim/evidence validation against the chart."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.claim_validation import critical_facts, validate_section

CHART = {
    "planets": {
        "sun": {"sign": "leo"}, "moon": {"sign": "pisces"}, "mercury": {"sign": "virgo"},
        "venus": {"sign": "libra"}, "mars": {"sign": "scorpio"}, "jupiter": {"sign": "gemini"},
        "saturn": {"sign": "capricorn"}, "uranus": {"sign": "aquarius"},
        "neptune": {"sign": "pisces"}, "pluto": {"sign": "sagittarius"},
    },
    "angles": {"asc": {"sign": "leo"}},
}


def test_correct_claims_pass():
    out = ("خورشید در اسد قرار دارد و طالع نیز اسد است. "
           "ماه در حوت و عطارد در سنبله دیده میشود.")
    rep = validate_section("identity", out, CHART)
    assert rep.ok, rep
    assert rep.claims_found == 4
    assert rep.mismatches == []


def test_wrong_sign_is_critical_hallucination():
    out = "خورشید در برج جوزا قرار دارد و این بر شخصیت او اثر میگذارد."
    rep = validate_section("identity", out, CHART)
    assert not rep.ok
    assert rep.critical_hallucination
    assert ("sun", "gemini", "leo") in rep.mismatches


def test_english_signs_tolerated():
    out = "Sun in Leo is the core; Venus in Libra adds charm."
    rep = validate_section("identity", out, CHART)
    assert rep.ok
    assert rep.claims_found >= 2


def test_no_chart_claims_not_flagged_as_hallucination():
    # generic prose without planet+sign pairs → not grounded but not lies
    out = "شما فردی رهبر و مصمم هستید و در روابط خود به تعادل اهمیت میدهید."
    rep = validate_section("identity", out, CHART)
    assert not rep.critical_hallucination
    assert not rep.grounded


def test_ascendant_checked():
    out = "طالع شما در سرطان است."
    rep = validate_section("identity", out, CHART)
    assert rep.critical_hallucination
    assert ("ascendant", "cancer", "leo") in rep.mismatches


def test_critical_facts_covers_all_planets():
    facts = dict(critical_facts(CHART))
    assert facts["sun"] == "leo"
    assert facts["ascendant"] == "leo"
    assert len(facts) == 11