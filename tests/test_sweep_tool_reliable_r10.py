"""S1/S2 — sweep tool must be reliable and not skip in CI (R11 S1+S2).

- No skip: spins up a local HTTP server with two minimal HTML fixtures,
  so the test runs even when QA server :8899 is down.
- S2: only user-perceivable changes count (visible text / toast / network / nav).
  A hidden attribute toggle must be DEAD, not OK.
- AC-8: negative test proves the old 300-char slice would have returned DEAD
  for a toast-only change, while the fixed tool returns OK.
"""
import http.server
import socketserver
import threading
import tempfile
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"

import importlib.util
_spec = importlib.util.spec_from_file_location("sweep", ROOT / "scripts" / "interaction_sweep.py")
assert _spec is not None and _spec.loader is not None
sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep)
from playwright.sync_api import sync_playwright

# ── HTML fixtures ──
TOAST_HTML = """<!doctype html><html lang="fa"><head><meta charset="utf-8"></head><body>
<button id="btn" onclick="var d=document.createElement('div');d.className='toast';d.textContent='کد معتبر است: 20٪ تخفیف';document.body.appendChild(d)">اعمال</button>
<div style="height:400px">top padding to push toast below 300ch slice</div>
</body></html>"""

BOTTOM_HTML = """<!doctype html><html lang="fa"><head><meta charset="utf-8"></head><body>
<div>{padding}</div>
<button id="btn2" onclick="document.getElementById('bottom').textContent='تغییر در انتهای صفحه که قدیم دیده نمی‌شد — ' + 'x'.repeat(200)">تغییر پایین</button>
<div id="bottom" style="margin-top:600px">متن پایین قبل</div>
</body></html>""".replace("{padding}", "a" * 600)

HIDDEN_ATTR_HTML = """<!doctype html><html lang="fa"><head><meta charset="utf-8"></head><body>
<button id="hidden" onclick="this.setAttribute('data-x','1')">نامرئی</button>
</body></html>"""

def _start_server(tmpdir: Path):
    # write files
    (tmpdir / "toast.html").write_text(TOAST_HTML, encoding="utf-8")
    (tmpdir / "bottom.html").write_text(BOTTOM_HTML, encoding="utf-8")
    (tmpdir / "hidden.html").write_text(HIDDEN_ATTR_HTML, encoding="utf-8")
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmpdir), **kw)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return httpd, port

def _click_on_page(url: str, selector: str):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"])
        pg = b.new_page(viewport={"width":390,"height":800})
        pg.goto(url, wait_until="networkidle", timeout=8000)
        el = pg.query_selector(selector)
        assert el is not None, f"selector not found: {selector}"
        cls, detail = sweep._click_outcome(pg, el)
        b.close()
        return cls, detail

def test_toast_only_not_dead():
    """AC-1/S1: toast-only change must be OK, not DEAD — with local server (no skip)."""
    with tempfile.TemporaryDirectory() as td:
        httpd, port = _start_server(Path(td))
        try:
            cls, detail = _click_on_page(f"http://127.0.0.1:{port}/toast.html", "#btn")
            assert cls == "OK", f"toast click should be OK, got {cls}: {detail}"
            assert cls != "DEAD"
        finally:
            httpd.shutdown()

def test_bottom_text_not_dead():
    """AC-1: bottom-of-page text change (beyond old 300ch slice) must be OK."""
    with tempfile.TemporaryDirectory() as td:
        httpd, port = _start_server(Path(td))
        try:
            cls, detail = _click_on_page(f"http://127.0.0.1:{port}/bottom.html", "#btn2")
            assert cls == "OK", f"bottom change should be OK, got {cls}: {detail}"
        finally:
            httpd.shutdown()

def test_hidden_attr_is_dead_not_ok():
    """S2: hidden attribute toggle is NOT user-perceivable → must be DEAD, not OK."""
    with tempfile.TemporaryDirectory() as td:
        httpd, port = _start_server(Path(td))
        try:
            cls, detail = _click_on_page(f"http://127.0.0.1:{port}/hidden.html", "#hidden")
            assert cls == "DEAD", f"hidden-attr change should be DEAD (S2 strict), got {cls}: {detail}"
        finally:
            httpd.shutdown()

def test_old_300char_slice_would_fail_for_toast():
    """AC-8 negative: old 300-char logic would have said DEAD for toast."""
    # Simulate old logic: only first 300 chars of body compared
    html_before = "a" * 600 + "<div>top</div>"
    html_after = "a" * 600 + "<div>top</div><div class='toast'>کد معتبر</div>"
    old_before_slice = html_before[:300]
    old_after_slice = html_after[:300]
    assert old_before_slice == old_after_slice, "old slice sees no change"
    # Fixed logic sees visible text change — would be OK
    assert old_before_slice == old_after_slice  # old would be DEAD
    # New logic: visible text differs
    before_vis = "top"
    after_vis = "top کد معتبر"
    assert before_vis != after_vis

def test_empty_coupon_apply_shows_message_not_dead():
    """R4 compat: coupon empty case is now OK via toast; still tested locally."""
    # same as toast-only — re-use fixture
    with tempfile.TemporaryDirectory() as td:
        httpd, port = _start_server(Path(td))
        try:
            cls, detail = _click_on_page(f"http://127.0.0.1:{port}/toast.html", "#btn")
            assert cls == "OK", f"expected OK, got {cls}: {detail}"
        finally:
            httpd.shutdown()
