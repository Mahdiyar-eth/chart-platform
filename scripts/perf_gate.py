"""REDESIGN-MASTER §9.6-6 — performance budget gate (the last final-gate item).

Measures on the LIVE site with 4x CPU throttle:
  - FCP  <= 300ms   for / and /plans
  - p95 scroll-frame time <= 20ms for / and /plans
  - backdrop-filter count <= 6
  - animated elements    <= 20

Exit code 0 only when every budget holds. Results -> docs/qa/redesign/perf.json
"""
import json
import statistics
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://chart.negar.io"
OUT = Path("docs/qa/redesign")
PAGES = ["/", "/plans"]
WIDTH = 390


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            viewport={"width": WIDTH, "height": 844},
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})

        for path in PAGES:
            page.goto(BASE + path, wait_until="networkidle", timeout=30000)
            fcp = page.evaluate(
                """new Promise(res => {
                     new PerformanceObserver(l => {
                       for (const e of l.getEntries())
                         if (e.name === 'first-contentful-paint') res(Math.round(e.startTime));
                     }).observe({type:'paint', buffered:true});
                   })"""
            )
            frames = page.evaluate(
                """async () => {
                     const t = [];
                     let last = performance.now();
                     for (let i = 0; i < 60; i++) {
                       window.scrollTo(0, document.documentElement.scrollHeight * (i % 10) / 10);
                       await new Promise(r => requestAnimationFrame(now => {
                         const now2 = performance.now();
                         t.push(now2 - last); last = now2; r();
                       }));
                       await new Promise(r => setTimeout(r, 8));
                     }
                     return t.map(x => Math.round(x));
                   }"""
            )
            p95 = int(statistics.quantiles(frames, n=20)[18]) if len(frames) >= 20 else max(frames or [0])
            backdrop, animated = page.evaluate(
                """([() => {
                     let n = 0;
                     for (const el of document.querySelectorAll('*')) {
                       const s = getComputedStyle(el);
                       if ((s.backdropFilter && s.backdropFilter !== 'none') ||
                           (s.webkitBackdropFilter && s.webkitBackdropFilter !== 'none')) n++;
                     }
                     return n;
                   }, () => {
                     let n = 0;
                     for (const el of document.querySelectorAll('*')) {
                       const an = el.getAnimations ? el.getAnimations({subtree:false}) : [];
                       if (an.length) n++;
                     }
                     return n;
                   }][0]() )"""
            ) if False else (
                page.evaluate(
                    "() => { let n=0; for (const el of document.querySelectorAll('*')) "
                    "{ const s=getComputedStyle(el); if ((s.backdropFilter&&s.backdropFilter!=='none')"
                    "||(s.webkitBackdropFilter&&s.webkitBackdropFilter!=='none')) n++; } return n; }"
                ),
                page.evaluate(
                    "() => { let n=0; for (const el of document.querySelectorAll('*')) "
                    "{ try { if (el.getAnimations().length) n++; } catch(e){} } return n; }"
                ),
            )
            row = {"page": path, "fcp_ms": fcp, "p95_frame_ms": p95,
                   "backdrop": backdrop, "animated": animated}
            results.append(row)
            if fcp > 300:
                failures.append(f"{path}: FCP {fcp}ms > 300ms")
            if p95 > 20:
                failures.append(f"{path}: p95 frame {p95}ms > 20ms")
            if backdrop > 6:
                failures.append(f"{path}: backdrop-filter {backdrop} > 6")
            if animated > 20:
                failures.append(f"{path}: animated elements {animated} > 20")

        browser.close()

    (OUT / "perf.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1))
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("ALL PERF BUDGETS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
