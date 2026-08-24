#!/usr/bin/env python
"""R.10 / P2-1 — interaction INVENTORY (the denominator for the full-QA sweep).

For every public page (+ guest state, since most are public), enumerate every
interactive element. This is the "مخرج" (denominator) for all the click claims in
P2-2. Drives a real Chromium via Playwright against the local QA server.

Output: docs/qa/INTERACTION-INVENTORY.md + .json
"""
import json
import os
import urllib.request
from pathlib import Path

os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"  # headless: no session bus
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = os.getenv("QA_BASE_URL", "http://127.0.0.1:8899")
OUT_MD = ROOT / "docs" / "qa" / "INTERACTION-INVENTORY.md"
OUT_JSON = ROOT / "docs" / "qa" / "INTERACTION-INVENTORY.json"

# Public pages reachable without login (guest state). Some need a cookie/owner;
# those are covered by the user-state sweep in P2-2. For the inventory we hit the
# pages a brand-new visitor can open.
PAGES = [
    "/", "/birth-form", "/plans", "/learn", "/learn/birth-chart", "/signs/asad",
    "/articles", "/articles/chart-tavalod-chist", "/glossary", "/faq", "/guide",
    "/about", "/contact", "/privacy", "/terms", "/refund", "/disclaimer",
    "/synastry", "/rectify", "/sky", "/moon", "/moon-in/hout", "/explore",
    "/self-discovery", "/deep-report", "/gift-guide", "/today", "/account/login",
]

SELECTORS = (
    "button, a[href], input, select, textarea, [role=button], [role=link], "
    "details, summary, [tabindex]:not([tabindex='-1'])"
)


def _fetch(path):
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except Exception:
        return None


def inventory():
    rows = []
    seen = set()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path in PAGES:
            status = _fetch(path)
            if status not in (200,):
                rows.append({"page": path, "status": status, "items": 0, "note": f"status {status}"})
                continue
            page = browser.new_page(viewport={"width": 390, "height": 800})
            page.goto(BASE + path, wait_until="networkidle", timeout=15000)
            els = page.query_selector_all(SELECTORS)
            count = 0
            for el in els:
                tag = el.evaluate("e => e.tagName.toLowerCase()")
                text = (el.inner_text() or "").strip()[:60]
                href = el.get_attribute("href") or ""
                onclick = el.get_attribute("onclick") or el.get_attribute("@click") or el.get_attribute("x-on:click") or ""
                role = el.get_attribute("role") or ""
                placeholder = el.get_attribute("placeholder") or ""
                key = (path, tag, text or placeholder or href or role or onclick)[:80]
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "page": path, "status": status, "type": tag,
                    "text": text, "href": href, "onclick": onclick[:60],
                    "role": role, "placeholder": placeholder,
                })
                count += 1
            page.close()
    return rows


def main():
    rows = inventory()
    # Dedupe by (page, type, text/href)
    dedup = {}
    for r in rows:
        k = (r["page"], r["type"], r["text"] or r["href"] or r["placeholder"])
        if k not in dedup:
            dedup[k] = r
    out = list(dedup.values())
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    by_page = {}
    for r in out:
        by_page.setdefault(r["page"], []).append(r)

    md = ["# 🤖 سیاههٔ تعاملی — INTERACTION-INVENTORY", "",
          f"> **مخرج:** {len(out)} آیتم تعاملی در {len(PAGES)} صفحهٔ عمومی (حالت مهمان).",
          "> این عدد، مخرج همهٔ ادعاهای «کلیک شد» در P2-2 است.",
          "", "| صفحه | آیتمها | تفکیک |"]
    for path in PAGES:
        items = by_page.get(path, [])
        types = {}
        for r in items:
            types[r["type"]] = types.get(r["type"], 0) + 1
        types_str = " · ".join(f"{k}:{v}" for k, v in sorted(types.items()))
        md.append(f"| `{path}` | {len(items)} | {types_str} |")
    md.append("")
    md.append("## نمونهٔ آیتمها (۳۰ مورد اول)")
    md.append("| صفحه | نوع | متن/برچسب | مقصد |")
    for r in out[:30]:
        md.append(f"| `{r['page']}` | {r['type']} | {r['text'] or r['placeholder']} | {r['href'] or r['onclick']} |")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"total items: {len(out)}  across {len(PAGES)} pages")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
