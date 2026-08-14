# زایچه (ZAYCHE) — پلن جامع دور چهارم (Round 4) — Production-Readiness

> **تاریخ:** ۱۴ اوت ۲۰۲۶ · **نویسنده:** Hermes Agent
> **مبنای این پلن:** سه تحلیل بیرونی (FULL-PROJECT-AUDIT، پاس دوم باندل، ممیزی جامع فارسی) + راستی‌آزمایی «ادعا به ادعا» با کد واقعی + سرچ/تحقیق عمیق (Redis atomic quota، reservation pattern، age encryption، presigned short-lived، pgvector، Web Push، payment state machine).
> **وضعیت فعلی:** ۱۵۱ تست پاس، ۴ مهاجرت Alembic، CI ۶ گیت، سرویس‌ها live با User=zayche.
> **این سند مستقل است و برای مشورت با AI دیگر (Claude) قابل ارسال است.**

---

## ۰) خلاصهٔ اجرایی

پلتفرم از نظر معماری و کیفیت مهندسی در سطح بالاست (امتیاز تولید: ~۷/۱۰). سه تحلیل بیرونی مجموعاً **۱۰ یافتهٔ P0 واقعی** (تأییدشده با کد)، ۸+ مورد P1 و ۴ مورد P3 دادند. این پلن در ۴ فاز آنها را می‌بندد:

- **فاز A (بلاکرهای لانچ):** امنیت/مالی/سکرت — ۱۱ آیتم
- **فاز B (زیرساخت):** DLQ، بکاپ رمزنگاری، presigned، rate limit، refund — ۱۰ آیتم
- **فاز C (کیفیت):** R2 صوت، پاکسازی کد مرده، warnings، health، حریم خصوصی — ۸ آیتم
- **فاز D (قابلیت):** Web Push، pgvector، کیف پول، SSE — ۴ آیتم

**اصول اجرا (از قبل تعیین‌شده):** TDD (تست اول)، هر فیکس = یک تست regression، کامیت پس از هر آیتم، راستی‌آزمایی زندهٔ هر ادعا، گزارش پس از هر فاز.

---

## ۱) یافته‌های تأییدشده (منبع: ۳ تحلیل + راستی‌آزمایی)

| کد | یافته | حکم راستی‌آزمایی | شاهد |
|---|---|---|---|
| P0-1 | رمز Umami (ارزش واقعی — حذفشده از این سند) کامیت‌شده در `deploy/umami-admin.txt` + `umami.env` | 🔴 درست و واقعی | grep مستقیم |
| P0-2 | `APP_ENV` کد `"prod"` چک می‌کند ولی `.env.example` مینویسد `production` → fail-closed ساکت غیرفعال | ✅ درست | auth.py:32، db.py:10، .env.example:7 |
| P0-3 | Transit IDOR: `/api/charts/{id}/transits` + `/transit/{id}` بدون `_owns_chart` | ✅ درست | main.py:1182، 1191 |
| P0-4 | Synastry: `/api/synastry/full` فقط paid-order چک می‌کند، مالکیت دو چارت نه | ✅ درست | main.py:916 |
| P0-5 | Orders: `POST /api/orders` بدون مالکیت | ✅ درست | main.py:541 |
| P0-6 | Bot: چارت‌های ساخته‌شده توسط بات مدل مالکیت وب را ندارند | ✅ درست | bots/handler.py |
| P0-7 | Report غیر-idempotent: هر POST → ردیف جدید + جاب LLM جدید | ✅ درست | main.py:364 |
| P0-8 | Chat quota race: count→compare→LLM (بدون اتمیک) + سهمیه per-chart | ✅ درست | main.py:1147 |
| P0-9 | اشتراک ماهانه بدون انقضا: فقط `Order.status=="paid"` | ✅ درست | main.py:1143 |
| P0-10 | تمدید اشتراک `now+30` → باقیمانده دور ریخته می‌شود | ✅ درست | orders.py:132 |
| P1-1 | DLQ موجود (`retry_failed_reports.py`, MAX_RETRIES=5) ولی **کرون نشده** — فقط دستی | ✅ درست | crontab |
| P1-2 | بکاپ شامل `.env` کامل (انفجار ریسک) — بدون رمزنگاری | ✅ درست | backup_db.py |
| P1-3 | Presigned ۷ روزه (604800s) | ✅ درست | storage.py:57 |
| P1-4 | fallback باکت `hermes-voice-clone` در backup_db.py (پروژه رفته روی zayche-storage) | ✅ درست | backup_db.py:110 |
| P1-5 | کد مردهٔ `send_transit_digests.py` (docstring آن کرونِ همان ساعت را آموزش می‌دهد → مین دوبل-سن) | ✅ درست | docstring |
| P2-1 | صوت TTS در `/tmp` (با پاکسازی ۲۴h) | ✅ درست | main.py:975 |
| P2-2 | Rate limit fallback در-حافظه در چند-ورکر → سقف چند برابر | ✅ درست (مستند) | security.py |
| P3-1..3 | Web Push، pgvector، کیف پول رفرال — غایب | ✅ درست | کد |

