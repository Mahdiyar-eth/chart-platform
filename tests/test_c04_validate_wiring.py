"""C-04 / AC-07 — validate_advanced() hallucination gate must catch
a Mercury-in-Leo claim when the golden chart has Mercury in Virgo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.claim_validation import validate_advanced

# Golden chart: Mercury in Virgo (mirrors tests/test_claim_validation_a2.py)
CHART = {
    "planets": {
        "sun": {"sign": "leo"}, "moon": {"sign": "pisces"},
        "mercury": {"sign": "virgo"}, "venus": {"sign": "libra"},
        "mars": {"sign": "scorpio"}, "jupiter": {"sign": "gemini"},
        "saturn": {"sign": "capricorn"}, "uranus": {"sign": "aquarius"},
        "neptune": {"sign": "pisces"}, "pluto": {"sign": "sagittarius"},
    },
    "angles": {"asc": {"sign": "leo"}},
}


def test_mercury_in_leo_is_critical_hallucination():
    """Model claims Mercury in Leo; chart has Mercury in Virgo → must flag."""
    out = "عطارد در برج اسد قرار دارد و افکار او را شکل می‌دهد."
    rep = validate_advanced("identity", out, CHART)
    assert rep.critical_hallucination, (
        f"expected critical_hallucination for Mercury-in-Leo claim; got "
        f"ok={rep.ok} claims={rep.claims_found} mismatches={rep.mismatches}"
    )


def test_mercury_in_virgo_passes():
    """Model claims Mercury in Virgo (the truth) → must NOT flag."""
    out = "عطارد در برج سنبله قرار دارد و او را دقیق و تحلیلگر می‌کند."
    rep = validate_advanced("identity", out, CHART)
    assert not rep.critical_hallucination, (
        f"critical_hallucination set incorrectly: {rep.mismatches}"
    )


def test_ascendant_wrong_is_critical():
    out = "طالع شما در سرطان است."
    rep = validate_advanced("identity", out, CHART)
    assert rep.critical_hallucination


def test_generic_prose_not_flagged():
    out = "شما فردی رهبر و مصمم هستید و در روابط به تعادل اهمیت می‌دهید."
    rep = validate_advanced("identity", out, CHART)
    assert not rep.critical_hallucination
