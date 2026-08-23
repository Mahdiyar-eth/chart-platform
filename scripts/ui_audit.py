#!/usr/bin/env python3
"""C3 - page-by-page UI/UX audit (18 checks x 5 viewports) per HERMES-PLAN-v1.

Runs against a LOCAL uvicorn instance (default 127.0.0.1:8798) using Playwright.
Output: docs/qa/UI-AUDIT-<date>.md + JSON + screenshots dir.

Usage:
    python scripts/ui_audit.py [--base http://127.0.0.1:8798] [--pages /,/plans]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

THEME = os.environ.get("AUDIT_THEME", "dark")

VIEWPORTS = [(320, 690), (375, 812), (414, 896), (768, 1024), (1280, 800)]

DEFAULT_PAGES = [
    "/", "/plans", "/birth-form", "/explore", "/today", "/sky",
    "/learn", "/articles", "/faq", "/contact", "/privacy", "/terms",
    "/refund", "/account/login", "/dashboard", "/account",
]

# checks that need no auth; chart-bound pages are appended when --chart given.
CONSOLE_IGNORE = ["favicon", "Autofocus processing"]

CHECK_JS = r"""
() => {
  const out = {};
  // 1 horizontal scroll
  out.hscroll = document.documentElement.scrollWidth > window.innerWidth + 1;
  // 4 touch targets
  const badTouch = [];
  document.querySelectorAll('a,button,input,select,[role=button]').forEach(el => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') return;
    if (el.disabled) return;
    if (r.width > 0 && (r.width < 40 || r.height < 40)) {
      const txt = (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30);
      badTouch.push({t: el.tagName.toLowerCase(), w: Math.round(r.width), h: Math.round(r.height), txt});
    }
  });
  out.touch = badTouch.slice(0, 8);
  out.touchCount = badTouch.length;
  // 6 images without alt
  out.imgNoAlt = [...document.querySelectorAll('img:not([alt])')].length;
  // 7 svg icons without aria-hidden or title
  out.svgNoA11y = [...document.querySelectorAll('svg')].filter(s =>
    !s.getAttribute('aria-hidden') && !s.querySelector('title') && !s.closest('button')).length;
  // 8 inputs without label
  out.inputNoLabel = [...document.querySelectorAll('input:not([type=hidden])')].filter(i => {
    if (i.getAttribute('aria-label')) return false;
    if (i.id && document.querySelector('label[for="' + i.id + '"]')) return false;
    const ph = i.getAttribute('placeholder');
    return !ph; // placeholder counts as minimal label here; strict check separately
  }).length;
  // 9 heading order
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => parseInt(h.tagName[1]));
  let h1 = hs.filter(x => x === 1).length;
  let jump = 0, prev = hs[0] || 1;
  for (const h of hs.slice(1)) { if (h - prev > 1) jump++; prev = h; }
  out.h1Count = h1; out.headingJumps = jump;
  // 11 RTL
  out.dir = document.documentElement.getAttribute('dir');
  // 13 text overflow
  let overflow = 0;
  document.querySelectorAll('.glass,.card,p,h1,h2,h3,a,button').forEach(el => {
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX !== 'auto'
        && getComputedStyle(el).overflowX !== 'scroll' && el.clientWidth > 0) overflow++;
  });
  out.textOverflow = overflow;
  // 16 bottom-nav overlap: last content element not hidden under fixed bottom bar
  const bar = document.querySelector('[data-bottomnav], nav.bottom, .bottom-dock, [class*=bottom]');
  let overlapped = false;
  if (bar && getComputedStyle(bar).position === 'fixed') {
    const pad = parseFloat(getComputedStyle(document.body).paddingBottom) || 0;
    overlapped = pad < bar.getBoundingClientRect().height * 0.6;
  }
  out.bottomOverlap = overlapped;
  // 17 safe-area
  out.safeArea = /env\(safe-area/.test([...document.styleSheets].length ? 'checked' : '') ||
                 !!document.querySelector('[style*=safe-area]') || (() => {
                   for (const sh of document.styleSheets) {
                     try { for (const r of sh.cssRules) if (r.cssText && r.cssText.includes('safe-area-inset-bottom')) return true; }
                     catch (e) {}
                   }
                   return false;
                 })();
  // 18 empty state heuristic: pages with lists but zero items should show .empty-state
  out.hasEmptyStateClass = !!document.querySelector('.empty-state');
  return out;
}
"""

CLS_OBSERVER = r"""
() => new Promise((resolve) => {
  const out = {consoleErrors: 0};
  resolve(out);
})
"""


def contrast_ok(page):
    """Check 5 - sample key text elements' contrast ratio (alpha-aware)."""
    js = r"""
() => {
  const BASE = document.documentElement.getAttribute("data-theme") === "light" ? [244,245,251] : [13,20,48];
  function parse(c) {
    const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
  }
  function blend(fg, bg) {
    const a = fg[3];
    return [fg[0]*a+bg[0]*(1-a), fg[1]*a+bg[1]*(1-a), fg[2]*a+bg[2]*(1-a), 1];
  }
  function lum(rgb) {
    if (!rgb) return null;
    const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; };
    return .2126 * f(rgb[0]) + .7152 * f(rgb[1]) + .0722 * f(rgb[2]);
  }
  function gradColor(el) {
    const gi = getComputedStyle(el).backgroundImage;
    const m = gi && gi.match(/(rgba?\([\d.]+,\s*[\d.]+,\s*[\d.]+(?:,\s*[\d.]+)?\))/);
    return m ? parse(m[1]) : null;
  }
  function bgOf(el) {
    let acc = BASE.slice().concat([1]);
    let e = el;
    while (e) {
      const g = gradColor(e);
      if (g) {                       // gradient first stop may be translucent — alpha-blend it
        if (g[3] < 1) { acc = blend(g, acc); }
        else return g;
      }
      const cc = parse(getComputedStyle(e).backgroundColor);
      if (cc && cc[3] > 0) acc = blend(cc, acc);
      e = e.parentElement;
    }
    return acc;
  }
  let fails = 0, checked = 0;
  document.querySelectorAll('p, span, a, button, label, h1, h2, h3').forEach(el => {
    if (el.children.length > 2) return;
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length < 3) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || +st.opacity === 0) return;
    if (el.getClientRects().length === 0) return;   // not rendered (e.g. hidden mobile nav)
    const l1 = lum(parse(st.color)), l2 = lum(bgOf(el));
    if (l1 === null || l2 === null) return;
    const hi = Math.max(l1, l2), lo = Math.min(l1, l2);
    const ratio = (hi + .05) / (lo + .05);
    checked++;
    const size = parseFloat(st.fontSize), bold = +st.fontWeight >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    if (ratio < (large ? 3 : 4.5)) fails++;
  });
  return {fails, checked};
}
"""
    try:
        res = page.evaluate(js)
        n = max(res["checked"], 1)
        return {"fail_ratio": round(res["fails"], 2), "checked": res["checked"],
                "pct": round(100 * res["fails"] / n, 2)}
    except Exception as e:
        return {"error": str(e)[:60]}