---

## ۲) تحقیق و مقایسهٔ گزینه‌ها (نتیجهٔ سرچ عمیق)

### سهمیهٔ روزانهٔ چت (P0-8) — الگوی اتمیک
| گزینه | مزیت | عیب |
|---|---|---|
| **Redis INCR + EXPIRE** (fixed window) | اتمیک، ساده، sub-ms، پاکسازی خودکار | نیاز به Redis (fallback در-حافظه فقط برای تست) |
| ZSET sliding window | دقیق‌تر | پیچیده‌تر، SCM زائد |
| Lua token bucket | نرخ‌مند | بیش‌مهندسی برای سهمیهٔ روزانه |

**انتخاب:** INCR + EXPIRE با کلید `chat_q:<date>:<account_id>`؛ در prod Redis **اجباری** (بدون fallback در-حافظه برای این مسیر). سقف: ۵ طلایی / ۱۵ ماهانه در روز. TTL = تا نیمه‌شب UTC.
**تصمیم محصول (نیاز به تأیید تو):** سهمیه per-account (توصیه — مطابق متن پلن «۵ سوال در روز») یا per-chart.

### کوپن/پرداخت (P0-10) — Reservation Pattern
مشکل: پرداخت موفق بیرونی + مصرف کوپن ناموفق → پول گرفته شده ولی سفارش failed.
| گزینه | توضیح |
|---|---|
| **Reservation** (انتخاب) | هنگام ساخت سفارش: `reserved` با `expires_at = now+15min`؛ هنگام پرداخت: `consumed`؛ هنگام لغو/انقضا: `released`. رزرو اتمیک با `used_count < max_uses` |
| Consume-at-payment (فعلی) | مسابقهٔ باقی‌مانده |

**پیاده‌سازی:** فیلد `status` روی CouponUsage (جدول جدید) یا فیلدهای `reserved_count`/`used_count` روی Coupon + کرون رهایی رزروهای منقضی.

### رمزنگاری بکاپ (P1-2) — age vs GPG
| گزینه | مزیت | عیب |
|---|---|---|
| **age** (انتخاب) | مدرن، ساده، کلید کوچک، **قبلاً در سرور نصب/استفاده شده** (voice-clone .env.age) | کمتر شناخته‌شده |
| GPG | شناخته‌شده | پیچیده، کلیدهای بزرگتر |

**پیاده‌سازی:** dump جدا از `.env`؛ هر دو با age رمزنگاری شوند؛ کلید age در `/root/.hermes/keys/` + کپی در بکاپ آفلاین. بکاپ DB شامل `.env` **نمیشود** (فایل سکرت جدا: `secrets.age`).

### Presigned کوتاه (P1-3)
الگوی استاندارد: **۱۵–۶۰ دقیقه + refresh از endpoint احرازشده**. PDF در R2 خصوصی می‌ماند؛ `GET /api/reports/{id}/pdf` پس از `_report_gate` یک URL تازه (۳۰ دقیقه) می‌سازد و 302 می‌دهد. (تحلیل ۱: ۷ روز غیرضروری است — تأیید.)

### RAG برداری (P3-2) — انتخاب embedding چندزبانه
| گزینه | کیفیت فارسی | هزینه/اندازه |
|---|---|---|
| multilingual-e5-large | خوب (آموزش چندزبانه) | ۵۶۰MB، رایگان، روی سرور CPU ممکن |
| paraphrase-multilingual-MiniLM | متوسط | ۴۷۰MB سبک |
| OpenAI text-embedding-3-large | عالی | پولی، نیاز به کلید |

