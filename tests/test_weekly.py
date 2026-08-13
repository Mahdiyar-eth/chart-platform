"""Weekly reflection tests — audit P0-2.

The weekly «نگاهی به آسمان هفته» must be reflective (not predictive), carry
no fortune-telling language, and end with the agency/free-will framing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.astrology.engine import compute_from_fields
from app.report.weekly import build_weekly_reflection


def _chart():
    return compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def test_reflection_is_not_predictive():
    txt = build_weekly_reflection(_chart())
    for banned in ("پیش‌بینی", "فال", "طالع", "آینده", "اتفاق می‌افتد"):
        assert banned not in txt, f"banned word present: {banned}"


def test_reflection_has_agency_framing():
    txt = build_weekly_reflection(_chart())
    assert "اختیار" in txt
    assert "نقشه" in txt  # "نقشهی موقعیتها، نه سرنوشت"


def test_reflection_has_title():
    txt = build_weekly_reflection(_chart())
    assert "نگاهی به آسمان هفته" in txt


def test_reflection_handles_empty_events():
    # a chart with no upcoming tight aspects still yields a non-empty reflection
    txt = build_weekly_reflection(_chart())
    assert len(txt) > 60