def audit_page(page, base, path, shots_dir, date_tag, context=None):
    rec = {"path": path, "sizes": {}}
    console_errors = []
    failed_requests = []

    def on_console(msg):
        if msg.type in ("error",):
            t = msg.text
            # 401/403 on /api/* = expected for guest sessions, not a page defect
            if "401" in t or "403" in t or "404" in t and "/api/" in t:
                return
            if any(k.lower() in t.lower() for k in CONSOLE_IGNORE):
                return
            console_errors.append(t[:120])

    page.on("console", on_console)
    page.on("pageerror", lambda e: console_errors.append(str(e)[:120]))
    page.on("response", lambda r: failed_requests.append(f"{r.status} {r.url[-60:]}")
            if r.status >= 400 and "api/credits" not in r.url and "api/wallet" not in r.url else None)

    for (w, h) in VIEWPORTS:
        page.set_viewport_size({"width": w, "height": h})
        url = base + path
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if THEME == "light":  # X19/R13: audit the LIGHT theme too
            page.evaluate("try{localStorage.setItem('zayche-theme','light')}catch(e){}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(350)
        d = page.evaluate(CHECK_JS)
        d["contrast"] = contrast_ok(page)
        shot = os.path.join(shots_dir, f"{date_tag}{path.replace('/', '_') or '_root'}-{w}.png")
        try:
            page.screenshot(path=shot)
        except Exception:
            pass
        rec["sizes"][f"{w}"] = d

    rec["console_errors"] = console_errors[:10]
    rec["failed_requests"] = failed_requests[:10]

    # focus-visible check (check 10) at default mobile width
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(base + path, wait_until="networkidle", timeout=30000)
    # keyboard-realistic: real Tab presses via Playwright (CDP), then inspect activeElement
    async_tab_js = r"""
async (n) => {
  const seen = [];
  let missing = 0;
  for (let i = 0; i < n; i++) {
    window.__hermes_tab && window.__hermes_tab();
  }
  return null;
}
"""

    # real Tab presses (keyboard-realistic focus-visible check)
    try:
        page.keyboard.press("Tab")
        missing = 0
        checked = 0
        prev = None
        for _ in range(25):
            page.keyboard.press("Tab")
            info = page.evaluate(
                "() => { const el=document.activeElement; if(!el||el===document.body) return null;"
                " const st=getComputedStyle(el);"
                " return {tag:el.tagName,"
                " outline:(st.outlineStyle!=='none'&&parseFloat(st.outlineWidth)>0),"
                " ring:((st.boxShadow||'none')!=='none')}; }"
            )
            if not info:
                break
            checked += 1
            if not (info.get("outline") or info.get("ring")):
                missing += 1
        rec["focus_missing"] = missing
    except Exception:
        rec["focus_missing"] = None

    # CLS/LCP (checks 14/15) — quick lab pass at 375px on a FRESH load
    # (buffered entries from earlier viewport changes must not count)
    try:
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(200)
    except Exception:
        pass
    perf_js = r"""
() => new Promise((resolve) => {
  const o = {CLS: 0, LCP: 0};
  try {
    new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) o.CLS += e.value; })
      .observe({type: 'layout-shift', buffered: true});
    new PerformanceObserver(l => { const e = l.getEntries().pop(); if (e) o.LCP = e.startTime; })
      .observe({type: 'largest-contentful-paint', buffered: true});
  } catch (err) {}
  setTimeout(() => resolve({CLS: +o.CLS.toFixed(4), LCP: Math.round(o.LCP)}), 2500);
})
"""
    try:
        # fresh page = clean performance timeline (no prior viewport/scroll history)
        ppage = context.new_page() if context is not None else None
        target = ppage or page
        await_like = target.goto(base + path, wait_until="domcontentloaded", timeout=30000)
        rec["perf"] = target.evaluate(perf_js)
        if ppage:
            ppage.close()
    except Exception:
        rec["perf"] = {}
    if os.getenv("AUDIT_DEBUG"):
        try:
            rec["_shifts"] = page.evaluate("""()=>new Promise(res=>{
              const out=[];
              new PerformanceObserver(l=>{for(const e of l.getEntries()){ if(!e.hadRecentInput){ for(const s of (e.sources||[])){ const n=s.node; out.push({v:+e.value.toFixed(3),tag:n&&n.tagName,cls:String((n&&n.className)||'').slice(0,40)}); } } }}).observe({type:'layout-shift',buffered:true});
              setTimeout(()=>res(out.slice(0,6)),2000);
            })""")
        except Exception:
            pass

    return rec


def verdict(rec) -> list[str]:
    issues = []
    for w, d in rec["sizes"].items():
        tag = f'{rec["path"]} @{w}px'
        if d.get("hscroll"): issues.append(f"{tag}: افقی اسکرول")
        if d.get("touchCount"): issues.append(f'{tag}: {d["touchCount"]} هدف لمسی <40px')
        if d.get("imgNoAlt"): issues.append(f'{tag}: {d["imgNoAlt"]} img بدون alt')
        if d.get("svgNoA11y"): issues.append(f'{tag}: {d["svgNoA11y"]} svg بدون aria/title')
        if d.get("inputNoLabel"): issues.append(f'{tag}: {d["inputNoLabel"]} input بدون label')
        if d.get("h1Count", 1) != 1: issues.append(f'{tag}: h1 count={d.get("h1Count")}')
        if d.get("headingJumps"): issues.append(f'{tag}: {d["headingJumps"]} پرش سطح هدینگ')
        if d.get("dir") != "rtl": issues.append(f'{tag}: dir={d.get("dir")}')
        if d.get("textOverflow"): issues.append(f'{tag}: {d["textOverflow"]} سرریز متن')
        c = d.get("contrast") or {}
        if c.get("pct", 0) > 5: issues.append(f'{tag}: کنتراست {c.get("pct")}% زیر حد ({c.get("fail_ratio")} عنصر)')
        if d.get("bottomOverlap"): issues.append(f"{tag}: محتوا زیر نوار پایین")
        if not d.get("safeArea"): issues.append(f"{tag}: safe-area نیست")
    if rec.get("console_errors"): issues.append(f'{rec["path"]}: {len(rec["console_errors"])} خطای کنسول')
    if rec.get("failed_requests"): issues.append(f'{rec["path"]}: {len(rec["failed_requests"])} درخواست ≥400')
    fm = rec.get("focus_missing")
    if fm: issues.append(f'{rec["path"]}: {fm} عنصر بدون فوکوس‌مشخص')
    p = rec.get("perf") or {}
    if p.get("CLS", 0) > 0.1: issues.append(f'{rec["path"]}: CLS={p.get("CLS")}')
    if p.get("LCP", 0) > 2500: issues.append(f'{rec["path"]}: LCP={p.get("LCP")}ms')
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8798")
    ap.add_argument("--pages", default=",".join(DEFAULT_PAGES))
    ap.add_argument("--limit-pages", type=int, default=0)
    args = ap.parse_args()

    date_tag = datetime.date.today().isoformat()
    qa_dir = "docs/qa"
    shots_dir = os.path.join(qa_dir, f"ui-audit-{date_tag}")
    os.makedirs(shots_dir, exist_ok=True)

    pages = [p.strip() for p in args.pages.split(",") if p.strip()]
    if args.limit_pages: pages = pages[: args.limit_pages]

    results, all_issues = [], []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": 375, "height": 812})
        for path in pages:
            try:
                rec = audit_page(pg, args.base, path, shots_dir, date_tag, context=pg.context)
            except Exception as e:
                rec = {"path": path, "error": str(e)[:160], "sizes": {}}
            results.append(rec)
            iss = verdict(rec)
            all_issues.extend(iss)
            status = "OK" if not iss else f"{len(iss)} issue(s)"
            print(f'{path:22s} {status}')
            for i in iss: print("   -", i)
        br.close()

    md = [f"# UI Audit — {date_tag}", "",
          f"- Pages: {len(results)} · Viewports: {', '.join(str(w) for w, _ in VIEWPORTS)}",
          f"- Total findings: **{len(all_issues)}**", ""]
    md.append("| صفحه | یافتهها |")
    md.append("|---|---|")
    for rec in results:
        iss = verdict(rec)
        md.append(f'| `{rec.get("path")}` | ' + ("<br>".join(iss) if iss else "✅") + " |")
    md.append("")
    json_path = os.path.join(qa_dir, f"UI-AUDIT-{date_tag}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    report = os.path.join(qa_dir, f"UI-AUDIT-{date_tag}.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("report:", report)
    print("json:", json_path)
    print("TOTAL FINDINGS:", len(all_issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