**انتخاب:** شروع با `multilingual-e5-large` (رایگان، روی CPU سرور) — بدون وابستگی خارجی؛ ارتقا به OpenAI در صورت نیاز. افزونه pgvector روی PostgreSQL همان سرور.

### Web Push (P3-1)
الگوی استاندارد: جدول `push_subscriptions` + VAPID keys (تولید محلی) + کتابخانه `pywebpush` سمت سرور + `sw.js` موجود (فقط تابع push handler اضافه می‌شود). ارسال از `weekly.py::run_weekly_delivery()` به‌موازات ربات‌ها.

### Payment State Machine (P1-7)
`pending → verifying → paid | failed` + `refund_requested → refunded` (وضعیت‌های شفاف به‌جای claim زودهنگام). تغییر کوچک: در verify ابتدا `verifying` (با همان UPDATE اتمیک شرطی) سپس پس از تأیید زرین‌پال `paid`. ریسک پایین، وضوح بالا.

---

## ۳) فاز A — بلاکرهای لانچ (۱۱ آیتم)

### A1. چرخش رمز Umami + پاکسازی تاریخچه git — 🔥 فوری
**مشکل:** `deploy/umami-admin.txt` (رمز واقعی ادمین + website_id) و `deploy/umami.env` (۲ سکرت) در git کامیت شده‌اند.
**اقدام:**
1. چرخش رمز ادمین Umami از پنل analytics.negar.io (و تغییر توکن‌های env در فایل‌های واقعی خارج از repo)
2. حذف فایل‌ها از repo + `git filter-repo` (یا BFG) برای پاکسازی تاریخچه — همان رویهٔ انجام‌شده برای voice-clone (filter-repo)
3. اسکن مجدد تاریخچه + push --force با چرخش SSH/توکن GitHub (چون تاریخچهٔ قدیمی ممکن است کپی‌شده باشد)
4. افزودن این دو فایل به `secret-scan` در ci.sh
**تست:** `grep -r "REDACTED_UMAMI_PASSWORD" .git` → خالی؛ CI secret-scan پاس.

### A2. APP_ENV یکپارچه (prod|production)
**فایل‌ها:** `app/config.py` (یا module جدید `app/env.py`) + `auth.py:32,104` + `db.py:10` + هر جای دیگر:
```python
ENV = os.getenv("APP_ENV", "dev").lower()
IS_PROD = ENV in ("prod", "production")
```
**تست:** `tests/test_env_prod.py` — با `APP_ENV=production` بوت اپ: نبود AUTH_SECRET/SECRETS_MASTER_KEY → RuntimeError؛ حالت OTP dev غیرممکن؛ `APP_ENV=prod` هم کار می‌کند (compat).
**معیار:** بوت با هر دو مقدار، رفتار یکسان fail-closed.

### A3. Transit IDOR
**فایل‌ها:** `app/main.py:1182` (`/api/charts/{id}/transits`)، `main.py:1191` (`/transit/{id}`)
**فیکس:** افزودن `_owns_chart(chart, session, request)` → 403/303.
**تست:** `tests/test_transit_authorization.py` — UUID خام → 403/303؛ capability معتبر → 200؛ capability اشتباه → 403.

### A4. Synastry مالکیت
**فایل‌ها:** `main.py:916` (`/api/synastry/full`) + `/api/synastry/order` + endpoint های access
**فیکس:** `_owns_chart(ca) and _owns_chart(cb)` + پرداخت معتبر.
**تست:** `tests/test_synastry_auth.py` — مالک A+B → 200؛ غیرمرتبط → 403؛ paid ولی غیرمالک → 403.

### A5. Order مالکیت
**فایل‌ها:** `main.py:541` (`POST /api/orders`) — قبل از `create_order`: `_owns_chart`؛ برای synastry هر دو.
**نکته:** ربات‌ها از همین endpoint استفاده می‌کنند → A6 همزمان.
**تست:** `tests/test_order_auth.py` — چارت خارجی → 403؛ چارت خودی → 200.

