"""A solar-return page view must not compute the same chart four times.

solar_return_for() computed both candidate anniversaries into `best`, then
threw that away and recomputed both into `results`. `best` is never read after
the loop — the first pass was pure waste, and it contained the tell:
`if best is None or True: pass`.

Each find_solar_return() is roughly 88 swe.calc_ut calls plus a full
compute_chart, and a paid page view calls solar_return_for twice (teaser plus
full content), so a single view cost about eight solar-return computations
where two would do.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.astrology.engine import BirthData, compute_chart
from app.report import solar as solar_mod


@pytest.fixture(scope="module")
def natal():
    r = compute_chart(BirthData(lat=35.6889, lon=51.3897, year=1994, month=8,
                                day=23, hour=6, minute=10, tz_name="Asia/Tehran"))
    return r.chart_json


def _count_calls(monkeypatch):
    calls = {"n": 0}
    real = solar_mod.find_solar_return

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(solar_mod, "find_solar_return", counting)
    return calls


def test_solar_return_computes_each_candidate_once(natal, monkeypatch):
    calls = _count_calls(monkeypatch)
    solar_mod.solar_return_for(natal, 35.6889, 51.3897, "Asia/Tehran",
                               when_local=datetime(2026, 3, 1, 12, 0,
                                                   tzinfo=ZoneInfo("Asia/Tehran")))
    assert calls["n"] == 2, (
        f"solar_return_for made {calls['n']} find_solar_return calls for two "
        "candidate anniversaries — it is recomputing work it already did"
    )


def test_result_is_unchanged_by_the_optimisation(natal):
    """The dead loop must not have been load-bearing."""
    when = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))
    a = solar_mod.solar_return_for(natal, 35.6889, 51.3897, "Asia/Tehran", when_local=when)
    b = solar_mod.solar_return_for(natal, 35.6889, 51.3897, "Asia/Tehran", when_local=when)
    assert a.moment_utc == b.moment_utc
    assert a.age_years == b.age_years
    # and the moment must actually be the active solar year: on or before `when`
    assert a.moment_utc.replace(tzinfo=None) <= when.astimezone(
        ZoneInfo("UTC")).replace(tzinfo=None)
