# 🔍 OPUS-REVIEW-R4 — بازبینی دور ۲.۲

**بازبین:** Opus 5 · **تاریخ:** ۲۰۲۶-۰۸-۲۳ · **حالت:** REVIEW-ONLY (هیچ کدی تغییر نکرد)
**دامنه:** `0753f93..fbf283e` — ۱ کامیت · ۱۸ فایل · ‎+۶۸۶ / ‎−۶۹
**پاسخ به:** اجرای `Z1`–`Z16` از `OPUS-REVIEW-R3`

> ### 🆕 این بار **واقعاً اجرا کردم**
> برخلاف سه دور قبل، این بار محیط کامل را ساختم و همه‌چیز را اجرا کردم:
> PostgreSQL 16 + pgvector + Redis + venv از روی `requirements.txt` + اجرای کامل pytest
> + بوت واقعی اپ + مرورگر Chromium با Playwright روی صفحهٔ گذرها.
> **نتیجهٔ اجرای واقعی سوئیت: ۹ failed · ۶۹۳ passed · ۲ skipped** — نه «۷۰۳ passed + ۱ skipped».

---

## STATUS

| محور | نتیجه |
|---|---|
| `Z1`–`Z16` | **۱۵ فیکس‌شده و تأییدشده** (بیشترشان با اجرا، نه فقط خواندن کد) · `Z14` انجام‌نشده (خود هرمس اعلام کرد) |
| کیفیت فیکس‌ها | **بهترین دور تا امروز.** `Z2` این بار **جهت درست** را گرفت: مدل اصلاح شد نه دیتابیس |
| **سوئیت تست (اجرای واقعی من)** | 🔴 **۹ شکست** — دو تای آن‌ها رگرسیون مستقیم از خودِ `Z2` |
| **CI روی GitHub Actions** | 🔴 **نمی‌تواند سبز باشد** — دو دلیل مستقل و اثبات‌شده |
| صفحهٔ گذرها (درخواست بصری هرمس) | 🟢 **استایل واقعاً درست شد** · 🟠 **ولی UX فروش شکسته است** |
| مسیر پول | 🟠 پایدارتر از هر دور دیگر؛ ولی E2E پرچم‌دار **به API پولی واقعی وصل است** |

**حکم:** دور ۲.۲ از نظر مهندسی قوی‌ترین دور بوده — `Z1` و `Z2` و `Z5` درست و اصولی‌اند.
اما ادعای «CI سبز، ۷۰۳ passed» **با اجرای مستقل تأیید نمی‌شود**، و دو مورد از شکست‌ها
مستقیماً از فیکس `Z2` همین دور می‌آیند.

---

## TRUTH-NOTES

**آنچه این بار اجرا کردم (با مدرک):**
1. ✅ `initdb` + PostgreSQL 16 روی `127.0.0.1:5432` + `CREATE EXTENSION vector` (pgvector 0.6.0)
2. ✅ `redis-server` (پاسخ `PONG`)
3. ✅ `python3 -m venv venv && pip install -r requirements.txt` ⇒ موفق
4. ✅ اجرای کامل `pytest tests/ -q` ⇒ **۹ failed، ۶۹۳ passed، ۲ skipped، ۳۴.۶۷ ثانیه**
5. ✅ بوت واقعی اپ روی `127.0.0.1:8798` با DB جدا (`chart_qa`) ⇒ `/health` = ۲۰۰
6. ✅ ساخت چارت واقعی از طریق `POST /api/charts` ⇒ ۲۰۰
7. ✅ Playwright + Chromium روی `/transits/{id}` در ۳۹۰px و ۱۲۸۰px + اسکرین‌شات
   (`docs/reviews/evidence/r4-transits-*.png`)

**آنچه اجرا نکردم:**
1. ❌ `bash scripts/ci.sh` کامل — گیت drift آن (`Z4`) نیاز به drop/create دیتابیس با دسترسی
   supervisor دارد و اسکریپت مسیرهای محلی (`venv/bin/...`, لاگ‌ها) را فرض می‌کند؛ ترجیح دادم
   به‌جای اجرای نیم‌بند، اجزایش را جدا بسنجم.