### A6. Bot chart capability token
**مشکل:** چارت‌های ساخته‌شده توسط بات (بدون session کاربر وب) باید لینک `/chart/{id}` قابل‌دسترس داشته باشند.
**گزینه‌ها:** (A) capability token `?t=<32-byte>` هنگام ساخت توسط بات (کمترین تغییر — **انتخاب**)؛ (B) اتصال به کاربر واقعی (تغییر بزرگتر).
**پیاده‌سازی:** هنگام ساخت چارت از بات، `access_token` تولید و در پیام/دکمه‌های URL قرار گیرد؛ `_owns_chart` آن را می‌پذیرد (قبلاً capability را پشتیبانی می‌کند — فقط باید در URL ربات قرار گیرد).
**تست:** فلوی بات → کلیک لینک → 200؛ بدون token → 303.

### A7. Report idempotency
**فایل‌ها:** `main.py:364` (`POST /api/charts/{id}/report`)
**فیکس:**
- اگر report با status در (queued, processing) موجود → همان را برگردان
- اگر done/degraded → همان را برگردان مگر `?regenerate=1` صریح
- ساخت جدید فقط وقتی هیچ‌کدام نباشد
**تست:** `tests/test_report_idempotency.py` — ۴ POST همزمان → ۱ ردیف فعال؛ processing → همان؛ regenerate → جدید.

### A8. Chat quota race + اتمیک
**فایل‌ها:** `security.py` یا `chat/service.py` + `main.py:1147`
**فیکس:** Redis INCR اتمیک (کلید روزانه per-account یا per-chart طبق تصمیم) + سقف؛ در prod بدون fallback (اگر Redis پایین است → 503 موقت، نه عبور از سقف).
**تست:** `tests/test_chat_quota_race.py` — ۱۰ درخواست همزمان با سقف ۵ → حداکثر ۵ LLM call؛ سهمیهٔ روز جدید ریست.

### A9. Subscription expiry
**فایل‌ها:** `main.py:1143` (چک چت) + `app/payment/orders.py`
**فیکس:** تابع `_sub_active(chat_id, chart_id)` — `Subscription.active AND expires_at > now`؛ چت و دسترسی‌های پولی ماهانه فقط با این شرط.
**تست:** `tests/test_subscription_expiry.py` — ماهانه فعال → allowed؛ منقضی → denied؛ بدون ردیف → denied.

### A10. Coupon/payment consistency (reservation)
**فایل‌ها:** `app/models.py` (فیلدهای Coupon یا جدول CouponUsage) + `payment/orders.py` + `main.py` verify
**فیکس:** رزرو اتمیک هنگام ساخت سفارش (`UPDATE coupons SET reserved_count=reserved_count+1 WHERE used_count+reserved_count < max_uses RETURNING id`)؛ consume هنگام پرداخت؛ release هنگام failed/انقضا (کرون).
**تست:** `tests/test_coupon_reservation.py` — رزرو همزمان فراتر از max_uses → رد؛ پرداخت → consume؛ لغو → release.

### A11. Production smoke test در CI
**فایل‌ها:** `.github/workflows/ci.yml` + `scripts/ci.sh`
**فیکس:** مرحلهٔ بوت با `APP_ENV=production` (بدون سکرت → انتظار خطا؛ با سکرت تست → بوت موفق + `/health` 200).
**تست:** خود همین مرحله.

---

## ۴) فاز B — زیرساخت (۱۰ آیتم)

### B1. DLQ خودکار
کرون: `*/15 * * * * retry_failed_reports.py` (اسکریپت موجود، MAX_RETRIES=5) + بخش «گزارش‌های degraded/failed» در پنل ادمین (فیلتر وضعیت). تست: اجرای دستی + تأیید لاگ.

### B2. بکاپ رمزنگاری + جداسازی سکرت
`backup_db.py`: dump → `age -e` با کلید اختصاصی chart (کلید جدید `zayche-backup.age` — جدا از voice-clone)؛ `.env` دیگر داخل zip نمی‌آید؛ فایل جداگانه `secrets-<date>.age`. بازیابی: `age -d` + sanity gate فعلی. **drill بازیابی کامل** در DB آزمایشی.

### B3. Presigned کوتاه (۳۰ دقیقه) + refresh
`storage.py:57` → `expires=1800`؛ endpoint های دانلود PDF/Word/صوت: gate احراز → presigned تازه → 302. تست: URL بعد از ۳۰ دقیقه منقضی (تست با expires مصنوعی).

### B4. R2 fail-closed در prod
`storage.py`: اگر `IS_PROD and (R2_BUCKET/ACCOUNT/KEYS خالی)` → RuntimeError در استارت (نه fallback بی‌صدا). تست: بوت prod بدون R2 → خطا.

