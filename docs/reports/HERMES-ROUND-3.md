# گزارش هرمس — دور ۳ (تکمیل مرحلهٔ ۰: C1 + G1)

**مدل:** deepseek-v4-flash · **تاریخ:** 2026-08-21 · **برنچ کاری:** `hermes/plan-v1-r1`
**کامیتها:** C1=`433e425` · G1 (این دور) در انتهای فایل

---

## 🎯 C1 — استخراج دیزاینسیستم
**هدف:** پیشنیاز همهٔ کارهای UI — استخراج CSS درونخطی `base.html` به سه فایل + کشباستینگ.

| فایل | نقش | وضعیت |
|---|---|---|
| `app/static/css/tokens.css` | `:root` — ۶۹ توکن (رنگ، فاصلهٔ ۸pt، تایپوگرافی، شعاع، سایه، بلور، z-index) | ✅ ۱۷۶۸ b |
| `app/static/css/base.css` | **کپی وفادارِ کامل** CSS اصلی (۱۸۸۱۱ b) — توکنشده، **۰ گمشدن قاعده** | ✅ |
| `app/static/css/components.css` | کتابخانهٔ افزودنی (کلاسهای جدید `.card/.field/.badge/.skeleton/.empty-state/.locked-panel`) | ✅ ۲۴۲۸ b |

**تصمیم کلیدی:** بهجای دستنویسی (که ریسک گمکردن ۳۱ سلکتور صفحه-خاص دارد)، `base.css` را **مکانیکی از منبع اصلی** ساختم و هر `#hex` را با `var(--x)` (همارزش) جایگزین کردم. شمارش: `131/131` سلکتور حفظ شد، `0` `#hex`، `0` ویژگی فیزیکی.

**کشباستینگ:** `?v={{ asset_version }}` از هش فایلها (افزوده به context از طریق `templates.env.globals`).

**Rigorous checks:**
- `0` hex در `base.css` و `components.css` (فقط `tokens.css`).
- `0` ویژگی فیزیکی (`margin-left/right`, `padding-left/right`, `text-align:left/right`) در هر سه فایل.
- **همهٔ ۴۷ `var(--x)` استفادهشده → تعریفشده** در tokens (۰ undefined).
- **تست پذیرش:** `test_design_system_c1.py` — **۵ passed.**
- **اثبات بصری (Playwright، ویوپورت موبایل ۳۹۰×۸۴۴):** فونت Vazirmatn ✓، پسزمینه گرادیان `rgb(35,44,102)`=`--bg-glow` ✓، شیشه `.appbar-inner`=`--glass` ✓، لوگو طلایی `--gold` ✓، هیچ var() بینگرفته. اسکرینشاتها: `docs/qa/c1-{landing,birth-form,plans}.png`.

---

## 🎯 G1 — ابزار سنجش قیف
**هدف:** ثبت رویدادهای دقیق Umami + داشبورد قیف ادمین + اثبات fire.

- **`app/static/js/track.js`** — `window.track(event, props)`:
  ۱) `umami.track(...)` اگر موجود (برای analytics.negar.io)؛ ۲) بیکن محلی `POST /api/track` (نگهدارنده، `sendBeacon`) تا داشبورد ادمین حتی بدون Umami دادهٔ واقعی داشته باشد (دفاعی در برابر بلاک). سلرف ثبتنامی: `window.FUNNEL_EVENTS = 26 رویداد` (نامها طبق پلن، عوض نشده). متصل با `defer` در `base.html`، بدون inline JS (`data-track`).
- **`POST /api/track`** — ثبت رویداد ناشناس؛ validate: `event ∈ FUNNEL_EVENTS` وگرنه ۴۰۰؛ طول فیلدها محدود. `FunnelEvent` (جدول جدید، append-only، بدون PII).
- **`GET /api/admin/funnel`** — نرخ تبدیل هر گام + ریزش + شمارش از `FunnelEvent`.
- **داشبورد ادمین** — بخش «📊 Funnel (G1)» در `admin.html` که `/api/admin/funnel` را fetch کرده و جدول گام/تعداد/تبدیل/ریزش را رندر میکند.
- **Instrumentation (نقاط کلیدی قیف):** `page_view_landing` (خودکار، `data-page="landing"`)، `birth_form_submit`، `pack_selected`، `payment_success`/`payment_failed`، `explore_card_click`.
- **Migration:** `a1c0de000002_g1_funnel_events.py` (دستی، down_revision=`a1c0de000001`).
- **matrix:** دو مسیر به `docs/AUTHORIZATION-MATRIX.md` افزوده شد.

**اثبات (واقعی، نه حدس):**
- تستهای پشتیبان `test_funnel_g1.py` → **۵ passed** (ثبت، رد غریبه، الزام `event`، محاسبهٔ قیف دقیق `[100,60,40,30,20,10,5]` با نرخ تبدیل `0.6/0.75/0.5`، ناشناسبودن).
- **اثبات مرورگر (Playwright):** `window.track` تابع است، registry=۲۶، `page_view_landing` خودکار → **DB** (۱ ردیف)، ۹ `pack_selected`، `birth_form_submit`/`explore_card_click` سرجایشان، `chart_created` دستی → DB (۱).

---

## 📊 متریکس نهایی
| دور | کار | نتیجهٔ آزمون | پوش |
|---|---|---|---|
| ۱ | Z1+E1+A1 | migration no-drift | ✅ |
| ۲ | سختسازی سوئیت | 566 سبز | ✅ |
| ۳ | C1+G1 | **576 passed, 1 skipped** | ✅ |

**هزینهٔ LLM:** $0 (هیچ endpoint پولی شلیک نشد).
**وضعیت:** مرحلهٔ ۰ کاملاً تمام. مرحلهٔ بعدی طبق ترتیب پلن: **مرحلهٔ ۱ (هستهٔ درآمد A2→A7).**