2. ❌ هیچ فراخوانی LLM پولی نزدم (طبق قانون هزینهٔ پروژه) — به همین دلیل شکست `test_x11`
   را دیدم که خودش یک یافته است (P1-1).
3. ❌ مهاجرت‌ها را روی DB تولید اجرا نکردم؛ ادعای «applied to prod» را نمی‌توانم تأیید کنم.
4. ❌ صحت نجومی خروجی گذر را نسنجیدم.

**دربارهٔ اینکه چرا هرمس گفت «تست نکردم»:** او گفت **تست end-to-end مرورگر** نزده
(فقط curl + pytest) — یعنی مرورگر واقعی باز نکرده تا ظاهر صفحه را ببیند. این صادقانه و
درست بود، و همان کاری است که من در این دور انجام دادم (بخش P1-2).

---

## FINDINGS

### 🔴 P0-1 — `pgvector` در `requirements.txt` نیست ⇒ نصب تازه اصلاً import نمی‌شود

**اثبات با اجرا:**
```
$ pip install -r requirements.txt      # موفق
$ pytest tests/ -q
ImportError while loading conftest 'tests/conftest.py'
app/models.py:12: from pgvector.sqlalchemy import Vector
E   ModuleNotFoundError: No module named 'pgvector'
```
- `app/models.py:12` — `from pgvector.sqlalchemy import Vector`
- `grep -in pgvector requirements.txt` ⇒ **NOT IN requirements.txt**

⇒ روی هر محیط تازه (کلون جدید، Docker، GitHub Actions) اپ **قابل import نیست**.
بعد از نصب دستی `pgvector`، سوئیت اجرا شد. یعنی «سبز بودن» فقط روی ماشینی ممکن است که
این پکیج از قبل و خارج از manifest در venv‌اش نصب شده باشد.

---

### 🔴 P0-2 — GitHub Actions متغیر `ADMIN_PIN` را ندارد ⇒ ۷۳ ماژول تست در collection می‌شکنند

**اثبات با اجرا:** بدون `ADMIN_PIN`:
```
73 errors in 20.28s
ERROR tests/test_z1_account_delete_paying_user.py - RuntimeError: ADMIN_PIN is required (audit P0: ...)
ERROR tests/test_round21_y_fixes.py       - RuntimeError: ADMIN_PIN is required
... (۷۱ مورد دیگر)
```
- `.github/workflows/ci.yml:27-30` فقط `DATABASE_URL`, `PUBLIC_BASE_URL`, `REDIS_URL` را ست می‌کند.
- `tests/conftest.py` هم `ADMIN_PIN` را ست نمی‌کند.
- روی سرور توسعه، `app/config.py` فایل `.env` را می‌خواند ⇒ محلی کار می‌کند، در CI نه.

**نتیجهٔ ترکیبی P0-1 + P0-2:** گیت CI روی GitHub **دو دلیل مستقل برای قرمز بودن** دارد.
هر ادعای «CI سبز» تا امروز از اجرای محلی روی سروری با `.env` کامل آمده، نه از گیت مخزن.
لاگ کامیت‌شده (`docs/qa/CI-ROUND21-2026-08-23.log`) هم همان اجرای محلی است.

---

### 🔴 P0-3 — `/about` و `/faq` و `/guide` روی هر میزبانی جز `/root/chart-platform` خطای ۵۰۰ می‌دهند

**اثبات با اپِ در حال اجرا** (نمونهٔ QA روی `127.0.0.1:8798`):
```
/              200      /articles      200      /gift-guide   200
/birth-form    200      /learn         200      /sky          200
/plans         200      /moon          200      /credits      303
/about         500  ❌   /faq          500  ❌   /guide       500  ❌
```
**ریشه:** `app/main.py:2854` و `app/main.py:2913`
```python
p = _P("/root/chart-platform/app/content/pages.json")     # 2854
p = _P("/root/chart-platform/app/content/articles.json")  # 2913
```
فایل‌ها **در مخزن هستند** (`app/content/pages.json`) ولی با **مسیر مطلق میزبان** خوانده می‌شوند.
جای دیگری `p.exists()` False می‌شود ⇒ `base = {}` ⇒ `_load_pages()["about"]` ⇒
`KeyError` در `app/routes/seo.py:192` ⇒ **۵۰۰**.