### B5. Rate limit چارت + اجباری Redis در prod
`security.py`: `check_rate_limit("chart:<ip>", 10, 60)` روی POST /api/charts. `RATE_LIMIT_BACKEND=redis` در prod اجباری (اگر Redis پایین → 503 برای مسیرهای حساس: OTP/payment/chat/report/chart). تست: ۱۱ چارت در دقیقه → 429.

### B6. Refund lifecycle مرکزی
ماژول `app/payment/refunds.py` — state machine: `refund_requested → refund_confirmed → refunded` + لغو دسترسی گزارش/اشتراک/چت + بازگرداندن کوپن (release) + تعدیل رفرال. پنل ادمین: دکمهٔ ریفاند. تست: فلوی کامل ریفاند طلایی → دسترسی چت قطع.

### B7. Payment state machine شفاف
verify: `pending → verifying → paid|failed` (UPDATE اتمیک شرطی روی pending→verifying، سپس verifying→paid بعد از تأیید زرین‌پال). تست‌های race فعلی به‌روزرسانی.

### B8. Subscription renewal + unique
`orders.py:130`: `base = max(now, sub.expires_at)`؛ `new_expiry = base + 30d`. migration: `UNIQUE(platform, chat_id, chart_id)` + upsert (ON CONFLICT DO UPDATE). تست: تمدید با ۲۰ روز باقی → ۵۰ روز.

### B9. LLM concurrency controls
`core/llm.py` + `report/worker.py`: timeout per-call (فعلی طولانی — بررسی و سقف)، retry backoff، job deadline، `concurrency` محدود ARQ، circuit breaker ساده (۳ خطای متوالی → ۶۰s off). تست: mock تایم‌اوت.

### B10. Decision محصول: سهمیه per-account (در انتظار تأیید) — اگر تأیید شد، مایگریشن کوچک روی منطق شمارش + متن‌های UI.

---

## ۵) فاز C — کیفیت (۸ آیتم)

### C1. صوت TTS → R2
`main.py:975`: تولید موقت → آپلود مستقیم R2 → presigned ۳۰ دقیقه؛ پاکسازی فایل موقت. (هزینه: ~۲KB/ثانیه — ناچیز). تست: آپلود + URL.

### C2. کد مرده + fallback باکت
حذف `scripts/send_transit_digests.py` (جایگزین: weekly.py) + `backup_db.py:110` → `"zayche-storage"`. تست: grep عدم وجود ارجاع.

### C3. پاکسازی warnings تست
Starlette TestClient deprecation → `with TestClient(app)`؛ SQLModel query deprecation → `session.exec(select(...))` معادل جدید. هدف: `151 passed, 0 warnings`.

### C4. ۴ تست skipped — طبقه‌بندی
بررسی هر ۴: environment-dependent/optional/known — مستندسازی در کامنت + یا حذف اگر منسوخ.

### C5. Health تفکیکی
`/liveness` (ساده)، `/readiness` (DB+Redis+worker+R2+disk)، `/health` فعلی → alias. بنر UI فقط روی readiness.

### C6. Lifecycle داده / حریم خصوصی
مستند «حریم خصوصی و نگهداشت داده» + پیاده‌سازی: حذف حساب → حذف cascading چارت/چت/گزارش؛ retention بکاپ (۳۰ روز R2 + پاکسازی خودکار — فایل cleanup در backup_db.py:131 موجود است)؛ بخش «ارسال داده به AI» در privacy policy.

### C7. انتقال از /root → /srv/zayche (بعد از لانچ)
نکته: `ProtectHome=true` نیازمند خروج از /root است. ریسک: downtime کوتاه. برنامه: rsync + systemd path + تست. **این مورد پس از لانچ** (فعلاً مستند در RUNBOOK).

### C8. ماتریس authorization (سند واحد)
جدول Resource × (Public/Capability/AuthOwner/Paid) از تحلیل ۱ (بخش ۳۹) به‌صورت `docs/AUTHORIZATION-MATRIX.md` + تست ساختاری که هر route در ماتریس هست.

---

## ۶) فاز D — قابلیت‌ها (۴ آیتم — پس از لانچ یا با تأیید تو)

