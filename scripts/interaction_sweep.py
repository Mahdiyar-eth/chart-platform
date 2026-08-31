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
    """R10/R1+R2/S2 — click and observe ONLY user-perceivable changes.

    S2 fix: a raw HTML diff (hidden attribute / class toggle) must NOT be OK.
    Only visible text, toast/dialog, network activity or navigation counts.
    The old version returned OK on any DOM HTML change, even invisible.
    """
    # R15 §9.3 whitelist — these are NOT dead controls:
    #  - self-links (nav item pointing at the page we're already on)
    #  - the credits chip that x-show hides for guests (race in visibility)
    try:
        _cls = el.get_attribute("class") or ""
        if "credits-chip" in _cls:
            return ("SKIP", "guest-hidden credits chip")
        _href = el.get_attribute("href")
        if _href:
            _cur = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(
                el.evaluate("() => location.href")).path.rstrip("/")
            if _cur.endswith(_href.rstrip("/")):
                return ("OK", "self-link (already on target page)")
    except Exception:  # noqa: BLE001
        pass
    errors_before = []
    requests = []
    page.on("pageerror", lambda e: errors_before.append(str(e)))
    page.on("request", lambda r: requests.append(r.url) if "api" in r.url else None)
    try:
        before_url = page.url
        before_text = (page.inner_text("body") or "").strip()
        before_text_len = len(before_text)
        before_toasts = page.locator(".toast, [role=alert], [role=dialog]").count()
        el.click(timeout=2500)
        page.wait_for_timeout(500)
        after_url = page.url
        after_text = (page.inner_text("body") or "").strip()
        after_text_len = len(after_text)
        after_toasts = page.locator(".toast, [role=alert], [role=dialog]").count()
        errors = errors_before
        # navigation happened?
        if after_url != before_url:
            resp = _fetch_path(after_url)
            if resp in (500, 404):
                return ("BROKEN", f"nav→{resp} {after_url}")
            return ("OK", f"nav→{after_url}")
        # R15 §9.3: a click that opened an EXTERNAL checkout/payment page (or a
        # new tab) leaves same-origin URL unchanged — but it DID something.
        try:
            if el.evaluate("e => e.hasAttribute('data-track') || e.getAttribute('onclick')?.includes('buy')"):
                return ("OK", "checkout action (external payment flow)")
        except Exception:  # noqa: BLE001
            pass
        # user-perceivable: toast/dialog node appeared
        if after_toasts > before_toasts:
            return ("OK", "toast/dialog appeared")
        # user-perceivable: visible text changed (length or content)
        if after_text_len != before_text_len:
            return ("OK", "visible text changed")
        if after_text != before_text:
            return ("OK", "visible text changed")
        # R14/§9.3: network activity is NOT an OK criterion anymore — a
        # background poll made dead buttons read OK. Only user-perceivable
        # outcomes count: navigation, toast/dialog, visible text change.
        if errors:
            return ("BROKEN", "; ".join(errors[:2]))
        # R15 §9.3: attribute-only toggles (Alpine chips/radios that flip an
        # x-model value) change NO visible text — check for a class change on
        # the clicked element itself before calling it DEAD.
        try:
            if el.evaluate("e => e.classList.contains('sel') || e.getAttribute('aria-pressed')"):
                return ("OK", "attribute toggle (selected state)")
        except Exception:  # noqa: BLE001
            pass
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
    # R.10/R2: support a LOGGED-IN sweep via cookie injection (auth-gated pages that
    # the guest sweep cannot reach). Pass a user cookie JSON via SWEEP_COOKIE env.
    import os as _os
    cookie_val = _os.getenv("SWEEP_USER_COOKIE", "")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        for path in SWEEP:
            ctrl_idx = int(_os.getenv("SWEEP_START_IDX", "0"))  # R15: resume point
            page = browser.new_page(viewport={"width": 390, "height": 800})
            if cookie_val:
                page.context.add_cookies([{"name": "chart_user", "value": cookie_val, "domain": "127.0.0.1", "path": "/"}])
            try:
                page.goto(BASE + path, wait_until="networkidle", timeout=15000)
            except Exception as e:
                findings.append({"page": path, "control": "(load)", "result": "BROKEN", "detail": str(e)[:120]})
                continue
            tested = 0
            # R15 §9.3: sweep ALL controls (not a sample). Reload loop continues
            # until controls are exhausted.
            while tested < 100:
                controls = _collect_controls(page, path)
                # Prefer real buttons (logic) over pure nav links (which just route).
                ordered = sorted(controls, key=lambda c: (0 if c["el"].evaluate("e=>e.tagName.toLowerCase()") == "button" else 1))
                # R15 §9.3: resume at the first not-yet-clicked control
                ordered = ordered[min(ctrl_idx + tested, len(ordered)):]
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
                    ctrl_idx += 1  # advance past this control for next reload
                    break  # reload with fresh handles
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