این **دقیقاً همان کلاس باگ R9** است (مسیر مطلق PDF راهنما) که در دور ۲ فقط در همان یک نقطه
فیکس شد. جارو نشد. الان هنوز **۷ مسیر مطلق** در کد محصول باقی است:
`main.py:2854` · `main.py:2913` · `config.py:3` · `cities_ir.py:34` ·
`sky.py:18` · `engine.py:22` · `admin.py:339`
(دوتای آخر fallback با `os.getenv` دارند؛ دوتای اول **هیچ fallbackی ندارند** و ۵۰۰ می‌دهند.)

> ⚠️ Dockerfile مخزن `WORKDIR /app` دارد ⇒ در Docker این سه صفحه از روز اول ۵۰۰‌اند.

---

### 🔴 P0-4 — فیکس `Z2` دو تست موجود را شکست (پاسخ مستقیم به سؤال «آیا Z فیش جدید باز کرد؟»)

**بله.** بازتولید شد:
```
FAILED tests/test_transit_forecast_b1.py::test_10_cache_skips_recompute
FAILED tests/test_transit_forecast_b1.py::test_11_cache_invalidates_after_ttl

psycopg2.errors.ForeignKeyViolation: insert or update on table "transit_forecasts"
violates foreign key constraint "transit_forecasts_chart_id_fkey"
DETAIL:  Key (chart_id)=(b1-cache-84f31bac) is not present in table "charts".
```
این دو تست ردیف `TransitForecast` را با `chart_id` ساختگی می‌سازند. تا پیش از `Z2`
(که FK را با `ondelete=CASCADE` برگرداند) این کار مجاز بود.

**این خودِ فیکس را زیر سؤال نمی‌برد** — `Z2` درست است و FK باید باشد؛ ایراد این است که
تست‌های وابسته به‌روز نشدند. **و مهم‌تر:** ادعای «۷۰۳ passed» نمی‌توانسته شامل این دو باشد.

---

### 🟠 P1-1 — E2E پرچم‌دارِ مسیر پول **به LLM پولی واقعی وصل است** و بدون کلید می‌شکند

**اثبات با اجرا:**
```
FAILED tests/test_round2_e2e_credit_economy.py::test_x11_buy_then_use_everything
AssertionError: narratives empty!
  ... 'narratives': [], 'metrics': {'calls': 24, 'retries': 24, 'total_tokens': 0, ...}
WARNING chart.llm: LLM provider omni failed: OMNI_API_KEY not set — trying next   (×24)
```
**ریشه — mock به هدف نمی‌خورد:**
- تست پچ می‌کند: `monkeypatch.setattr(tn, "build_router", ...)` (`tests/test_round2_e2e_credit_economy.py:63`)
  یعنی `app.report.transit_narrative.build_router`
- ولی اندپوینت **خودش روتر را می‌سازد**: `app/main.py:2491` → `from app.core.llm import build_router`
  و `app/main.py:2504` → `narrate_transit(..., router=build_router("transit"), ...)`
⇒ چون روتر از بیرون **پاس داده می‌شود**، `narrate_transit` هرگز به attribute پچ‌شده نگاه نمی‌کند.

**پیامد:** روی ماشینی که `.env` با کلید واقعی دارد، این تست با **۲۴ فراخوانی API پولی** پاس می‌شود.
این مستقیماً قانون خود پروژه را نقض می‌کند (`CLAUDE.md`: «هرگز اندپوینت LLM پولی را در
تست/اعتبارسنجی صدا نزن»). و توضیح می‌دهد چرا «۷۰۳ سبز» محلی به‌دست آمده.

---

### 🟠 P1-2 — صفحهٔ گذرها: **استایل درست شد ✅ ولی UX فروش شکسته است**

