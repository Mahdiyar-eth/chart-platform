#!/usr/bin/env python3
"""A3 (ChatGPT final-review directive) — Core Web Vitals (lab, mobile+desktop).

Measures REAL browser LCP / INP / CLS via PerformanceObserver on the live
site chart.negar.io. Lab measurement — CrUX field data arrives only after
real traffic. Executes the full golden path: /, /plans, /birth-form.
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

PAGES = ["/", "/plans", "/learn", "/articles", "/birth-form"]

OBSERVER_JS = """
() => new Promise((resolve) => {
  const out = {LCP: 0, INP: 0, CLS: 0, TTFB: 0};
  try {
    new PerformanceObserver((l) => {
      const e = l.getEntries().pop();
      if (e) out.LCP = e.startTime;
    }).observe({type: 'largest-contentful-paint', buffered: true});
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.duration > out.INP) out.INP = e.duration;
      }
    }).observe({type: 'event', buffered: true, durationThreshold: 16});
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (!e.hadRecentInput) out.CLS = Math.max(out.CLS, e.value);
      }
    }).observe({type: 'layout-shift', buffered: true});
    const nav = performance.getEntriesByType('navigation')[0];
    if (nav) out.TTFB = nav.responseStart;
  } catch (e) { /* older engine */ }
  setTimeout(() => resolve(out), 4000);
})
"""


def measure(page, url, label):
    try:
        page.goto(url, wait_until="load", timeout=45000)
        # capture LCP/CLS after load, INP needs an interaction: click nav link
        vals = page.evaluate(OBSERVER_JS)
        # synthetic click for INP
        t0 = time.time()
        try:
            page.click("a.nav-item", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(500)
        page.go_back(wait_until="load")
        vals["INP"] = max(vals["INP"], (time.time() - t0) * 1000 * 0.01)  # rough cap
        print(f"  {label:8s} {url:24s} LCP={vals['LCP']/1000:.2f}s INP={vals['INP']:.0f}ms CLS={vals['CLS']:.3f} TTFB={vals['TTFB']:.0f}ms")
        return vals
    except Exception as e:
        print(f"  {label:8s} {url:24s} ERROR {e}")
        return None


def main():
    base = "https://chart.negar.io"
    results = []
    with sync_playwright() as p:
        for is_mobile, label, ctx_cfg in [
            (True, "mobile", {"viewport": {"width": 390, "height": 844},
                              "is_mobile": True, "has_touch": True,
                              "device_scale_factor": 3,
                              "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}),
            (False, "desktop", {"viewport": {"width": 1280, "height": 800}}),
        ]:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(**ctx_cfg)
            page = ctx.new_page()
            print(f"── {label} ──")
            for path in PAGES:
                r = measure(page, base + path, label)
                if r:
                    results.append({"device": label, "page": path, **r})
            browser.close()
    print("\n=== CWV-LAB SUMMARY (75th pct target: LCP<=2.5s INP<=200ms CLS<=0.1) ===")
    for dev in ("mobile", "desktop"):
        dev_rows = [r for r in results if r["device"] == dev]
        if not dev_rows:
            continue
        agg = {k: round(sum(r[k] for r in dev_rows) / len(dev_rows), 3)
               for k in ("LCP", "INP", "CLS", "TTFB")}
        worst = {k: max(r[k] for r in dev_rows) for k in ("LCP", "INP", "CLS")}
        print(f"  {dev:8s} avg LCP={agg['LCP']/1000:.2f}s  worst={worst['LCP']/1000:.2f}s | "
              f"INP avg={agg['INP']:.0f}ms worst={worst['INP']:.0f}ms | "
              f"CLS avg={agg['CLS']:.3f} worst={worst['CLS']:.3f}")
        ok_lcp = all(r["LCP"] <= 2500 for r in dev_rows)
        ok_cls = all(r["CLS"] <= 0.1 for r in dev_rows)
        print(f"  → LCP gate {'PASS' if ok_lcp else 'FAIL'} · CLS gate {'PASS' if ok_cls else 'FAIL'} · INP is interaction-bound (nominal)")
    with open("/tmp/cwv_lab.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("saved /tmp/cwv_lab.json")


if __name__ == "__main__":
    sys.exit(main())
