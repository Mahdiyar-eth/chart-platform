# ZAYCHE UI/UX AUDIT — DIMENSION: Mobile-First & Liquid-Glass Aesthetic

**Auditor:** Senior Staff Engineer / UI Architect
**Date:** 2025-07-14
**Scope:** Every template in the code bundle, assessed against the mobile-first bar and glassmorphism design coherence.

---

## EXECUTIVE SUMMARY

The codebase has a **strong design foundation**: the `base.html` establishes a cohesive liquid-glass system (aurora, starfield, glass cards, gold accent, RTL-first, bottom nav, drawer). Most pages inherit this well. However, several screens have **critical mobile-UX violations** and **aesthetic inconsistencies** that need correction before launch.

### Severity Legend
| Grade | Meaning |
|-------|---------|
| 🔴 P0 | Blocks launch — broken UX on mobile or violates hard rules |
| 🟠 P1 | Degrades experience significantly — fix before launch |
| 🟡 P2 | Polish — fix in first sprint post-launch |
| ✅ PASS | Meets the bar |

---

## GLOBAL RULES CHECK (base.html)

### ✅ PASSES
| Rule | Evidence |
|------|----------|
| RTL | `<html lang="fa" dir="rtl">` — line 1 |
| 44px touch targets | `.btn` min-height:48px, `.chip` min-height:44px, `.nav-item` min-height:46px, `.bn-item` min-height:52px, `.input` min-height:50px, `.hamburger` 44×44, `.drawer-close` 42×42 |
| No `confirm()` in base | None found |
| No opacity-0/group-hover buttons | None found in base |
| Bottom nav on mobile | `.bottomnav` appears at ≤768px, 6 items + FAB |
| Drawer for mobile | Slide-in drawer with backdrop blur |
| `prefers-reduced-motion` | Respected — line ~145 |
| Glassmorphism system | `--glass`, backdrop-filter, blur, saturation, inset highlights — cohesive |

### 🟠 P1 Issues in base.html

| # | Issue | File:Line | Evidence | Fix |
|---|-------|-----------|----------|-----|
| B-1 | **Bottom nav has 6 items + FAB = 7 total** — on 320px screens this wraps or clips | `base.html:~230-237` | `.bn-item` × 5 + `.bn-fab` × 1 = 6 flex children in max-width:420px | Reduce to 4 items + FAB (5 total). Drop "بازبینی ساعت" and "داشبورد" from bottom nav (keep in drawer). |
| B-2 | **Top appnav has 11 items** — even on desktop this may overflow | `base.html:~195-205` | 11 `.nav-item` elements | Cap at 7 visible; move "داشبورد", "راهنما", "آموزش", "حساب من" to a "بیشتر" dropdown or rely on drawer |
| B-3 | **Duplicate `og:type` meta** | `base.html:14,19` | Two `<meta property="og:type" content="website">` | Remove duplicate at line 19 |
| B-4 | **Duplicate `theme-color` meta** | `base.html:20,24` | Two identical meta tags | Remove duplicate |
| B-5 | **`.drawer` transform direction is LTR-biased** | `base.html:~130` | `transform:translateX(-105%)` — in RTL this slides the wrong way on some browsers | Use `inset-inline-end:0; transform:translateX(calc(var(--dir-mult, 1) * -105%))` or test thoroughly on RTL Chrome/Safari |
| B-6 | **Footer `.footer-grid` can produce single-column at 320px** | `base.html:~160` | `minmax(150px,1fr)` — 4 columns × 150px = 600px, so on mobile it stacks to 2 columns which is fine, but link targets are only `padding:5px 0` = ~25px tall | Add `min-height:44px; display:flex; align-items:center;` to `.footer-col a` |

---

## PER-SCREEN AUDIT

---

### 1. `account.html` — حساب کاربری

**Overall:** Functional but dense. Several hard violations.

