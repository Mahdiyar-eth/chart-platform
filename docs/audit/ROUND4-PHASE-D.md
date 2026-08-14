# ROUND 4 — PHASE D Report (D1–D4)

**Date:** 2026-08-14 · **Branch:** main · **Version:** v4.0 (post-phase-D)

## D1 — Web Push (اعلان مرورگر) ✅

| فایل | تغییر |
|---|---|
| `app/models.py` | جدول `push_subscriptions` (endpoint/p256dh/auth، user_id اختیاری) |
| `app/push.py` | VAPID از env (unescape + تبدیل PEM→raw base64url)، `send_to_user`، `_send_one` |
| `app/main.py` | `GET /api/push/vapid-public-key` (503 اگر پیکربندی نشده)، `POST /api/push/subscribe`، `POST /api/push/unsubscribe` |
| `app/static/sw.js` | هندلرهای `push` + `notificationclick` (فارسی RTL، باز کردن URL) |
| `app/templates/account.html` | دکمهٔ فعال‌سازی اعلان + پیام محدودیت iOS Safari |
| `app/report/weekly.py` | بعد از تلگرام → push به مرورگر صاحب چارت |

**واقعیت فنی:** dotenv با PEM چندخطی می‌شکست («could not parse statement starting at line 35») → کلیدها یک‌خطی با `\n`-escape ذخیره شدند؛ pywebpush (`Vapid02.from_string`) PEM/PKCS8 نمی‌پذیرد → تبدیل PEM→raw base64url هنگام load (pub ۶۵ بایت / priv ۳۲ بایت). اعتبار کلیدها با پرووف end-to-end اثبات شد: امضا و رمزنگاری VAPID پاس، فقط مرحلهٔ شبکه روی endpoint ساختگی fail شد.

**تست:** ۴ تست (`tests/test_web_push.py`) · شمارش کل: 213

## D2 — pgvector RAG (چت با بازیابی معنایی) ✅

| فایل | تغییر |
|---|---|
| `app/models.py` | جدول `report_chunks` (text + `Vector(384)`) + ایندکس HNSW در `__table_args__` |
| `app/rag.py` | chunk/index/search + `_model_instance` لِیزی (env `RAG_MODEL`) |
| `app/report/worker.py` | هنگام done گزارش → chunk + index |
| `app/chat/service.py` | `chat_answer(..., report_id=...)` → `search_relevant` در prompt (best-effort) |

**واقعیت فنی:** `pgvector` 0.6.0 نصب و extension روی prod/test فعال. **e5-large = 1.2GB RSS در هر worker → OOM با ۲ worker وب** → پیش‌فرض **multilingual-e5-small (384-dim، ~118MB)**؛ override با `RAG_MODEL`. اسموک واقعی: index اولیه 17.8s، search 0.61s؛ سؤال «کار و شغل» → chunk شغلی اول رتبه‌بندی شد.

**تست:** ۳ تست (`tests/test_rag_pgvector.py`، مدل mock — بدون دانلود در تست) · شمارش کل: 216

## D3 — کیف پول رفرال ✅

| فایل | تغییر |
|---|---|
| `app/models.py` | `User.balance_rial` + جدول `withdrawal_requests` + `Order.note` |
| `app/payment/orders.py` | `reward_referral()` (۵٪ مبلغ پس از تخفیف، یک‌بار per order، idempotent) + `pay_with_balance()` (فقط کل مبلغ، بدون ترکیب با درگاه) |
| `app/main.py` | reward در لحظهٔ verify پرداخت (گارد: **رفرال هرگز پرداخت را نشکند** — try/except + rollback + re-fetch)؛ endpointهای کیف پول/تسویه؛ صف تسویه در ادمین |
| `app/templates/account.html` | بخش کیف پول (موجودی + کد دعوت) |
| `app/templates/plans.html` | دکمهٔ «پرداخت با موجودی» (اگر موجودی ≥ قیمت) |

**تست:** ۴ تست (`tests/test_wallet_referral.py`) · شمارش کل: 220

## D4 — SSE Streaming چت ✅

| فایل | تغییر |
|---|---|
| `app/core/llm.py` | `LLMProvider.stream()` + پیاده‌سازی `stream=True` در DeepSeekProvider (ارث به GoProvider) + `router.stream_complete()` با زنجیرهٔ fallback و circuit breaker یکسان |
| `app/chat/service.py` | `chat_stream()` — async generator رویدادها (intent → token* → done/error) |
| `app/main.py` | `POST /api/chat/stream` — `text/event-stream`؛ گاردهای مشترک استخراج‌شده در `_chat_guarded_context` (rate-limit، مالکیت، پلن، انقضای اشتراک، سهمیه اتمیک)؛ **سهمیه فقط پس از اولین توکن مصرف می‌شود** (در غیر این صورت refund) |
| `app/templates/chat.html` | مصرف‌کنندهٔ SSE با `ReadableStream` + cursor تایپ متحرک؛ ایموجی‌های ⏳🔒 → sprite (`icon-lock`) |

**واقعیت فنی:** استریم واقعی توکن‌ها از API سازگار با OpenAI (بدون شبیه‌سازی)؛ history در پایان استریم ذخیره می‌شود؛ خطاهای mid-stream با رویداد `error` به کلاینت می‌رسد و هرگز کلاینت را معلق نمی‌گذارد.

**تست:** ۳ تست (`tests/test_chat_stream_sse.py`) · شمارش کل: **223 passed, 1 skipped** · CI OK

## جمع‌بندی فاز D

- **شمارش تست:** 209 (C8) → 213 (D1) → 216 (D2) → 220 (D3) → **223 (D4)**؛ ۱ skipped (chart-2-no-time by design)
- **CI:** ✅ (ruff F/E9، bandit، pip-audit، secret scan، brand scan، alembic chain، coverage، prod boot smokes A11/B4/B5)
- **Production:** `sudo systemctl restart chart-web` → readiness **200**؛ روت‌های جدید (push، stream) روی prod فعال
- **Migrations:** prod و test روی head (D1 `64397ea3dbf5`، D2 `be499a77ca2b`، D3 ۲ رِویژن)
- **کامیت‌ها:** `feat(d1)`، `fix(d1) VAPID`، `feat(d2)`، `feat(d3)`، `feat(d4)` — همه push شده

## Pending (خارج از دور ۴)

- فیکس VAPID در `.env` — انجام شد ✅ (یک‌خطی escaped)
- انتقال /srv → موکول به بعد از لانچ
- تأیید نهایی کاربر روی موبایل واقعی
