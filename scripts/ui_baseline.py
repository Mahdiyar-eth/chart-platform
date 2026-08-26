"""Create a truthful visual baseline for the Zayche redesign.

This is deliberately read-only: it visits public pages on the live site,
records status/title/console/failed requests/overflow, and saves mobile and
desktop screenshots for before/after comparison.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

BASE = "https://chart.negar.io"
PAGES = [
    "/", "/plans", "/birth-form", "/synastry", "/rectify", "/today", "/sky",
    "/sky-today", "/articles", "/learn", "/glossary", "/faq", "/guide",
    "/about", "/contact", "/privacy", "/terms", "/refund", "/disclaimer",
    "/moon", "/signs/leo", "/birth-chart/tehran", "/solar-guide",
    "/relocation-guide", "/deep-report", "/self-discovery", "/gift-guide",
]
OUT = Path("docs/qa/redesign-baseline")
WIDTHS = (390, 1280)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        for path in PAGES:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 844})
                console_errors = []
                failed = []
                page.on("pageerror", lambda e: console_errors.append(str(e)))
                page.on("requestfailed", lambda r: failed.append(r.url))
                try:
                    response = page.goto(BASE + path, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(300)
                    row = {
                        "path": path,
                        "width": width,
                        "status": response.status if response else 0,
                        "title": page.title(),
                        "overflow": page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"),
                        "console_errors": console_errors[:5],
                        "failed_requests": failed[:10],
                        "body_chars": len(page.inner_text("body")),
                    }
                    page.screenshot(path=str(OUT / f"{path.strip('/').replace('/', '-') or 'home'}-{width}.png"), full_page=True)
                except Exception as exc:
                    row = {"path": path, "width": width, "status": 0, "error": str(exc)[:200]}
                rows.append(row)
                page.close()
        browser.close()
    (OUT / "baseline.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    from collections import Counter
    print(json.dumps({
        "pages": len(PAGES), "widths": len(WIDTHS), "checks": len(rows),
        "status": dict(Counter(str(r.get("status")) for r in rows)),
        "console_error_checks": sum(bool(r.get("console_errors")) for r in rows),
        "failed_request_checks": sum(bool(r.get("failed_requests")) for r in rows),
        "overflow_checks": sum((r.get("overflow") or 0) > 1 for r in rows),
        "output": str(OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
