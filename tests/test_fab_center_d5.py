"""R14-D5 — the bottom-nav FAB must be EXACTLY centered.

Measured defect: FAB center was 266px on a 390px viewport (71px off) because
the FAB was slot 2 of 5. Fix: FAB is slot 3. This test proves geometry, not
markup — measures getBoundingClientRect centers at three widths.
"""
import os

from app.nav import nav_for


def test_fab_is_third_slot_of_five_both_states():
    for hc in (False, True):
        bottom = nav_for(has_chart=hc)["bottom"]
        assert len(bottom) == 5, f"bottom bar must have exactly 5 slots, got {len(bottom)}"
        fab_idx = next(i for i, it in enumerate(bottom) if it.primary)
        assert fab_idx == 2, f"FAB must be the MIDDLE (3rd) slot, is #{fab_idx + 1}"


def test_fab_center_geometry_at_three_widths():
    """DOM-level: |fab.cx - viewport/2| <= 4px on 360/390/430."""
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
            fab = pg.query_selector(".bn-fab .fab-circle")
            assert fab, f"no .bn-fab at width {w}"
            box = fab.bounding_box()
            cx = box["x"] + box["width"] / 2
            assert abs(cx - w / 2) <= 4, f"width {w}: fab center {cx}, expected {w / 2}"
            pg.close()
        b.close()
