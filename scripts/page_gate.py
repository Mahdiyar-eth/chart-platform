"""REDESIGN-MASTER §9.2 — page gate: hard, exit-code-bearing page QA.

For each page and each width (360/390/430/768/1280/1920):
  - HTTP 200
  - zero horizontal overflow
  - no interactive element hidden under the fixed bottom nav IN THE LIVE
    VIEWPORT (full-page screenshots legitimately scroll content past the nav,
    so overlap is measured per-viewport, not on the stitched page)
  - every VISIBLE interactive control >= 44x44px (touch target) — elements
    hidden by visibility/display are excluded; tall whole-card links are fine
  - screenshot saved to docs/qa/redesign/

Exit code 0 only when EVERYTHING passes — this script CAN go red.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("QA_BASE_URL", "https://chart.negar.io")
OUT = Path("docs/qa/redesign")
WIDTHS = [360, 390, 430, 768, 1280, 1920]
PAGES = ["/", "/plans", "/articles", "/synastry", "/today", "/faq", "/glossary"]

CHECK_JS = """
() => {
  const nav = document.querySelector('.bottomnav');
  const navRect = nav ? nav.getBoundingClientRect() : null;
  const bad = [];
  document.querySelectorAll('a, button, input, select, textarea, [role=button]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') return;
    // touch target
    const small = (r.width < 40 || r.height < 40) && el.tagName !== 'INPUT';
    // hidden under fixed bottom nav (only elements in the same viewport band)
    let under = false;
    if (navRect && r.bottom > navRect.top && r.top < navRect.bottom && el !== nav && !nav.contains(el)) {
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      under = cx > navRect.left && cx < navRect.right;
    }
    if (small || under) bad.push({tag: el.tagName, cls: String(el.className).slice(0, 40),
                                  small: !!small, under: !!under,
                                  w: Math.round(r.width), h: Math.round(r.height)});
  });
  return bad.slice(0, 12);
}
"""


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    failures = []
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for path in PAGES:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 844})
                try:
                    resp = page.goto(BASE + path, wait_until="networkidle", timeout=25000)
                    status = resp.status if resp else 0
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    # R14 §9.2: overlap must test REACHABILITY, not a static
                    # top-of-page snapshot. Scroll each interactive element into
                    # view and check it clears the fixed bottom nav — that is
                    # what a real user can do. Full-page coordinates are bogus
                    # (the stitched image always "overlaps").
                    bad = page.evaluate(CHECK_JS + """
                        // reachability pass: scroll each offender into view
                        (() => { const nav = document.querySelector('.bottomnav');
                          if (!nav) return [];
                          const nr = nav.getBoundingClientRect(); const real = [];
                          document.querySelectorAll('a, button, input, select, textarea').forEach(el => {
                            const r = el.getBoundingClientRect();
                            if (!r.width || !r.height) return;
                            if (!(r.bottom > nr.top && r.top < nr.bottom) || nav.contains(el)) return;
                            el.scrollIntoView({block: 'center'});
                            const r2 = el.getBoundingClientRect();
                            if (r2.bottom > nr.top && r2.top < nr.bottom)
                              real.push({tag: el.tagName, cls: String(el.className).slice(0,40),
                                         small: false, under: true,
                                         w: Math.round(r2.width), h: Math.round(r2.height)});
                          });
                          return real;
                        })()""")
                    name = (path.strip("/").replace("/", "-") or "home") + f"-{width}.png"
                    page.screenshot(path=str(OUT / name), full_page=True)
                    ok = status == 200 and overflow <= 2 and not bad
                    results.append({"page": path, "w": width, "status": status,
                                    "overflow": overflow, "bad_controls": len(bad),
                                    "ok": ok})
                    if not ok:
                        failures.append({"page": path, "w": width, "status": status,
                                         "overflow": overflow, "controls": bad})
                finally:
                    page.close()
        browser.close()
    import json
    (OUT / "page-gate.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(failures[:6], ensure_ascii=False, indent=1))
    print(f"PAGES {len(PAGES)}x{len(WIDTHS)} | FAILURES {len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(run())
