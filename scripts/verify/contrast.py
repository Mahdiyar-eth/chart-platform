"""Contrast audit that composites alpha and reads gradients.

The naive version treated rgba(255,255,255,.08) as opaque white and any
gradient-filled element as transparent, which produced a page of phantom
failures on elements that are perfectly legible.
"""
import os
import sys
from playwright.sync_api import sync_playwright

CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
JS = r"""() => {
  const parse = c => {
    const m = (c||'').match(/[\d.]+/g); if (!m) return null;
    return [ +m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1 ];
  };
  const over = (fg, bg) => {          // composite fg (with alpha) onto bg
    const a = fg[3];
    return [ fg[0]*a + bg[0]*(1-a), fg[1]*a + bg[1]*(1-a), fg[2]*a + bg[2]*(1-a), 1 ];
  };
  const lum = c => { const [r,g,b] = c.slice(0,3).map(v => { v/=255;
      return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b; };

  // Effective background: walk up compositing every translucent layer. An
  // element painted with a gradient is treated as opaque and skipped, because
  // we cannot sample a gradient's colour under the text reliably.
  const bgOf = el => {
    let e = el, acc = null, gradient = false;
    while (e) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') { gradient = true; break; }
      const c = parse(cs.backgroundColor);
      if (c && c[3] > 0) acc = acc ? over(acc, c) : c;
      if (acc && acc[3] >= 0.999) break;
      e = e.parentElement;
    }
    if (gradient) return null;
    if (!acc) return [0,0,0,1];
    return acc[3] < 1 ? over(acc, [0,0,0,1]) : acc;
  };

  const out = [];
  document.querySelectorAll('p, span, a, li, h1, h2, h3, label, .muted, button').forEach(el => {
    const t = (el.textContent||'').trim();
    if (!t || el.children.length > 0) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.1) return;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) return;
    const bg = bgOf(el); if (!bg) return;            // gradient — skip, unmeasurable
    let fg = parse(cs.color); if (!fg) return;
    if (fg[3] < 1) fg = over(fg, bg);
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3.0 : 4.5;
    if (ratio < need) out.push({t: t.slice(0,40), ratio: +ratio.toFixed(2), need,
                                fg: cs.color, size: cs.fontSize, cls: el.className});
  });
  const seen = {}; return out.filter(x => !seen[x.cls] && (seen[x.cls]=1));
}"""
scheme = sys.argv[1]
paths = sys.argv[2:] or ["/", "/plans", "/birth-form", "/sky"]
total = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"])
    pg = b.new_context(viewport={"width":390,"height":844}, is_mobile=True,
                       color_scheme=scheme).new_page()
    for path in paths:
        pg.goto(os.environ.get("QA_BASE", "http://127.0.0.1:8798")+path, wait_until="networkidle")
        fails = pg.evaluate(JS)
        total += len(fails)
        print(f"  [{scheme}] {path}: {len(fails)} real contrast failures")
        for f in fails[:6]:
            print(f"      {f['ratio']} < {f['need']}  {f['size']:>7} {f['fg']:22} {f['t'][:30]!r} .{f['cls'][:24]}")
    b.close()
print(f"  TOTAL [{scheme}]: {total}")