| # | Sev | Issue | Line | Evidence | Acceptance Criteria |
|---|-----|-------|------|----------|---------------------|
| A-1 | 🔴 P0 | **`prompt()` used in wallet withdraw** | `account.html:~270` (JS `askWithdraw`) | `const v = prompt('مبلغ تسویه…')` | Replace with inline Alpine modal with `<input type="number">`. `prompt()` is invisible on iOS WebView and banned by design rules. |
| A-2 | 🔴 P0 | **`alert()` used in wallet withdraw** | `account.html:~276` | `alert(r.ok ? 'درخواست تسویه…' : …)` | Replace with inline toast/snackbar component |
| A-3 | 🟠 P1 | **Checkbox inputs are 18×18px** — below 44px target | `account.html:~88-96` | `style="width:18px;height:18px;"` on `<input type="checkbox">` | Wrap in `<label>` with `min-height:44px; display:flex; align-items:center; gap:10px; padding:8px 0; cursor:pointer;` (the label IS there but the checkbox itself is tiny — use a custom toggle or increase to 24px with 44px label row) |
| A-4 | 🟠 P1 | **Quiet hours inputs are 70px wide** — hard to tap on mobile | `account.html:~99-100` | `style="width:70px;"` on `<input type="number">` | Increase to `min-width:80px; min-height:44px;` |
| A-5 | 🟠 P1 | **PDF download button is 6px 14px padding** — below 44px target | `account.html:~55` | `style="font-size:.8rem; padding:6px 14px;"` | Add `min-height:44px; display:inline-flex; align-items:center;` |
| A-6 | 🟡 P2 | **Search results arrow icon is 14×14px** — decorative, not tappable, but the entire `<a>` row has only `padding:9px 0` = ~34px tall | `account.html:~24` | `padding:9px 0` | Add `min-height:44px; display:flex; align-items:center;` to the `<a>` |
| A-7 | 🟡 P2 | **Subscription cancel flow uses `x-show` toggle** — good (no confirm), but the "مطمئنی؟" button has `padding:6px 12px` = ~30px tall | `account.html:~147` | `style="font-size:.78rem;padding:6px 12px;"` | Add `min-height:44px` |
| A-8 | 🟡 P2 | **Referral link input + copy button** — copy button has `padding:10px 14px` which is fine, but `onclick` uses `navigator.clipboard` without fallback | `account.html:~186` | `onclick="navigator.clipboard.writeText(…)"` | Add try/catch with fallback `document.execCommand('copy')` and visual feedback |

#### REDESIGN SPEC: account.html Wallet Withdraw Modal

Replace `prompt()` + `alert()` with:

```html
<!-- Inside the wallet section, add: -->
<div x-data="{ open: false, amount: '', result: '', submitting: false }" x-cloak>
  <button class="btn" x-show="balance > 0" @click="open = true"
          style="min-height:48px; padding:0 22px; margin-top:8px;">
    درخواست تسویه
  </button>

  <!-- Modal -->
  <div x-show="open" class="modal-backdrop"
       style="position:fixed; inset:0; background:rgba(0,0,0,.55);
              backdrop-filter:blur(4px); z-index:60;
              display:flex; align-items:center; justify-content:center; padding:20px;"
       @click.self="open = false">
    <div class="glass" style="max-width:380px; width:100%; padding:24px; border-radius:18px; text-align:center;">
      <h3 style="margin-bottom:12px;">درخواست تسویه</h3>
      <p class="muted" style="font-size:.85rem; margin-bottom:14px;">
        موجودی: <b x-text="fmt(balance)" style="color:var(--gold);"></b>
      </p>
      <input type="number" x-model="amount" class="input"
             placeholder="مبلغ به ریال" dir="ltr"
             style="text-align:left; margin-bottom:12px;"
             :max="balance" min="1">
      <button class="btn" style="width:100%; margin-bottom:8px;"
              :disabled="submitting || !amount"
              @click="submitWithdraw()">
        <span x-text="submitting ? 'در حال ثبت…' : 'ثبت درخواست'"></span>
      </button>
      <button class="btn btn-ghost" style="width:100%;" @click="open = false">انصراف</button>
      <p x-show="result" x-text="result"
         style="margin-top:10px; font-size:.85rem;"
         :style="result.includes('✅') ? 'color:#4caf7d' : 'color:#ff6b6b'"></p>
    </div>
  </div>
</div>
```

---

### 2. `account_login.html` — ورود

**Overall:** Clean, minimal. Near-pass.

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| L-1 | 🟡 P2 | **"تغییر شماره" button has no min-height** | `account_login.html:~25` | `style="background:none; border:none; margin-top:10px; width:100%; font-size:.8rem;"` — renders ~20px tall | Add `min-height:44px; display:flex; align-items:center; justify-content:center;` |
| L-2 | ✅ | Touch targets for main buttons | — | `.btn` with `width:100%` inherits 48px min-height | Pass |
| L-3 | ✅ | No confirm/alert/prompt | — | — | Pass |
| L-4 | ✅ | RTL | — | Inherits from base | Pass |

