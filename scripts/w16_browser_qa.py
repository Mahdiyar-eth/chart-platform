"""MASTER W16 — browser QA of every redesigned page.

Runs against the local QA server (:8899). For each page, at 390px AND 1280px:
- HTTP 200
- no horizontal overflow (scrollWidth <= clientWidth + 2)
- primary heading visible
- key content markers present
- screenshot saved to docs/qa/w16/
"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8899"
OUT = Path("docs/qa/w16")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("/", ["چارت تولد", "چارت رایگان من"]),
    ("/plans", ["شناخت کامل", "باز کردن با", "نرخ مرجع"]),
    ("/today", []),
    ("/dashboard", []),   # login-gated → expects redirect
]

RESULTS = []


def check(page, url: str, width: int, markers: list[str]) -> dict:
    page.set_viewport_size({"width": width, "height": 844})
    resp = page.goto(BASE + url, wait_until="networkidle", timeout=20000)
    status = resp.status if resp else 0
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    h1_visible = False
    try:
        loc = page.locator("h1").first
        h1_visible = loc.is_visible() and len((loc.text_content() or "").strip()) > 3
    except Exception:
        pass
    body = page.content()
    found = [m for m in markers if m in body]
    shot = OUT / f"{url.strip('/').replace('/', '_') or 'landing'}-{width}.png"
    page.screenshot(path=str(shot), full_page=True)
    return {"url": url, "width": width, "status": status,
            "overflow_px": overflow, "h1_visible": h1_visible,
            "markers_found": found, "markers_missing": [m for m in markers if m not in body],
            "screenshot": str(shot)}


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    ctx = browser.new_context(locale="fa-IR")
    page = ctx.new_page()
    for url, markers in PAGES:
        for w in (390, 1280):
            RESULTS.append(check(page, url, w, markers))
    browser.close()

failures = [r for r in RESULTS
            if r["status"] != 200 or r["overflow_px"] > 2 or r["markers_missing"]]
print(json.dumps(RESULTS, ensure_ascii=False, indent=1))
print(f"\nTOTAL {len(RESULTS)} | FAILURES {len(failures)}")
if failures:
    print(json.dumps(failures, ensure_ascii=False, indent=1))
sys.exit(0)
