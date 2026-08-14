"""Share card generator — 1200×630 OG-style card rendered via headless Chromium.

Persian text + chart wheel; cached PNG on disk keyed by chart_id.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.astrology.big_three import big_three
from app.astrology.svg_wheel import render_chart_svg

CACHE_DIR = Path(os.getenv("SHARE_CACHE_DIR", "/tmp/chart-share"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _card_html(chart_json: dict) -> str:
    bt = big_three(chart_json)
    wheel = render_chart_svg(chart_json)
    # strip width/height so CSS can size it
    wheel = wheel.replace('width="640"', 'width="300"').replace('height="640"', 'height="300"')
    signs = {
        "Sun": ("خورشید", bt.get("Sun", {}).get("sign_fa", "")),
        "Moon": ("ماه", bt.get("Moon", {}).get("sign_fa", "")),
        "ASC": ("طالع", bt.get("ASC", {}).get("sign_fa", "")),
    }
    badges = "".join(
        f'<div style="background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);'
        f'border-radius:16px;padding:14px 22px;text-align:center;">'
        f'<div style="font-size:15px;color:#a9b6e8;">{label}</div>'
        f'<div style="font-size:26px;font-weight:800;color:#fff;margin-top:4px;">{sign}</div></div>'
        for label, sign in signs.values()
    )
    return f"""<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8">
<style>
@font-face {{ font-family:'Vazirmatn'; src:url('/static/fonts/Vazirmatn-Bold.ttf'); }}
body {{ margin:0; font-family:Vazirmatn, Tahoma, sans-serif; }}
.card {{ width:1200px; height:630px; display:flex; align-items:center; gap:40px; padding:0 60px;
  background: radial-gradient(900px 600px at 80% -10%, #1b2350 0%, #0b1026 60%), #0b1026;
  box-sizing:border-box; }}
.wheel {{ flex:0 0 300px; }}
.info {{ flex:1; }}
h1 {{ color:#f5c518; font-size:34px; margin:0 0 6px; }}
.sub {{ color:#a9b6e8; font-size:18px; margin-bottom:26px; }}
.badges {{ display:flex; gap:14px; }}
</style></head><body>
<div class="card">
  <div class="wheel">{wheel}</div>
  <div class="info">
    <h1>چارت تولد من</h1>
    <div class="sub">گزارش اختصاصی با محاسبه‌ی دقیق نجومی</div>
    <div class="badges">{badges}</div>
  </div>
</div></body></html>"""


def render_share_card(chart_json: dict, chart_id: str) -> str:
    """Render + cache PNG. Returns file path."""
    key = hashlib.sha1(chart_id.encode(), usedforsecurity=False).hexdigest()[:16]
    out = CACHE_DIR / f"{key}.png"
    if out.exists():
        return str(out)

    html = _card_html(chart_json)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        pg.set_content(html)
        pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        b.close()
    return str(out)
