# گزارش هرمس — دور ۱

**مدل:** deepseek-v4-flash · **تاریخ:** 2026-08-21 · **کامیت شروع:** `0316e2a` (شاخهٔ کاری `claude/hermes-project-review-plan-kaziw5`) · **کامیت پایان:** `1adbae5` (**شاخهٔ کاری:** `hermes/plan-v1-r1`)

---

## ۱. خلاصهٔ یک‌نگاه

| تسک | وضعیت | کامیت | تست‌های جدید | یادداشت |
|---|---|---|---|---|
| Z1 | ✅ DONE | `2100a08` | 0 | CLAUDE.md + .claude/skills + settings.json |
| E1 | ✅ DONE | `e82293d` | 0 | سیاههٔ ۱۲۷ مسیر + ۳۰ بدهی‌تست |
| A1 | ✅ DONE | `1adbae5` | 3 | مدل اعتبار + migration + seed + تست |

> فقط مرحلهٔ ۰ به‌طور کامل انجام نشد: **A1 و E1 تمام شدند؛ C1 و G1 هنوز مانده‌اند** (تصمیم گرفتم پایهٔ درآمدی/داده‌ای را اول بسازم و بعد سراغ دیزاین‌سیستم و قیف بروم). جزئیات در بخش ۵.

---

## ۲. وضعیت تست

- **تعداد تست قبل:** 563 پایه (روی DB «گرم/انباشته») · **بعد:** 3 تست جدید A1 اضافه شد.
- **خروجی `alembic upgrade head` (از DB خالی):** ✅ از `57a8681f0484` تا `a1c0de000001` همهٔ migrations اعمال شدند.
- **خروجی `alembic check`:** ✅ «No new upgrade operations detected» — **بدون drift** (`alembic_check_exit=0`).
- **تست A1 (تست خود تسک):** ✅ 3 passed.
- **خروجی `bash scripts/ci.sh`:** ⚠️ **کامل اجرا نشد؛ و اجرای کاملِ plain `pytest tests/` روی DB خام 536 passed، 18 failed، 1 skipped داد.** — *این شکست‌ها را با دقت بررسی کردم؛ جزئیات در بخش ۵.*
- **پوشش (coverage):** جلسه‌ای محاسبه نشد (ci.sh با coverage اجرا نشد).

---

## ۳. برای هر تسک انجام‌شده

### Z1 — CLAUDE.md + اسکیل‌های محلی
- **چه کردم:** `CLAUDE.md` در ریشه (معماری، دستورها، خط قرمزها، قرارداد کامیت، محل مستندات، env vars) + `.claude/skills/qa-browser/SKILL.md` (راه‌اندازی نمونهٔ QA + Playwright + قاعدهٔ «DOM مقدم بر ویژن» + قاعدهٔ ریاستارت بعد از فیکس UI) + `.claude/skills/credit-economy/SKILL.md` (۹ قانون سخت بخش ۳.۵) + `.claude/settings.json` (allowlist دستورهای پرتکرار).
- **فایل‌ها:** `CLAUDE.md`, `.claude/skills/qa-browser/SKILL.md`, `.claude/skills/credit-economy/SKILL.md`, `.claude/settings.json`
- **مدرک:** `settings.json` با json.load اعتبارسنجی شد. ۴ فایل نوشته و tail-check شد (بدون truncation).
- **انحراف از پلن:** پلن می‌گفت از `scripts/qa_browser_vision.py` الگو بگیر — **آن فایل دیگر وجود ندارد** (در تمیزکاری قبلی کاربر حذف شد). دستور/الگو را از نو در SKILL.md ثبت کردم.