این همان چیزی است که هرمس خواست در مرورگر ببینم. با Chromium واقعی دیدم.

**✅ آنچه واقعاً درست شد (`Z9`):**
| سنجه | مقدار اندازه‌گیری‌شده |
|---|---|
| کلاس‌های مردهٔ Tailwind | **صفر** (grep روی HTML رندرشده) |
| `.card` استایل واقعی | `padding: 24px · border-radius: 20px · background: rgb(36,31,51)` ✅ |
| اسکرول افقی ۳۹۰px / ۱۲۸۰px | **False / False** ✅ |
| خطای کنسول | ۲ مورد، هر دو محیطی (۴۰۱ روی `/api/credits/me` برای مهمان + بلاک‌شدن `analytics.negar.io` توسط پراکسی) |

**🟠 ولی در اسکرین‌شات (`docs/reviews/evidence/r4-transits-mobile-390.png`) این‌ها دیده می‌شود:**

1. **~۳۲ کارت یکسان در یک لیست تخت** — ارتفاع صفحه در موبایل **۵۲۸۷ پیکسل**.
2. **دکمهٔ اصلی خرید («تحلیل تأملی گذرها — ۵ اعتبار») در انتهای همین دیوار است** —
   کاربر باید از ~۳۲ کارت رد شود تا آن را ببیند. این نقض مستقیم قاعدهٔ D3-۴ پلن اصلی است
   («CTA اصلی باید در دسترس شست باشد»).
3. **انتخابگر ۳/۱۲ ماه هم پایین است** — کاربر بدون اسکرول کامل نمی‌تواند بازه را عوض کند.
4. **`weight` محاسبه می‌شود ولی استفاده نمی‌شود.** موتور برای هر رویداد وزن می‌سازد
   (`transit_forecast.py`: `WEIGHT_PLANET × WEIGHT_TARGET × WEIGHT_ASPECT`)، اما مرتب‌سازی
   بر اساس `window_start` است ⇒ «زحل در تربیع با خورشید تولد» بین ده‌ها جنبهٔ جزئی مریخ گم می‌شود.
5. **هیچ‌کدام از مشخصات B3 پیاده نشده:** تایم‌لاین با جداکنندهٔ ماه ❌ · نوار شدت ❌ ·
   **رویداد اول رایگان به‌عنوان طعمهٔ تحلیل** ❌ · دکمهٔ «افزودن به تقویم (.ics)» ❌
6. **صفحه چیزی نمی‌فروشد:** همهٔ ۳۲ رویداد رایگان نشان داده می‌شوند و **هیچ نمونه‌ای از
   تحلیل پولی** دیده نمی‌شود. کاربر نمی‌داند بابت ۵ اعتبار چه می‌گیرد.

> خلاصه: `Z9` وظیفه‌اش (استایل) را کامل انجام داد. مشکل باقی‌مانده **طراحی محصول** است، نه CSS.

---

### 🟡 P2 — موارد کوچک‌تر (همه با اجرا تأیید شد)

| # | یافته | مدرک |
|---|---|---|
| P2-1 | `Subscriber` (شماره/ایمیل کاربر) در حذف حساب پاک نمی‌شود. `Z1` هفت جدول را پوشش داد ولی این یکی جا ماند — دادهٔ شخصی بعد از حذف حساب باقی می‌ماند | `main.py` بلوک `account_delete` |
| P2-2 | ۱۲ فایل تست هنوز `/root/chart-platform` را هاردکد می‌کنند. `Y10` فقط `DATABASE_URL`/`SWISSEPH_EPHE_PATH` را درست کرد. نتیجه: ۲ شکست واقعی: `FileNotFoundError: /root/chart-platform/app/content/articles.json` | `tests/test_content_sweep_v4.py:14` |
| P2-3 | `test_extra_api_flows` (۵۰۳) و `test_admin_extra_flows` (۵۰۲ «R2 upload failed») بدون کلید R2/VAPID می‌شکنند — تست‌های وابسته به سرویس بیرونی بدون `skipif` | `tests/test_e2e_full_flows.py:243,286` |
| P2-4 | `Z14` (تست مسیر صوت بدون monkeypatch) انجام نشد — **خود هرمس صادقانه اعلام کرد** ✅ | — |

