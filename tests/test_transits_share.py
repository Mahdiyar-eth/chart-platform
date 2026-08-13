"""Phase 6-9 tests — share card + transits (deterministic, no LLM)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.astrology.engine import compute_from_fields
from app.astrology.transits import compute_transits
from app.share.card import _card_html

CHART = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def test_transits_returns_events():
    ev = compute_transits(CHART, when=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc))
    assert isinstance(ev, list)
    for e in ev:
        assert "planet" in e and "aspect" in e and "orb" in e
        assert e["target"] in ("Sun", "Moon", "ASC")


def test_transits_sorted_by_orb():
    ev = compute_transits(CHART, when=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc))
    orbs = [e["orb"] for e in ev]
    assert orbs == sorted(orbs)


def test_transits_deterministic():
    a = compute_transits(CHART, when=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc))
    b = compute_transits(CHART, when=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc))
    assert a == b


def test_share_card_html_contains_wheel_and_badges():
    html = _card_html(CHART)
    assert "<svg" in html          # wheel
    assert "خورشید" in html and "ماه" in html and "طالع" in html
    assert "اسد" in html           # Sun in Leo