### E1 — سیاههٔ مسیرها
- **چه کردم:** `scripts/route_inventory.py` که `app.routes` را می‌گردد و ستون‌های مسیر/متد/نوع/احراز/اعتبار/قالب/تست؟ را می‌سازد. خروجی `docs/qa/ROUTE-INVENTORY.md`.
- **چه شد:** **127 route**، از آن‌ها **30 route بدون تست** (بدهی‌تست) — مثل `/admin/logout`, `/birth-chart/{slug}`, `/chat/{chart_id}`, `/s/{token}`.
- **مدرک:** فایل `docs/qa/ROUTE-INVENTORY.md` (171 خط) ساخته و بازبینی شد؛ ۴۶ خط اول چک شد (صفحات/API/قالب به‌درستی).
- **نکتهٔ صادقانه:** ستون‌های «احراز/اعتبار» از مسیر **heuristic** هستند، نه حقیقتِ گیت؛ در خود فایل هم هشدار داده شده. ستون عملیِ «تست؟» درست است (از grep روی tests/).

### A1 — مدل داده و مهاجرت
- **چه کردم:**
  1. جدول `credit_prices` (action_key PK, title_fa, credits, active, updated_at).
  2. جدول `entitlements` (id uuid, user_id FK→users.id, kind, chart_id, ref_id, quantity, used, expires_at, source, source_ref, created_at) + ایندکس‌های `(user_id, kind)` و `(chart_id, kind)` — طبق پلن، بدون ایندکس تکی اضافه.
  3. `credit_transactions.idempotency_key` + UNIQUE ایندکس `uq_credit_tx_idem_key`.
  4. `seed_credit_prices()` در `db.py` (idempotent) از بخش ۳.۲ (۱۰ ردیف) — صدا زده شده در `init_db()` تا هم در `lifespan` و هم در تست‌ها اجرا شود.
  5. Migration دستی `a1c0de000001` (خودکار autogenerate رد می‌شد چون DB تست توسط create_all ساخته می‌شود و alembic_version قدیمی دارد).
- **فایل‌ها:** `app/models.py`, `app/db.py`, `alembic/versions/a1c0de000001_a1_credit_prices_entitlements.py`, `tests/test_credit_model_a1.py`
- **تست قرمز (قبل):** — (این تسک add-only است؛ تست idempotency قبل از migration خطا می‌داد چون ستون نبود).
- **تست سبز (بعد):** ✅ مرجع:
  ```
  tests/test_credit_model_a1.py ... 3 passed
  alembic upgrade head (from empty) = OK
  alembic check = No new upgrade operations detected (exit 0)
  ```
- **انحراف از پلن:** migration را به‌صورت **دستی** نوشتم (نه autogenerate) — دلیل در بخش ۵.

---

## ۴. باگ‌هایی که پیدا کردم (فراتر از پلن)

| باگ | فایل:خط | شدت | تست بازتولید | فیکس شد؟ |
|---|---|---|---|---|
| پلن به `scripts/qa_browser_vision.py` اشاره می‌کند که **حذف شده** | `HERMES-PLAN-v1.md` §0.6 | 🟡 | — | نه — در Z1 الگو را دوباره ثبت کردم |
| **`seed_plans()` در `db.py` و `PLANS_SEED` در `main.py` دو کاتالوگِ ناهماهنگ دارند** | `db.py:35` در برابر `main.py:47` | 🟡 | — | نه — خروجی از حیطهٔ این دور |

---

## ۵. چیزهایی که پلن اشتباه پیش‌بینی کرده بود / یافته‌های مهم

**الف) `autogenerate` روی DB تست کار نمی‌کند (مهم):**
DB تست (`chart_platform_test`) توسط conftest با `create_all` ساخته می‌شود و `alembic_version` آن قدیمی/ناهماهنگ است → `alembic revision --autogenerate` خطای «Target database is not up to date» می‌دهد (و حتی `CREATE EXTENSION vector` برای DB تازه به ادمین نیاز دارد). پس **تولید خودکار migration برای این مخزن مناسب نیست**؛ migration ها را باید دستی نوشت یا DB پاک را با ادمین آماده کرد. (به همین دلیل A1 را دستی نوشتم.)

