"""REDESIGN-MASTER §9.6-7 — axe-core accessibility audit on the 10 main pages.

Vendors axe-core locally (scripts/vendor/axe.min.js — no CDN at runtime).
Fails (exit 1) on any critical/serious violation, in either theme.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("QA_BASE_URL", "https://chart.negar.io")
OUT = Path("docs/qa/redesign/axe-results.json")
PAGES = ["/", "/plans", "/birth-form", "/synastry", "/today",
         "/dashboard", "/articles", "/faq", "/glossary", "/credits"]
AXE = Path(__file__).resolve().parent / "vendor" / "axe.min.js"


def run():
    findings = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        for theme in ("dark", "light"):
            for path in PAGES:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.add_init_script(
                    f"try{{localStorage.setItem('zayche-theme','{theme}')}}catch(e){{}}"
                )
                try:
                    page.goto(BASE + path, wait_until="networkidle", timeout=25000)
                    page.add_script_tag(path=str(AXE))
                    res = page.evaluate(
                        "axe.run(document, {resultTypes: ['violations']})"
                    )
                    viols = [
                        {
                            "id": v["id"],
                            "impact": v.get("impact"),
                            "nodes": len(v["nodes"]),
                            "help": v.get("help"),
                        }
                        for v in res.get("violations", [])
                        if v.get("impact") in ("critical", "serious")
                    ]
                    findings.append({"page": path, "theme": theme,
                                     "critical_or_serious": viols})
                    flag = "RED" if viols else "ok"
                    print(f"{theme:5s} {path:12s} {flag} {len(viols)}")
                except Exception as e:  # noqa: BLE001
                    findings.append({"page": path, "theme": theme,
                                     "error": str(e)[:150]})
                    print(f"{theme:5s} {path:12s} ERROR")
                finally:
                    page.close()
        browser.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    reds = [f for f in findings if f.get("critical_or_serious")]
    print(f"PAGES {len(PAGES)*2} | RED {len(reds)}")
    return 0 if not reds else 1


if __name__ == "__main__":
    raise SystemExit(run())