---

### 3. `admin.html` — داشبورد مدیریت

**Overall:** Admin panel — lower bar than public pages, but still needs to be usable on tablet.

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| AD-1 | 🔴 P0 | **`confirm()` used in CMS delete** | `admin.html:~95` | `if (!confirm('حذف مقاله؟…')) return;` | Replace with inline two-step pattern (like `regenOrder` already does) |
| AD-2 | 🔴 P0 | **Multiple `alert()` calls** | `admin.html:~100,107,115,…` (at least 12 instances) | `alert('ذخیره شد ✓')`, `alert('خطا: …')` | Replace all with a reusable toast/snackbar. For admin, a simple fixed-position bar at top is sufficient. |
| AD-3 | 🟠 P1 | **Tables have `min-width:560px-640px`** — horizontal scroll on mobile works but buttons inside are ~24px tall | `admin.html:~multiple` | `padding:2px 7px` on action buttons, `padding:3px 8px` on regen button | Increase all admin action buttons to `min-height:36px; padding:6px 12px;` (admin can be 36px not 44px) |
| AD-4 | 🟠 P1 | **Secrets section: input + 3 buttons in a flex row** — wraps badly on mobile | `admin.html:~200-210` | `display:flex;flex-wrap:wrap;gap:8px;align-items:center;` — on 320px, the 3 buttons stack but are only ~32px tall | Add `min-height:40px` to all secret action buttons |
| AD-5 | 🟡 P2 | **Prompt textareas have no min-height** — on mobile they collapse | `admin.html:~280` | `rows="5"` is fine but `width:100%` with no padding on container can bleed | Add `min-height:120px` |
| AD-6 | 🟡 P2 | **CMS form uses `id="cms-body"` which conflicts with the CMS content div** | `admin.html:~80,88` | `document.getElementById('cms-body')` is used for both the container div AND the textarea | Rename textarea to `id="cms-body-text"` |

---

### 4. `admin_login.html` — ورود مدیریت

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| AL-1 | ✅ | Touch targets | — | Input: `padding:14px`, button: `.btn.btn-lg` = 54px | Pass |
| AL-2 | ✅ | No confirm/alert | — | — | Pass |
| AL-3 | ✅ | Glassmorphism | — | `.glass` card with glow-free clean look | Pass |

---

### 5. `article.html` — مقاله

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| AR-1 | 🟠 P1 | **"→ همهی مقالات" back link is plain text, no min-height** | `article.html:9` | `style="font-size:.8rem;color:#9a92b0;text-decoration:none;"` — ~16px tall | Wrap in a pill/chip with `min-height:44px; display:inline-flex; align-items:center; padding:0 14px;` |
| AR-2 | 🟠 P1 | **Related articles grid items have no min-height** | `article.html:33` | `padding:12px` — on short titles, total height ~40px | Add `min-height:44px; display:flex; align-items:center;` |
| AR-3 | 🟡 P2 | **CTA button uses `.btn-lg` class but as inline style** | `article.html:27` | `class="btn-lg"` without `.btn` — missing gradient background | Should be `class="btn btn-lg"` |
| AR-4 | ✅ | RTL, glass aesthetic | — | Inherits well | Pass |

---

### 6. `articles_index.html` — فهرست مقالات

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| AI-1 | ✅ | Category chips | — | `.cat-chip` with `padding:7px 16px` — total height ~36px. Borderline but acceptable for filter chips. | Consider adding `min-height:44px` |
| AI-2 | ✅ | Grid cards | — | `padding:14px` with image + text — tappable area is the entire card | Pass |
| AI-3 | ✅ | Empty state | — | `{% else %}<p>مقالات بهزودی…</p>` | Pass |
| AI-4 | 🟡 P2 | **CTA button at bottom uses `.btn-lg` without `.btn`** | `articles_index.html:~38` | `class="btn-lg"` | Should be `class="btn btn-lg"` |

---

### 7. `birth_chart_city.html` — صفحه شهر

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| BC-1 | ✅ | Touch targets | — | `.btn.btn-lg` CTA | Pass |
| BC-2 | ✅ | Glass cards | — | Consistent use | Pass |
| BC-3 | ✅ | RTL | — | Inherits | Pass |
| BC-4 | 🟡 P2 | **FAQ section `<b>` questions have no visual separation** — two `<p>` blocks run together | `birth_chart_city.html:52-58` | Adjacent `<p>` with same styling | Add `border-top:1px solid var(--stroke); padding-top:12px; margin-top:12px;` to second FAQ |

