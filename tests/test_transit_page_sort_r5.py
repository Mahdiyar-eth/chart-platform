"""R.5 / AC-4 (V9+V10) — pure-function unit tests for the transit page sorters.

`top_by_weight` returns the N globally-highest-weight events REGARDLESS of month
(the R4 page only sorted WITHIN each month, burying a heavy transit ~4000px down).
`open_month_keys` returns the month-groups to leave expanded (current + next 2).
Both are pure + deterministic, so the ordering is unit-testable without a browser.
"""
from app.astrology.transit_forecast import month_label_map, open_month_keys, top_by_weight


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


# ─── R.6 / U1 (structural AC-4) and U2 (year-aware month labels) ───────────

def test_structural_ac4_at_most_3_groups_open():
    """R.6/U1 — AC-4 must be STRUCTURAL, not pixel/data-dependent.

    The pixel goal «height < 3000px» breaks on a chart that happens to have many
    events in its first 3 open months. The durable invariant is: no matter how
    many months/events the window holds, AT MOST 3 month-groups are left expanded
    and the rest are collapsed into `<details>`. This is independent of chart data.
    """
    # A wide window spanning several years and many events.
    wide = [
        _ev(w, f"202{_y}-{_m:02d}-01", f"e{i}")
        for i, (w, _y, _m) in enumerate([
            (1, 6, 8), (2, 6, 9), (3, 6, 10), (4, 6, 11), (5, 6, 12),
            (6, 7, 1), (7, 7, 2), (8, 7, 3), (9, 7, 6), (5, 7, 9),
        ])
    ]
    # distinct months: 2026-08..2026-12, 2027-01..2027-03, 2027-06, 2027-09
    open_months = open_month_keys(wide, 3)
    assert len(open_months) == 3, open_months
    # every group is either in the open set or not — and only ≤3 are open
    all_months = sorted({str(e["window_start"])[:7] for e in wide})
    assert len(open_months) == 3
    assert all(m in all_months for m in open_months)
    # the invariant the browser check needs: open set is small and bounded
    assert len(open_month_keys(wide, 3)) <= 3


def test_open_months_bounded_even_for_single_month_flood():
    """R.6/U1 — a flood of events in ONE month must not blow the open set."""
    flood = [_ev(9, "2026-08-01", f"f{i}") for i in range(50)]
    assert open_month_keys(flood, 3) == ["2026-08"]


def test_month_labels_same_year_keep_bare_name():
    """R.6/U2 — a single-year window keeps the clean bare month name."""
    ev = [_ev(1, "2026-08-01"), _ev(1, "2026-09-01")]
    labels = month_label_map(ev)
    assert labels["2026-08"] == "آبان"
    assert labels["2026-09"] == "آذر"


def test_month_labels_two_years_get_year_suffix():
    """R.6/U2 — spanning two Persian years disambiguates the duplicate month name."""
    # 2026-08 & 2027-08 both map to Persian «آبان», across two Persian years (1405/1406).
    ev = [_ev(1, "2026-08-01"), _ev(1, "2027-08-01")]
    labels = month_label_map(ev)
    assert labels["2026-08"] == "آبان ۱۴۰۵", labels
    assert labels["2027-08"] == "آبان ۱۴۰۶", labels
    assert labels["2026-08"] != labels["2027-08"]


def test_month_labels_missing_window_start_ignored():
    assert month_label_map([_ev(1, "")]) == {}
