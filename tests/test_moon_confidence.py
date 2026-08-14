"""H0.3 (HARDENING): unknown birth time — Moon sign confidence.

The Moon (~13°/day) can cross a sign boundary within the birth day. When the
birth time is unknown the engine must NOT present a single definitive Moon
sign; it reports sign_confidence (high|medium|low) + possible signs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402

from app.astrology.engine import compute_from_fields  # noqa: E402

TEHRAN = dict(lat=35.6892, lon=51.3890, tz_name="Asia/Tehran")


def test_known_time_always_high():
    c = compute_from_fields(year=2024, month=7, day=5, hour=12, minute=0,
                            time_known=True, **TEHRAN).chart_json
    assert c["birth"]["moon_confidence"] == "high"
    assert c["birth"]["moon_possible_signs"] == []
    assert "sign_confidence" not in c["planets"]["Moon"]


def test_unknown_time_normal_day_high():
    c = compute_from_fields(year=2024, month=7, day=10, hour=12, minute=0,
                            time_known=False, **TEHRAN).chart_json
    assert c["birth"]["moon_confidence"] == "high"
    assert c["birth"]["moon_possible_signs"] == []


@pytest.mark.parametrize("day,expected", [
    (5, "medium"),   # moon crosses 90° (Gemini→Cancer) during 2024-07-05
    (25, "medium"),  # crosses Aries→Pisces boundary that day
    (2, "medium"),   # Taurus→Gemini boundary day
])
def test_unknown_time_boundary_day_reports_uncertainty(day, expected):
    c = compute_from_fields(year=2024, month=7, day=day, hour=12, minute=0,
                            time_known=False, **TEHRAN).chart_json
    b = c["birth"]
    assert b["moon_confidence"] == expected
    assert len(b["moon_possible_signs"]) >= 2
    m = c["planets"]["Moon"]
    assert m["sign_confidence"] == expected
    assert len(m["possible_signs"]) >= 2
    # the presented sign is always one of the possible ones
    assert m["sign_fa"] in m["possible_signs"]


def test_houses_still_omitted_without_time():
    c = compute_from_fields(year=2024, month=7, day=10, hour=12, minute=0,
                            time_known=False, **TEHRAN).chart_json
    assert c["houses"] == {}
    assert c["angles"] == {}
    assert "Fortune" not in c["planets"]