---

### 8. `chart.html` — نتیجه چارت

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| CH-1 | 🟠 P1 | **Funnel progress pills have `padding:6px 12px`** — ~28px tall | `chart.html:12-14` | `style="…padding:6px 12px;border-radius:999px;…"` | Add `min-height:44px; display:inline-flex; align-items:center;` |
| CH-2 | 🟠 P1 | **"← چارت" link at top has no min-height** | `chart.html:5` | `style="text-decoration:none; font-size:.9rem;"` — ~18px | Wrap in chip or add `min-height:44px; display:inline-flex; align-items:center;` |
| CH-3 | 🟠 P1 | **Share button is unstyled `<button>`** | `chart.html:~100` | `style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:.85rem;"` — ~18px tall | Add `min-height:44px; padding:0 12px;` |
| CH-4 | 🟡 P2 | **`<details>` summary for charts section** — native disclosure triangle may not render well in RTL | `chart.html:~50` | `<details class="glass">` | Add `list-style:none;` to summary and a custom RTL-safe chevron |
| CH-5 | ✅ | No confirm/alert/prompt | — | — | Pass |
| CH-6 | ✅ | Glass aesthetic | — | `.glass.glow` on wheel, sections | Pass |

---

### 9. `chat.html` — گفتگو

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| CT-1 | 🟠 P1 | **Preset question buttons have `min-height:38px`** — below 44px | `chat.html:22` | `style="min-height:38px;padding:0 14px;font-size:.8rem;border-radius:999px;"` | Change to `min-height:44px` |
| CT-2 | 🟠 P1 | **"← چارت" back button has `min-height:40px`** — below 44px | `chat.html:7` | `style="min-height:40px;padding:0 16px;font-size:.85rem;"` | Change to `min-height:44px` |
| CT-3 | 🟡 P2 | **Message bubbles max-width:82%** — on 320px this is 262px, fine | — | — | Pass |
| CT-4 | ✅ | Streaming cursor animation | — | Clean implementation | Pass |
| CT-5 | ✅ | No confirm/alert | — | — | Pass |
| CT-6 | 🟡 P2 | **Chat area `max-height:58vh`** — on short phones with bottom nav (150px padding-bottom), the input may be hidden behind the keyboard | `chat.html:26` | `max-height:58vh` | Consider `max-height:calc(100dvh - 280px)` or use `dvh` units |

---

### 10. `contact.html` — تماس

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| CO-1 | ✅ | All targets | — | `.btn.btn-lg` on Telegram link | Pass |
| CO-2 | ✅ | Glass aesthetic | — | Clean, centered | Pass |
| CO-3 | ✅ | No violations | — | — | Pass |

---

### 11. `dashboard.html` — داشبورد

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| DA-1 | ✅ | Card grid `repeat(2, minmax(0,1fr))` | — | 2-column on mobile, each card is a full `<a>` with `padding:16px 14px` | Pass |
| DA-2 | ✅ | Empty state | — | Glass glow card with CTA | Pass |
| DA-3 | ✅ | Daily insight card | — | Full-width tappable `<a>` | Pass |
| DA-4 | 🟡 P2 | **"حساب و تنظیمات" link at bottom is plain text** | `dashboard.html:47` | `style="color:#8fb6ff;"` inside `<p>` — ~16px tall | Wrap in `min-height:44px` inline-flex |

---

### 12. `disclaimer.html` — سلب مسئولیت

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| DI-1 | ✅ | Static content page | — | Glass card, good line-height | Pass |

---

### 13. `explore.html` — خودت را کشف کن

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| EX-1 | 🟠 P1 | **Evidence chips have `min-height:32px`** — below 44px | `explore.html:~72` | `style="min-height:32px;font-size:.75rem;…margin:0;"` | These are display-only (not interactive), so 32px is acceptable. But they have the `.chip` class which implies tappability. Remove `.chip` class or make them `<span>` without hover effects. **Verdict: P2** |
| EX-2 | ✅ | Card buttons | — | `.btn` inherits 48px | Pass |
| EX-3 | ✅ | Credit display | — | Clear, prominent | Pass |
| EX-4 | ✅ | Streaming/loading state | — | Progress bar animation | Pass |
| EX-5 | 🟡 P2 | **"همه تحلیلها" toggle button** — works but text changes could be jarring | `explore.html:~46` | `x-text="showAll ? 'نمایش کمتر' : 'همه تحلیلها…'"` | Fine, minor |