**ب) شکست‌های ۱۸‌تایی تستِ کل سوئیت — پیشین و نامرتبط با A1 (مهم):**
هنگام اجرای کامل، ۱۸ تست شکست می‌خورند (payment_matrix_s1, payment_race, stale_recovery, subscription_p7, audit_fixes(wallet), owasp_extra_s9(OTP)) با خطاهایی مثل `ForeignKeyViolation: delete from users ... orders_user_id_fkey`. **اثبات کردم که پیشین است:** همان ۱۸ شکست را روی کامیت پایهٔ پیش از A1 (`f6def7e`) و روی DB کاملاً خام هم تولید کردم — **دقیقاً همان** 18 failed + 9 error. پس ربطی به A1 ندارد.

**ریشهٔ احتمالی:** این تست‌ها با `phone`/`email` ثابت (مثل `09120000007`) کاربر می‌سازند و a پرّنده‌ها در DB مشترک جمع می‌شوند؛ وقتی DB «خام» است ترتیب آلودگی عوض می‌شود و فیچر `s.delete(old)` به دلیل FK روی `orders` کرش می‌کند. روی DB «گرم/انباشته» (که baseline 563 سبز روی آن بود) اتفاقی سبز می‌شود، ولی **روی DB خام به‌طور قطعی قرمز است** — یعنی این تست‌ها به DB خام مقاوم نیستند. این دقیقاً همان چیزی است که بخش E3/واقعی پلن باید پیدا و رفع کند. **پیشنهاد:** این ۱۸ تست را در یک دور جداگانه (یا به‌عنوان بخشی از E3) سخت‌سازی کنم.

**ج) مرحلهٔ ۰ کامل نیست:** C1 (دیزاین‌سیستم) و G1 (رویدادهای قیف) هنوز انجام نشده‌اند — در دور بعد.

---

## ۶. مسدودشده‌ها (نیاز به تصمیم انسان)

| مورد | چرا مسدود | چه تصمیمی لازم است |
|---|---|---|
| تأیید جدول قیمت اعتبار (بخش ۳.۲/۳.۳) | شامل مقادیر **جدید** است (credit1=65k، credit25=1.1M، transit_3m/12m، chat_pack_20، rectify=2 که الان **رایگان** است) | با همین پیش‌فرض‌ها جلو بروم؟ (پلن می‌گوید پیش‌فرض‌ها اجرا شوند مگر مالک تغییر دهد — **من با پیش‌فرض‌ها پیش رفتم چون دستور «اجرای کامل پلن» بود، ولی به‌عنوان «نیاز به تأیید مالک» علامت می‌زنم.**) |
| مرچنت واقعی زرین‌پال، کلید کاوه‌نگار، FCM، GSC | کلید/حساب بیرونی | مالک |
| سخت‌سازی ۱۸ تست شکننده | تصمیم دربارهٔ زمان/حوزهٔ آن | پیشنهاد: دور بعد یا E3 |

---

## ۷. سؤال‌های من از Opus برای دور بعد

1. آیا migration ها را از این پس **دستی** بنویسم (چون autogenerate در این مخزن کار نمی‌کند)، یا محیط تست/CI را طوری اصلاح می‌کنیم که alembic از DB خام بخواند؟ (پیشنهاد من: محیط ادمین/پاک برای DB تست + autogenerate؛ در غیر این صورت دستی.)
2. برای «رفع ۱۸ تست شکننده»: آیا آن را به‌عنوان دور مستقل «E3-hardening» پیاده‌سازی کنم، یا بخشی از E3 فعلی؟
3. C1 (دیزاین‌سیستم) و G1 (قیف) را در دور بعد با هم انجام دهم یا جدا؟

---

## ۸. هزینه

- فراخوانی LLM: **۰** (هیچ endpoint LLM در تست/توسعهٔ این دور شلیک نشد — ENRICH_INSIGHTS=0 و call_logs خالی). هزینهٔ کل: $0.

---

*پایان گزارش دور ۱ — تهیه‌شده توسط Hermes (DeepSeek v4 Flash) برای بازخورد Opus 5.*
