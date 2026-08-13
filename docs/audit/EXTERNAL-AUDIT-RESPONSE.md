# پاسخ به ممیزی بیرونی (chart-platform-audit-report.md + بررسی جامع PDF)

**تاریخ:** 2026-08-13 — **منبع:** دو سند ارزیابی مستقل کاربر (توسط AI دیگر)
**امتیاز دادهشده:** Architecture 8.5 / Engine 8 / Backend 8 / Security 5.5 / Production 6.5 — Overall 7.5
**وضعیت پس از این دور:** تمام P0 بسته شد؛ اکثر P1 بسته شد؛ بقیه مستند شد.

قانون: هر ادعا پیش از پاسخ در کد/سرور راستیآزمایی شد (✓ = تأیید، ✗ = رد، ⚠ = جزئی).

---

## P0 — بحرانی (همه بسته شد)

| # | یافته | راستیآزمایی | فیکس |
|---|-------|-------------|------|
| 2.1 | Admin PIN پیشفرض `000000` | ✓ واقعی (پیشفرض در main.py) | پیشفرض حذف شد؛ بدون `ADMIN_PIN` سرور بالا نمیآید + rate limit لاگین (۵/۵دقیقه) |
| 2.2 | OTP Dev Mode پیشفرض true | ✓ واقعی (کد در response برمیگشت) | پیشفرض false؛ در پروداکشن بدون کلید SMS → خطای ۵۰۳ تمیز (نه لوگ کد)؛ کد هرگز در log پروداکشن |
| 2.3 | وبهوکها بدون auth | ✓ واقعی (Bale بدون هیچ محافظی) | Telegram fail-closed (بدون secret → 403)؛ Bale با secret در URL + مقایسه HMAC |
| 2.4 | ساعت تولد نامعلوم → ASC/خانههای ظهر | ✓ واقعی (ظهر محاسبه میشد) | engine: بدون angles/houses/Fortune؛ UI: بدون طالع + نوتیس؛ پرامپت LLM: ممنوعیت حدس طالع/خانه؛ widget خانهها: نوتیس |
| 2.5 | Credential DB در سورس | ✓ واقعی (DEFAULT_URL) | پروداکشن `DATABASE_URL` اجباری (fail-fast)؛ مقدار dev فقط برای محیط غیر-prod |
| 3.1 | Auth با اسکن کل جدول | ✓ واقعی (لوپ روی همه کاربران) | cookie = `user_id.sig` (HMAC) → lookup مستقیم O(1) + امضای قابلراستیآزمایی |
| 3.2 | Ownership ناقص | ✓ جزئی (PDF/DOCX/صدا گیت داشتند) | از قبل: `_report_gate` (paid + مالکیت) روی هر ۳؛ بقیه endpoints با کوکی کاربر scope شدهاند |
| 3.3 | Payment result بدون token | ✓ قبلاً درست بود (Authority تایید میشود) | بدون تغییر لازم |
| 4 | CSRF بدون token واقعی | ✓ جزئی — `security_guard` Origin/Host دارد | برای SPA با cookie-auth نیاز نیست (Origin/Host + SameSite=Lax کافی) — مستند شد |
| 14 | PUBLIC_BASE_URL fallback | ✓ قبلاً اجباری/محیطی است | بدون تغییر لازم (تأیید شد) |

## P1 — بلافاصله بعد (اکثراً بسته شد)

| # | یافته | وضعیت |
|---|-------|--------|
| Element Donut | ✗ قبلاً رد شد (درست بود) — راستیآزمایی مجدد: درست است (Fire/Earth/Air/Water) | ✅ از قبل درست (P1-6 همان روز فیکس شده بود) |
| UNIQUE(platform, chat_id) | ✓ واقعی (نبود) | ✅ constraint + مدل |
| Indexهای مرکب | ✓ واقعی (نبود) | ✅ orders(chart_id,status) + reports(chart_id,created_at) |
| Admin login rate limit | ✓ واقعی (نبود) | ✅ ۵ تلاش/۵ دقیقه |
| Audio در request | ✓ واقعی (TTS همزمان) | ⚠ cleanup /tmp + کش؛ انتقال به worker → P1-PENDING |
| Redis pool مشترک | ✓ واقعی (پول جدید هر درخواست) | ✅ پول مشترک در lifespan + بستن تمیز |
| وضعیت degraded | ⚠ worker فقط done/failed دارد | P1-PENDING (مستند در ACTION-PLAN) |
| timezone واقعی | ⚠ محصول فعلاً ایرانمحور است (cities_ir) | ✅ قابل قبول تا پشتیبانی جهانی (طبق خود سند) |
| noindex صفحات خصوصی | ✓ واقعی (نبود) | ✅ chart/account/admin |
| Alembic migrations | ✓ واقعی (create_all) | P1-PENDING (پیشنهاد: قبل از لانچ عمومی) |

## P2 — Scale (مستند شد در ACTION-PLAN، خارج از این دور)

caching (chart/transit/report)، reconciliation worker، monitoring هزینه LLM، metrics per plan، observability.

## ✅ زیرساخت (از سند «بررسی جامع PDF»)

- **uvicorn --proxy-headers** (نکته واقعی و مهم): بدون آن rate limit ها کلید مشترک 127.0.0.1 داشتند → فیکس شد + لاگ IP واقعی ثابت شد (`91.107.183.171` در لاگ)
- روند پرداخت، RAG چت، golden tests، معماری deterministic engine — همگی تأیید شدند

## ⚠️ وابستگی به کاربر (برای بستن کامل)

1. **کلید Kavenegar** (`OTP_SMS_API_KEY`) — بدون آن ورود با شماره موبایل 503 میگیرد (عمدی، fail-closed)
2. مرچنت واقعی زرینپال (سندباکس فعلی)
3. تست موبایل واقعی (امتیاز نهایی UX)
4. اگر لانچ عمومی نزدیک است: Alembic migrations + انتقال Audio به worker

## تستها

- 66 passed / 3 skipped (بعد از همه فیکسها)
- golden test `chart-2-no-time` **بهروز شد**: رفتار صحیح جدید (بدون خانه/طالع) را assert میکند
- CI: ✅
