"""R.5 / AC-4 (V9+V10) — pure-function unit tests for the transit page sorters.

`top_by_weight` returns the N globally-highest-weight events REGARDLESS of month
(the R4 page only sorted WITHIN each month, burying a heavy transit ~4000px down).
`open_month_keys` returns the month-groups to leave expanded (current + next 2).
Both are pure + deterministic, so the ordering is unit-testable without a browser.
"""
from app.astrology.transit_forecast import open_month_keys, top_by_weight


def _ev(weight, start, name=None):
    return {
        "id": f"{name or start}-{weight}",
        "weight": weight,
        "window_start": start,
        "window_end": start,
        "transit_planet_fa": "زحل",
        "aspect_fa": "مقارنه",
        "natal_target_fa": "خورشید",
        "natal_house": 10,
        "transit_sign_fa": "اسد",
        "retro_passes": 1,
    }


EVENTS = [
    _ev(3, "2026-08-01"),   # early, minor
    _ev(9, "2027-06-15"),   # heaviest but 10 months out — must rise to top
    _ev(6, "2026-10-01"),
    _ev(1, "2026-09-01"),
    _ev(8, "2026-12-01"),   # 2nd heaviest
    _ev(4, "2027-02-01"),
    _ev(7, "2027-03-01"),
]


def test_top_by_weight_is_global_not_monthly():
    top3 = top_by_weight(EVENTS, 3)
    weights = [e["weight"] for e in top3]
    assert weights == [9, 8, 7], weights


def test_top_by_weight_defaults_to_five():
    assert len(top_by_weight(EVENTS)) == 5


def test_top_by_weight_respects_n_and_tie_breaks_chronologically():
    # two events with the same weight → earlier window_start wins
    a = _ev(5, "2026-11-01", "a")
    b = _ev(5, "2026-08-01", "b")
    out = top_by_weight([a, b], 1)
    assert out[0]["id"] == b["id"]  # b is earlier


def test_open_month_keys_opens_first_three_groups():
    keys = open_month_keys(EVENTS, 3)
    # distinct months in date order: 2026-08, 2026-09, 2026-10, 2026-11, 2026-12,
    # 2027-02, 2027-03, 2027-06 → first three = 2026-08, 2026-09, 2026-10
    assert keys == ["2026-08", "2026-09", "2026-10"], keys


def test_open_month_keys_empty_on_no_events():
    assert open_month_keys([], 3) == []


def test_open_month_keys_handles_missing_window_start():
    assert open_month_keys([_ev(1, "")], 3) == []
