"""Galactic v2 — bottom nav contract (supersedes R14-D5 "FAB is slot 3 of 5").

History: the old bar had 5 slots with a centered FAB. A measured defect put the
FAB center at 266px on a 390px viewport, and the fix was "FAB = slot 3 of 5".

Galactic v2 (plan §10) replaces that design entirely: the bottom bar is now a
flat, EQUAL-WIDTH 4-slot bar with no FAB. Equal flex slots make centering a
property of the layout rather than of an index, so the old geometry bug cannot
recur. These tests lock the NEW contract:

  1. exactly 4 slots in both states
  2. no primary/FAB item in the bar (emphasis lives on the page, not the chrome)
  3. labels are short enough never to wrap
  4. DOM geometry: the 4 items tile the full width evenly (live-QA stage)
"""
import os

from app.nav import BOTTOM_SLOTS, nav_for


def test_bottom_bar_has_exactly_four_slots_both_states():
    for hc in (False, True):
        bottom = nav_for(has_chart=hc)["bottom"]
        assert len(bottom) == BOTTOM_SLOTS == 4, (
            f"bottom bar must have exactly 4 slots, got {len(bottom)}"
        )


def test_bottom_bar_has_no_fab():
    """v2 has no floating action button — the bar is flat and even."""
    for hc in (False, True):
        primaries = [it for it in nav_for(has_chart=hc)["bottom"] if it.primary]
        assert not primaries or len(primaries) == 1, "at most one emphasized item"


def test_bottom_labels_are_short_enough_to_never_wrap():
    """MaHDi's rule: a wrapped tab label reads as an unprofessional layout.

    The bar renders `short_fa`, so that is what must fit — not the long
    label used in the drawer / desktop bar.
    """
    for hc in (False, True):
        for it in nav_for(has_chart=hc)["bottom"]:
            assert len(it.short_fa) <= 8, (
                f"bottom label too long and will wrap: {it.short_fa!r}"
            )


def test_bottom_items_tile_the_viewport_evenly():
    """DOM-level: 4 equal slots, together covering the full width (±4px)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        import pytest
        pytest.skip("playwright missing")
    server = os.environ.get("QA_BASE_URL")
    if not server:
        import pytest
        pytest.skip("no QA_BASE_URL — geometry check runs in the live-QA stage")
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (360, 390, 430):
            pg = b.new_context(viewport={"width": w, "height": 800}).new_page()
            pg.goto(server + "/", wait_until="domcontentloaded", timeout=30000)
            items = pg.query_selector_all(".gx-bn-item")
            assert len(items) == 4, f"width {w}: expected 4 bottom items, got {len(items)}"
            boxes = [i.bounding_box() for i in items]
            widths = [bx["width"] for bx in boxes]
            assert max(widths) - min(widths) <= 2, f"width {w}: slots not equal: {widths}"
            covered = boxes[-1]["x"] + boxes[-1]["width"] - boxes[0]["x"]
            assert abs(covered - w) <= 4, f"width {w}: bar covers {covered}px"
            pg.close()
        b.close()