### D1. Web Push
جدول `push_subscriptions` + `pywebpush` + VAPID (تولید محلی) + هندلر push در `sw.js` + دکمهٔ اشتراک در حساب کاربری + ارسال در `weekly.py`. (iOS Safari محدودیت دارد — مستند.)

### D2. pgvector RAG چت
`CREATE EXTENSION vector` (migration) + جدول embeddings + index HNSW + chunk گزارش‌ها با `multilingual-e5-large` (روی CPU سرور؛ ~۱ دقیقه برای هر گزارش — job آرک) + جایگزینی تدریجی keyword-retrieval در `chat/retrieval.py`.

### D3. کیف پول رفرال
`referral_events` → فیلد `balance` روی User + خرج در خرید (select در صفحه پلن) + درخواست تسویه (ردیف در ادمین). مرز: تابع پرداخت با موجودی.

### D4. SSE streaming چت
`/api/chat` → `text/event-stream` با `sse-starlette`؛ UI: استریم در جعبهٔ چت. (UX مهم — تحلیل ۳ اشاره کرد.)

---

## ۷) تصمیمات نیازمند تأیید تو (قبل از اجرا)

| # | تصمیم | گزینه‌ها | توصیه |
|---|---|---|---|
| 1 | **سهمیهٔ چت** | per-account / per-chart | **per-account** (مطابق متن پلن «۵ سوال در روز») |
| 2 | حذف `send_transit_digests.py` | حذف / نگهداری | **حذف** (کد مرده + مین دوبل-سن) |
| 3 | Presigned کوتاه | ۳۰ دقیقه / ۱ ساعت | **۳۰ دقیقه** (refresh خودکار) |
| 4 | فاز D (قابلیت‌ها) | قبل از لانچ / بعد از لانچ | **بعد از لانچ** (P0/P1 اول) |
| 5 | انتقال به /srv/zayche | الان / بعد از لانچ | **بعد از لانچ** (downtime کوتاه) |

---

## ۸) ریسک‌ها و Trade-off ها

- **A1 (filter-repo + force push):** تاریخچهٔ GitHub بازنویسی می‌شود → کلون‌های موجود باید دوباره بگیرند؛ هماهنگ با ریپوهای خصوصی (فقط تو و من) — ریسک کم.
- **A8 (Redis اجباری):** اگر Redis down → چت/OTP/پرداخت 503 موقت (fail-closed) به‌جای عبور از سقف — پذیرفته‌شده (امنیت > در دسترس‌بودن برای این مسیرها).
- **B2 (age):** کلید age گم شود = بکاپ غیرقابل بازیابی → کلید در ۲ مکان (سرور + کپی آفلاین).
- **B7 (state machine):** تغییر وضعیت در verify — تست‌های race فعلی (۵ کال‌بک همزمان) باید همچنان سبز بمانند.
- **C7 (/srv):** فقط بعد از لانچ و با بکاپ تازه.

---

## ۹) ترتیب اجرا و برآورد

| فاز | مدت تخمینی | خروجی |
|---|---|---|
| A1–A2 (سکرت/env) | ۱–۲ ساعت | رمزها چرخیده، تاریخچه پاک |
| A3–A6 (authorization) | ۳–۴ ساعت | ۴ ماتریس مالکیت + تست |
| A7–A10 (idempotency/مالی) | ۴–۶ ساعت | ۴ فیکس مالی + تست race |
| A11 + B1–B5 | ۳–۴ ساعت | CI prod-smoke، DLQ، بکاپ age، presigned، rate limit |
| B6–B9 | ۳–۴ ساعت | refund، state machine، renewal، LLM concurrency |
| C1–C8 | ۳–۴ ساعت | کیفیت + privacy + ماتریس |
| D1–D4 (پس از تأیید) | ۸–۱۲ ساعت | قابلیت‌های جدید |

**پس از فاز A:** اجرای کامل `pytest` + `ci.sh` + دیپلوی + **بررسی مجدد توسط AI بیرونی** (دور چهارم).

---

## ۱۰) خارج از این پلن (منتظر تو — پیش‌نیاز لانچ واقعی)

مرچنت واقعی زرین‌پال · کلید Kavenegar · دامنهٔ zayche.io · تست موبایل واقعی (قانون: بدون تأیید تو روی موبایل، «نهایی» اعلام نمی‌شود) · ثبت برند و شبکه‌های اجتماعی.