---

## آنچه واقعاً درست شد (تأییدشده — بیشترش با اجرا)

| مورد | تأیید |
|---|---|
| **`Z1`** آبشار حذف حساب | کد ۷ جدول را پاک می‌کند (`CreditTransaction`, `Entitlement`, `Exploration`, `PushSubscription`, `ConsentLog`, `NotificationPrefs`, `TransitAlertLog`) + توضیح صریح دربارهٔ `FunnelEvent` (ناشناس، بدون FK). **اجرا شد: `tests/test_z1_account_delete_paying_user.py` سبز** ✅ |
| **`Z2`** بازگرداندن FK | **این بار جهت درست:** مدل اصلاح شد (`ondelete="CASCADE"`) نه دیتابیس. دقیقاً همان چیزی که قانون «drift را با تخریب حل نکن» می‌خواست ✅ |
| **`Z3`** مهاجرت `subscribers` | `d9e3f4a5b6c7` idempotent ✅ |
| **`Z5`** مسیر ارتقا | `has(..., unbound_only=True)` در `entitlements.py:33,61` + استفاده در `main.py:661` ✅ |
| **`Z6`** پارامتر `months` | ✅ |
| **`Z9`** استایل واقعی | **بصری تأیید شد** — صفر کلاس مرده، `.card` واقعاً استایل دارد ✅ |
| **`Z10`** چک کلاس تعریف‌نشده | `scripts/ui_audit.py:325,344,372,396` — لینت واقعی اضافه شد ✅ |
| **`Z11`/`Z12`/`Z13`/`Z15`/`Z16`** | مهاجرت backfill، گارد inspector، `refund()→None`، retention، لاگ CI ✅ |
| **کیفیت تست‌ها** | `tests/test_round21_y_fixes.py` + `test_z1_...` ⇒ **۱۰ تست، همه سبز در اجرای من** ✅ |

**نکتهٔ مثبت مهم:** `Z2` نشان داد بازخورد قاعده‌ای (نه فقط باگ‌محور) جواب می‌دهد — دور قبل
FK حذف شد تا `alembic check` سبز شود؛ این دور مدل اصلاح شد. **این دقیقاً تغییر رفتار درست است.**

---

## REQUIRED_FIXES

### گروه ۱ — سبز کردن واقعی CI (بدون این، هیچ ادعای دیگری قابل اتکا نیست)
| ID | فیکس | یافته |
|---|---|---|
| `W1` | `pgvector` را به `requirements.txt` اضافه کن (نسخهٔ pin‌شده) | P0-1 |
| `W2` | `ADMIN_PIN`, `ADMIN_PHONE`, `SWISSEPH_EPHE_PATH`, `AUTH_SECRET`, `ADMIN_SECRET`, `SECRETS_MASTER_KEY` را به بلوک `env:` در `.github/workflows/ci.yml` اضافه کن (یا در `conftest.py` با `setdefault`) | P0-2 |
| `W3` | تست‌های `test_transit_forecast_b1.py::test_10/test_11` را به‌روز کن تا چارت واقعی بسازند (FK درست است — تست باید عوض شود، نه FK) | P0-4 |
| `W4` | mock را درست کن: در `main.py` روتر را از داخل `narrate_transit` بگیر (پارامتر `router` را حذف کن یا `build_router` را در `app.main` قابل‌پچ کن)، و در تست همان را پچ کن. **تست باید بدون هیچ کلید LLM سبز شود** | P1-1 |
| `W5` | بعد از W1-W4، یک اجرای واقعی روی **GitHub Actions** بگیر و لینک run را در گزارش بیاور — نه لاگ محلی | P0-1/2 |

