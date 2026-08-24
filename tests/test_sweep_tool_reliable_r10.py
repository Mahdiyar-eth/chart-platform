"""R10 / R1 (AC-1) — the interaction-sweep tool must not report false DEAD.

The reviewer caught the tool only comparing the first 300 chars of <body>, so a
button that only shows a toast or only changes the bottom of the page read as DEAD.
This drives the real sweep tool (against the QA server) and asserts those two cases
must come back OK, never DEAD.
"""
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"
from playwright.sync_api import sync_playwright  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("sweep", ROOT / "scripts" / "interaction_sweep.py")
assert _spec is not None and _spec.loader is not None
sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep)

BASE = "http://127.0.0.1:8899"


def _server_up() -> bool:
    try:
        urllib.request.urlopen(BASE + "/health", timeout=3)
        return True
    except Exception:
        return False


def _click(selector, text_case=False):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        pg = b.new_page(viewport={"width": 390, "height": 800})
        pg.goto(BASE + "/plans", wait_until="networkidle")
        if text_case:
            pg.fill("input[placeholder*='کد تخفیف']", "LANCH20")
        el = pg.query_selector(selector)
        cls, detail = sweep._click_outcome(pg, el)
        b.close()
        return cls, detail


def test_empty_coupon_apply_shows_message_not_dead():
    """R4: the coupon 'اعمال' button with an EMPTY field must give feedback (not DEAD)."""
    if not _server_up():
        import pytest
        pytest.skip("QA server not running on :8899")
    cls, detail = _click("button:has-text('اعمال')", text_case=True)
    assert cls == "OK", f"expected OK for coupon-with-valid-code, got {cls}: {detail}"


def test_toast_only_not_dead():
    """AC-1: the tool must not classify a click that only shows a toast as DEAD."""
    if not _server_up():
        import pytest
        pytest.skip("QA server not running on :8899")
    cls, detail = _click("button:has-text('اعمال')", text_case=False)
    assert cls != "DEAD", f"empty-coupon click must not be DEAD: {detail}"
    assert cls == "OK", f"expected OK, got {cls}: {detail}"