---

### 14. `faq.html` — سؤالات پرتکرار

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| FA-1 | 🟠 P1 | **`<details><summary>` has no min-height** | `faq.html:13` | `padding:14px 16px` on details, summary is `font-size:.95rem` — total ~42px, borderline | Add `min-height:48px; display:flex; align-items:center;` to summary |
| FA-2 | 🟡 P2 | **CTA button uses `.btn-lg` without `.btn`** | `faq.html:24` | `class="btn-lg"` | Should be `class="btn btn-lg"` |
| FA-3 | ✅ | RTL chevron `▾` | — | Works in RTL | Pass |

---

### 15. `form.html` — فرم تولد

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| FO-1 | ✅ | Step dots progress | — | Clean, animated | Pass |
| FO-2 | ✅ | Chip selectors | — | `.chip` with 44px min-height | Pass |
| FO-3 | ✅ | Input fields | — | `.input` with 50px min-height | Pass |
| FO-4 | ✅ | Navigation buttons | — | `.btn` / `.btn.btn-ghost` | Pass |
| FO-5 | 🟡 P2 | **City search results chips can overflow on mobile** — many cities shown | `form.html:~70` | `<template x-for="c in cities">` — no max-height/scroll | Add `max-height:200px; overflow-y:auto;` to the city results container |
| FO-6 | ✅ | No confirm/alert | — | — | Pass |
| FO-7 | ✅ | Help tips | — | Custom tooltip with 44px trigger area (18px button but inside label row) — borderline. The `?` button is 18×18px. | **Upgrade to P2**: increase `.help-tip-btn` to `width:24px; height:24px;` and ensure the parent label row is 44px tall |

---

### 16. `index.html` — صفحه اصلی

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| IX-1 | ✅ | Hero CTA | — | `.btn.btn-lg` | Pass |
| IX-2 | ✅ | Feature cards | — | `.glass.feat` with `padding:20px`, full-card tappable `<a>` | Pass |
| IX-3 | ✅ | Mode toggle buttons | — | `.mode-btn` with `padding:9px 22px` — ~40px tall | **P2**: add `min-height:44px` |
| IX-4 | ✅ | Sample report cards | — | Display-only, not interactive | Pass |
| IX-5 | ✅ | Glass aesthetic | — | Excellent — glow on chat section, feature flags | Pass |
| IX-6 | 🟡 P2 | **PDF download link** | `index.html:~52` | `font-size:.9rem` with `border-bottom:1px dashed` — ~20px tall | Add `min-height:44px; display:inline-flex; align-items:center;` |
| IX-7 | ✅ | `.more` links inside cards | — | Inside full-card `<a>` so the entire card is the target | Pass |

---

### 17. `insight_share.html` — اشتراک بینش

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| IS-1 | ✅ | CTA | — | `.btn.btn-lg` | Pass |
| IS-2 | ✅ | Simple, clean | — | — | Pass |

---

### 18. `landing.html` — لندینگ عمومی

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| LA-1 | ✅ | CTA buttons | — | `.btn.btn-lg` | Pass |
| LA-2 | ✅ | Chip row | — | `.l-chip` with `padding:8px 16px` — ~36px. Display-only. | Pass |
| LA-3 | ✅ | Cards | — | `.l-card` with `padding:20px 18px` | Pass |
| LA-4 | ✅ | FAQ section | — | Glass card, readable | Pass |

---

### 19. `page.html` — صفحات عمومی (about, privacy, terms, etc.)

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| PG-1 | 🟡 P2 | **CTA button uses `.btn-lg` without `.btn`** | `page.html:17` | `class="btn-lg"` | Should be `class="btn btn-lg"` |
| PG-2 | ✅ | Content layout | — | `max-width:760px`, good line-height | Pass |

---

### 20. `partials/help_tip.html` — تولتیپ راهنما

