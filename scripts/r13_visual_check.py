"""R13-visual: real screenshots of PROD (chart.negar.io) at 390px mobile.
Pages: landing, plans, synastry (with dropdown open), articles, dashboard.
Saves to docs/qa/r13-visual/ and prints nothing fancy.
"""
import time
from playwright.sync_api import sync_playwright

BASE = "https://chart.negar.io"
OUT = "docs/qa/r13-visual"

PAGES = [
    ("/", "home"),
    ("/plans", "plans"),
    ("/synastry", "synastry"),
    ("/articles", "articles"),
    ("/today", "today"),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844},
                        device_scale_factor=2, locale="fa-IR")
    pg = ctx.new_page()
    for path, name in PAGES:
        pg.goto(BASE + path, wait_until="networkidle", timeout=45000)
        time.sleep(1.5)
        # full page screenshot
        pg.screenshot(path=f"{OUT}/{name}-390-full.png", full_page=True)
        print("saved", name)
    # synastry with city dropdown OPEN
    pg.goto(BASE + "/synastry", wait_until="networkidle", timeout=45000)
    inp = pg.query_selector('input[name=city_a]')
    if inp:
        inp.fill("تهر")
        time.sleep(1.5)
        pg.screenshot(path=f"{OUT}/synastry-dropdown-390.png")
        print("saved synastry-dropdown")
    b.close()
print("DONE")