### گروه ۲ — مسیرهای مطلق (جارو کردن کامل، نه نقطه‌ای)
| ID | فیکس | یافته |
|---|---|---|
| `W6` | `main.py:2854` و `main.py:2913` را به `BASE_DIR / "content" / ...` تبدیل کن | P0-3 |
| `W7` | هر ۷ مورد `/root/chart-platform` در `app/` را جارو کن + یک تست/گیت CI که وجود این رشته در `app/` را ممنوع کند | P0-3 |
| `W8` | ۱۲ فایل تست را هم از مسیر مطلق پاک کن (`Path(__file__).resolve().parents[1]`) | P2-2 |

### گروه ۳ — محصول و حریم خصوصی
| ID | فیکس | یافته |
|---|---|---|
| `W9` | **بازطراحی صفحهٔ گذرها:** CTA و انتخابگر ماه را **بالای** لیست ببر (و روی موبایل sticky کن)؛ مرتب‌سازی پیش‌فرض بر اساس `weight` نزولی (یا گروه‌بندی «مهم‌ترین‌ها» + «بقیه»)؛ جداکنندهٔ ماه؛ نوار شدت؛ **رویداد اول با تحلیل رایگان به‌عنوان نمونه** | P1-2 |
| `W10` | حذف `Subscriber` (بر اساس contact کاربر) در `account_delete` | P2-1 |
| `W11` | `skipif` برای تست‌های وابسته به R2/VAPID | P2-3 |
| `W12` | `Z14`: تست مسیر صوت بدون monkeypatch گیت | P2-4 |

---

## ACCEPTANCE_CRITERIA

### AC-1 (W1/W2/W5) — CI واقعاً سبز روی GitHub
```
کلون تازه → pip install -r requirements.txt → python -c "import app.main"   → موفق
اجرای workflow روی GitHub Actions → سبز
مدرک: لینک run در GitHub، نه لاگ محلی
```

### AC-2 (W3/W4) — سوئیت بدون هیچ کلید بیرونی سبز
```
محیط کاملاً بدون کلید (بدون OMNI_API_KEY، بدون R2، بدون VAPID):
pytest tests/ -q  → 0 failed
مخصوصاً: test_x11_buy_then_use_everything سبز با narratives غیرخالی و metrics.calls از mock
```

### AC-3 (W6/W7) — صفحات ثابت روی هر میزبانی
```
اپ را از یک مسیر دلخواه (مثلاً /srv/app) اجرا کن:
GET /about → 200 · GET /faq → 200 · GET /guide → 200
گیت: grep -rn "/root/chart-platform" app/ --include=*.py  → صفر خط
```

### AC-4 (W9) — صفحهٔ گذرها می‌فروشد
```
اسکرین‌شات ۳۹۰px: CTA خرید در ۱۰۰۰ پیکسل اول صفحه دیده شود
رویداد اول تحلیل نمونه دارد (بدون خرید)
رویدادها بر اساس weight نزولی مرتب‌اند (تست واحد روی ترتیب)
ارتفاع صفحه در موبایل < ۳۰۰۰px (یا صفحه‌بندی/جمع‌شونده)
قبل/بعد در گزارش
```

### AC-5 (W10) — حذف کامل حساب
```
کاربر → /api/subscribe با ایمیلش → /account/delete
assert: هیچ ردیف subscribers با آن contact باقی نماند
```

---

## قانون دور بعد

**قانون «مدرک باید بازتولیدپذیر باشد».** سه دور است که «CI سبز» گزارش می‌شود و این دور با
اجرای مستقل معلوم شد که گیت مخزن **به دو دلیل ساختاری نمی‌تواند سبز باشد**
(`pgvector` در manifest نیست، `ADMIN_PIN` در workflow نیست).
از این پس مدرکِ سبز بودن = **لینک اجرای GitHub Actions**، نه لاگ محلی.
اجرای محلی روی سروری که `.env` کامل و پکیج‌های خارج از manifest دارد، «سبز بودن پروژه» را
اثبات نمی‌کند — فقط «سبز بودن آن ماشین» را.

---

*بازبینی توسط Opus 5 — این بار با اجرای واقعی: Postgres+pgvector+Redis، ۶۹۳/۷۰۴ تست، اپِ زنده، و مرورگر Chromium. محدودیت‌ها در TRUTH-NOTES.*