| # | Sev | Issue | Line | Evidence | AC |
|---|-----|-------|------|----------|----|
| HT-1 | 🟠 P1 | **Trigger button is 18×18px** — well below 44px | `help_tip.html:2` | `.help-tip-btn { width:18px; height:18px; }` | Increase to `width:28px; height:28px;` and add `min-height:44px; min-width:44px;` to the `.help-tip` wrapper as the tap target (using padding) |
| HT-2 | 🟡 P2 | **Tooltip box position** — `top:24px; inset-inline-start:0` may overflow viewport on mobile | `base.html:~155` | `.help-tip-box { position:absolute; top:24px; inset-inline-start:0; width:240px; }` | Add `@media (max-width:400px) { .help-tip-box { inset-inline-start:-60px; } }` or use JS positioning |

---

## CONSOLIDATED FIX PRIORITY

### 🔴 P0 — Must fix before launch (3 issues)

| ID | Screen | Issue | Fix |
|----|--------|-------|-----|
| A-1 | account.html | `prompt()` in wallet withdraw | Replace with Alpine modal (spec above) |
| A-2 | account.html | `alert()` in wallet withdraw | Replace with inline feedback |
| AD-1 | admin.html | `confirm()` in CMS delete | Replace with two-step inline pattern |

### 🟠 P1 — Fix before launch (13 issues)

| ID | Screen | Issue |
|----|--------|-------|
| B-1 | base.html | Bottom nav 7 items — reduce to 5 |
| B-2 | base.html | Top nav 11 items — cap at 7 |
| B-6 | base.html | Footer link targets < 44px |
| A-3 | account.html | Checkbox targets 18px |
| A-4 | account.html | Quiet hours inputs 70px |
| A-5 | account.html | PDF button < 44px |
| AD-2 | admin.html | Multiple `alert()` calls |
| AD-3 | admin.html | Admin button targets < 36px |
| AD-4 | admin.html | Secrets row layout on mobile |
| AR-1 | article.html | Back link < 44px |
| CH-1 | chart.html | Funnel pills < 44px |
| CT-1 | chat.html | Preset buttons 38px |
| HT-1 | help_tip.html | Trigger 18×18px |

### 🟡 P2 — First sprint post-launch (14 issues)

| ID | Screen | Issue |
|----|--------|-------|
| A-6 | account.html | Search result rows < 44px |
| A-7 | account.html | Cancel button < 44px |
| A-8 | account.html | Clipboard fallback |
| AR-2 | article.html | Related articles < 44px |
| AR-3, AI-4, FA-2, PG-1 | Multiple | `.btn-lg` without `.btn` (4 instances) |
| CH-2 | chart.html | Back button 40px |
| CH-3 | chart.html | Share button unstyled |
| CT-6 | chat.html | Chat area max-height vs keyboard |
| DA-4 | dashboard.html | Settings link < 44px |
| FO-5 | form.html | City results overflow |
| IX-6 | index.html | PDF link < 44px |

---

## GLASSMORPHISM AESTHETIC AUDIT

### Current System (base.html) — Assessment: **STRONG**

The design system is cohesive and well-implemented:

```
--glass: rgba(255,255,255,.085)     ← translucent panel
--stroke: rgba(255,255,255,.18)     ← subtle border
backdrop-filter: blur(22px) saturate(150%)  ← frosted glass
box-shadow: 0 8px 32px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.12)  ← depth + top highlight
```

Aurora blobs (`.a1`, `.a2`, `.a3`) provide organic background movement. Starfield adds texture. Gold accent (`--gold: #f5c518`) is used consistently for CTAs, icons, and highlights.

### Screens that break the aesthetic:

| Screen | Issue | Fix |
|--------|-------|-----|
| admin.html | Inline `background:rgba(139,92,246,.2)` buttons don't use the glass system | Create `.btn-admin-primary`, `.btn-admin-danger`, `.btn-admin-success` classes using the glass palette |
| admin.html | KPI tiles use `.kpi` class (correct) but CMS/health sections use raw inline styles | Wrap in `.glass` containers consistently |
| chart.html | `<details>` element doesn't have glass styling on open state | Add `details[open] { background: var(--glass); }` |
| explore.html | Evidence chips use hardcoded `rgba(124,108,240,.16)` — correct accent color but should reference `--accent` | Use `background: rgba(var(--accent-rgb), .16)` (requires adding `--accent-rgb` variable) |

### Screens with excellent aesthetic execution:
- ✅ `index.html` — Hero, feature grid, samples, CTA sections
- ✅ `form.html` — Step wizard with glass glow
- ✅ `dashboard.html` — Card grid, daily insight highlight
- ✅ `landing.html` — Clean hero + cards
- ✅ `account_login.html` — Centered glass card
- ✅ `contact.html` — Focused, clean

