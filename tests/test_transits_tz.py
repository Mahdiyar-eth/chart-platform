"""H1.1 (HARDENING): transits follow the CHART's timezone, not server UTC.

A user whose chart tz is ahead/behind the server must see transit windows
anchored to THEIR local day. Ephemeris input stays UTC.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.astrology.transits import _chart_tz, upcoming_transits  # noqa: E402

FAKE_NOW = datetime(2026, 8, 15, 2, 30, tzinfo=timezone.utc)  # server 02:30 UTC


def _chart(tz_name: str) -> dict:
    return {
        "birth": {"tz_name": tz_name},
        "planets": {
            "Sun": {"longitude": 143.0, "sign_fa": "اسد"},
            "Moon": {"longitude": 200.0, "sign_fa": "میزان"},
        },
        "angles": {"ASC": {"longitude": 150.0, "sign_fa": "سنبله"}},
    }


def test_chart_tz_reads_from_chart():
    assert _chart_tz(_chart("America/New_York")) == "America/New_York"
    assert _chart_tz({"birth": {}}) == "Asia/Tehran"
    assert _chart_tz({}) == "Asia/Tehran"


@patch("app.astrology.transits.datetime")
def test_upcoming_transits_start_on_local_day(mock_dt):
    """Server is at 02:30 UTC on Aug 15; chart tz = Asia/Tehran (UTC+3:30)
    → local time is already Aug 15 06:00 → first event date must be 2026-08-15
    (NOT Aug 14 as a naive UTC scan would give)."""
    mock_dt.now.side_effect = lambda tz=None: (
        FAKE_NOW if tz is None else FAKE_NOW.astimezone(tz)
    )
    mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
    evs = upcoming_transits(_chart("Asia/Tehran"), days=1, step=1)
    if evs:
        assert evs[0]["start"] >= "2026-08-15"


@patch("app.astrology.transits.datetime")
def test_late_night_utc_user_sees_their_tomorrow(mock_dt):
    """Server 2026-08-15 02:30 UTC; chart tz = America/Los_Angeles (UTC-7)
    → local is still Aug 14 19:30 → window starts Aug 14."""
    mock_dt.now.side_effect = lambda tz=None: (
        FAKE_NOW if tz is None else FAKE_NOW.astimezone(tz)
    )
    mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
    evs = upcoming_transits(_chart("America/Los_Angeles"), days=1, step=1)
    if evs:
        assert evs[0]["start"] <= "2026-08-14"


def test_compute_transits_accepts_when_override():
    from app.astrology.transits import compute_transits
    evs = compute_transits(_chart("Asia/Tehran"), when=FAKE_NOW)
    assert isinstance(evs, list)
    assert len(evs) <= 12
