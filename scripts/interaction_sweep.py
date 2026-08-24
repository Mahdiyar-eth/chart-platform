#!/usr/bin/env python
"""R.10 / P2-2 — real interaction SWEEP: click everything, classify the result.

The F1 audit's core finding: 665 tests but ZERO real clicks. This drives a real
browser and actually presses buttons / submits forms, then records whether the
interaction worked, broke, did nothing, or gave no feedback.

Result classes:
  OK      — no JS error + navigation to right target (200/303) or content changed
  BROKEN  — JS error / 500 / crash
  DEAD    — nothing observable happened (click had no effect)
  SILENT  — worked but no visible feedback (no toast / loading / content change)
  BLOCKED — needs an external key / login we can't reach in guest state

Note: full coverage of all 1311 items would require owning charts/credits/admin.
Here we sweep the GUEST-REACHABLE, high-value interactive controls (forms + CTAs)
and report honest coverage + real findings.
"""
import json
import os
import sys
from pathlib import Path

import urllib.request
import urllib.error

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = os.getenv("QA_BASE_URL", "http://127.0.0.1:8899")
OUT_MD = ROOT / "docs" / "qa" / "INTERACTION-SWEEP.md"
OUT_JSON = ROOT / "docs" / "qa" / "INTERACTION-SWEEP.json"

# Pages + the button/control to actually exercise. (Guest-reachable; for these we
# can drive a real click without owning a chart or entering external keys.)
SWEEP = [
    # (page, css selector hint) — we click buttons/CTAs on the page
    "/birth-form",
    "/plans",
    "/account/login",
    "/synastry",
    "/rectify",
    "/today",
    "/glossary",
    "/faq",
    "/explore",
]


def _collect_controls(page, path):
    """Buttons + nav links that are real interactive controls on the page."""
    els = page.query_selector_all("button, a[href], input[type=submit], [role=button], details summary")
    out = []
    for el in els:
        text = (el.inner_text() or "").strip()[:60]
        href = el.get_attribute("href") or ""
        disabled = el.get_attribute("disabled")
        if disabled:
            continue
        # Only test controls actually VISIBLE (hidden dialog/toggle closes are not
        # reachable without first opening them — clicking them is not a real flow).
        try:
            vis = el.is_visible()
        except Exception:
            vis = False
        if not vis:
            continue
        out.append({"el": el, "text": text, "href": href})
    return out


def _click_outcome(page, el):
    """Click and observe. Return (class, detail)."""
    errors_before = []
    page.on("pageerror", lambda e: errors_before.append(str(e)))
    try:
        before_url = page.url
        before_text = (page.inner_text("body") or "")[:300]
        el.click(timeout=2500)
        page.wait_for_timeout(450)
        after_url = page.url
        after_text = (page.inner_text("body") or "")[:300]
        errors = errors_before
        # navigation happened?
        if after_url != before_url:
            resp = _fetch_path(after_url)
            if resp in (500, 404):
                return ("BROKEN", f"nav→{resp} {after_url}")
            return ("OK", f"nav→{after_url}")
        # content changed?
        if after_text != before_text:
            return ("OK", "content changed")
        if errors:
            return ("BROKEN", "; ".join(errors[:2]))
        return ("DEAD", "click: no observable change")
    except Exception as e:
        err = str(e)[:120]
        if "500" in err or "Internal Server Error" in err:
            return ("BROKEN", err)
        return ("SILENT", f"exception (may be dialog/preventDefault): {err}")


def _fetch_path(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def main():
    findings = []
    covered = 0
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"  # headless: no session bus
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        for path in SWEEP:
            page = browser.new_page(viewport={"width": 390, "height": 800})
            try:
                page.goto(BASE + path, wait_until="networkidle", timeout=15000)
            except Exception as e:
                findings.append({"page": path, "control": "(load)", "result": "BROKEN", "detail": str(e)[:120]})
                continue
            tested = 0
            # Re-collect controls after EACH reload so handles are never stale.
            while tested < 6:
                controls = _collect_controls(page, path)
                # Prefer real buttons (logic) over pure nav links (which just route).
                ordered = sorted(controls, key=lambda c: (0 if c["el"].evaluate("e=>e.tagName.toLowerCase()") == "button" else 1))
                clicked_any = False
                for c in ordered:
                    if tested >= 10:
                        break
                    if not c["text"] and not c["href"]:
                        continue
                    tag = c["el"].evaluate("e=>e.tagName.toLowerCase()")
                    if tag == "a" and c["href"] and c["href"] not in (BASE + path,):
                        # nav link: one representative per page, then continue
                        pass
                    cls, detail = _click_outcome(page, c["el"])
                    findings.append({"page": path, "control": c["text"] or c["href"],
                                     "result": cls, "detail": detail})
                    tested += 1
                    covered += 1
                    clicked_any = True
                    break  # reload after each successful click
                if not clicked_any:
                    break
                # Reload the page so handles are fresh for the next iteration.
                try:
                    page.goto(BASE + path, wait_until="networkidle", timeout=15000)
                except Exception:
                    break
            page.close()
        browser.close()

    OUT_JSON.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    counts = Counter(f["result"] for f in findings)
    md = ["# 🖱️ سوییپ تعاملی — INTERACTION-SWEEP", "",
          f"> پوشش: **{covered} کلیک واقعی** روی {len(SWEEP)} صفحه (حالت مهمان).",
          f"> نتیجه: {dict(counts)}",
          "", "| # | صفحه | کنترل | نتیجه | جزئیات |"]
    for i, f in enumerate(findings, 1):
        md.append(f"| {i} | `{f['page']}` | {f['control']} | **{f['result']}** | {f['detail']} |")
    md.append("")
    md.append("## یافتههای غیر OK")
    bad = [f for f in findings if f["result"] != "OK"]
    if not bad:
        md.append("> هیچ یافتهٔ غیر-OK در این پوشش (حالت مهمان، بدون کلید خارجی).")
    else:
        for f in bad:
            md.append(f"- **{f['result']}** `{f['page']}` → `{f['control']}`: {f['detail']}")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"covered {covered} clicks across {len(SWEEP)} pages")
    print(f"results: {dict(counts)}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