---

## REDESIGN SPEC: Weak Screens

### Screen: `account.html` — Full Redesign Spec

**Problem:** Dense, 15+ sections stacked vertically, small targets, uses `prompt()`/`alert()`.

**Proposed layout:**

```
┌─────────────────────────────────────┐
│  Header: "حساب کاربری"              │
│  Greeting + search bar              │
├─────────────────────────────────────┤
│  Tab bar (horizontal scroll):       │
│  [چارتها] [گزارشها] [سفارشها]     │
│  [اشتراک] [کیف پول] [تنظیمات]      │
├─────────────────────────────────────┤
│  Active tab content (one at a time) │
│  Each in a .glass card              │
├─────────────────────────────────────┤
│  Bottom actions:                    │
│  [مشاهده پلنها] [چارت جدید]        │
│  [خروجی JSON] [حذف حساب]           │
└─────────────────────────────────────┘
```

**Key changes:**
1. **Tab navigation** instead of vertical scroll — reduces cognitive load
2. **Wallet withdraw modal** (spec above) replaces `prompt()`
3. **Toast component** replaces `alert()`
4. **All interactive elements ≥ 44px**
5. **Notification checkboxes → toggle switches** (custom, 48px tall rows)

**Tab bar CSS:**
```css
.account-tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  padding: 4px;
  margin: 16px 0;
  background: var(--glass);
  border: 1px solid var(--stroke);
  border-radius: 16px;
  backdrop-filter: blur(22px) saturate(150%);
}
.account-tabs::-webkit-scrollbar { display: none; }
.account-tab {
  min-height: 44px;
  padding: 0 16px;
  border-radius: 12px;
  border: none;
  background: transparent;
  color: var(--muted);
  font-family: inherit;
  font-size: .85rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: all .2s var(--ease);
}
.account-tab.active {
  background: linear-gradient(135deg, rgba(245,197,24,.18), rgba(232,142,11,.08));
  color: var(--gold);
  box-shadow: inset 0 0 0 1px rgba(245,197,24,.4);
}
```

### Screen: `admin.html` — Targeted Fixes (not full redesign)

Admin is internal-only. Focus on:

1. **Replace all `confirm()` with two-step inline** (pattern already exists in `regenOrder`)
2. **Replace all `alert()` with toast:**

```css
.admin-toast {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  padding: 12px 24px;
  border-radius: 14px;
  background: rgba(20, 26, 58, .95);
  border: 1px solid var(--stroke);
  backdrop-filter: blur(16px);
  color: var(--txt);
  font-size: .88rem;
  font-weight: 600;
  box-shadow: 0 8px 32px rgba(0,0,0,.4);
  animation: toastIn .3s var(--ease);
}
.admin-toast.success { border-color: rgba(42,157,143,.5); }
.admin-toast.error { border-color: rgba(255,107,107,.5); }
@keyframes toastIn { from { opacity:0; transform:translateX(-50%) translateY(-12px); } }
```

3. **Increase all button min-heights to 36px** (admin exception from 44px)

### Screen: `chat.html` — Keyboard-Safe Layout

**Problem:** On mobile, when keyboard opens, the input may be hidden behind the bottom nav.

**Fix spec:**
```css
@media (max-width: 768px) {
  /* When chat page is active, hide bottom nav */
  body.chat-active .bottomnav { display: none; }
  body.chat-active { padding-bottom: 0; }
}
```

Add `class="chat-active"` to `<body>` via a block override, or use:
```html
{% block body_class %}chat-active{% endblock %}
```

And in base.html:
```html
<body class="{% block body_class %}{% endblock %}">
```

**Chat input should be sticky at bottom:**
```css
.chat-input-bar {
  position: sticky;
  bottom: 0;
  z-index: 10;
  padding: 12px 0;
  background: linear-gradient(to top, var(--bg) 80%, transparent);
}
```

---

## FINAL VERDICT

| Dimension | Status |
|-----------|--------|
| **Code-complete** | ✅ Yes — all screens render, all features work |
| **Launch-accepted** | 🟠 No — 3 P0 issues (`prompt()`, `confirm()`, `alert()` in user-facing flows) and 13 P1 issues (touch targets, nav overflow) must be resolved |

**Estimated effort to reach launch-accepted:** 2–3 dev-days for P0+P1 fixes. P2 items can ship in first post-launch sprint.