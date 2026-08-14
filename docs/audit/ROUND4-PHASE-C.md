# ROUND 4 — PHASE C گزارش (audit r4)

تاریخ: 1405/05/23 (2026-08-14) — برنچ `main`

## خلاصه

فاز C (کیفیت، حریم خصوصی، عملیات) ۸ مورد — همه کامل. **۲ باگ واقعی P0 پیدا و فیکس شد** (حذف حساب برای هر کاربر دارای چارت ۵۰۰ میداد؛ chat_messages هرگز حذف نمیشدند).

| # | مورد | شواهد | وضعیت |
|---|------|--------|--------|
| C1 | صوت TTS → R2 | `audio_key`/`upload_audio` در storage؛ cache-hit اول (بدون هزینه TTS مجدد)؛ miss → تولید → آپلود → presigned ۳۰ دقیقه → پاکسازی `/tmp`؛ ۳ تست `test_report_audio_r2.py` | ✅ |
| C2 | حذف send_transit_digests + fallback باکت | فایل git-rm؛ کرون از قبل weekly_transit را میخواند؛ `R2_BUCKET` fallback → `zayche-storage` (هرگز voice-clone)؛ بدون ارجاع باقیمانده | ✅ |
| C3 | صفر warning تست | ۴۸ → **۰**؛ حذف cookies= منسوخ (۹ فایل، `client.cookies.update`)؛ `s.query→s.exec(select)`؛ pytest.ini فیلتر warning کتابخانهای starlette (مستند)؛ helper `scripts/refactor_cookies.py` | ✅ |
| C4 | طبقهبندی ۴ skip | ۴ → **۱**؛ `verify_utc` به expected چارتهای ۱/۸/سایدریال اضافه شد؛ تنها skip = chart-2-no-time (بیساعت، by-design + docstring) | ✅ |
| C5 | Health تفکیکی | `/liveness` (heartbeat بدون وابستگی) + `/readiness` (DB+Redis+worker+R2+disk، 503 در degraded) + `/health` alias؛ بنر UI → `/readiness`؛ ۴ تست `test_health_split.py` | ✅ |
| C6 | حریم خصوصی | **فیکس ۲ باگ**: chat_messages هیچوقت حذف نمیشد + unitofwork ترتیب FK delete را نمیدهد (flush سطحی) — حذف حساب برای کاربر دارای چارت ۵۰۰ میداد!؛ retention صوت R2 (۳۰ روز) در backup؛ `docs/PRIVACY.md`؛ privacy.html با نام واقعی AI (DeepSeek/OpenCode) + retention؛ ۳ تست `test_data_lifecycle.py` | ✅ |
| C7 | انتقال /srv | موکول به بعد از لانچ (در پلن مستند؛ downtime لازم) | ⏳ موکول |
| C8 | ماتریس authorization | `docs/AUTHORIZATION-MATRIX.md` (۶۸ route × Public/Capability/User/Paid/Admin) + تست ساختاری دوطرفه (route→matrix و matrix→route) + ۳ spot-check گاردها؛ ۳ تست `test_authz_matrix.py` | ✅ |

## آمار نهایی

- **تستها: 209 passed, 1 skipped** (صفر warning)
- CI: ۷ گیت (ruff/bandit/pip-audit/secret/brand/alembic/pytest+coverage) + ۳ گیت boot prod — همه ✅
- کامیتها: c1…c8 (۸ کامیت — هر مورد جدا با پیام audit)
- rollout: `git pull --ff-only` + systemctl restart chart-web + migration (در این فاز مهاجرت جدید لازم نشد)

## باگهای مهم کشفشده (P0 — از قبل در prod بود)

1. **account_delete 500 برای هر کاربر دارای چارت/چت**: SQLAlchemy unitofwork ترتیب حذف FK را درست نمیکند → `session.flush()` بین سطحها + افزودن حذف chat_messages (کاملاً غایب بود). تست cascade هر سه اجرا پاس.
2. **fallback باکت R2** به باکت پروژه دیگر (hermes-voice-clone) → `zayche-storage`.

## هزینه

TTS تستها همگی mock (بدون edge_tts/R2 واقعی) — هزینه صفر دلار. فاز C: **$0**.

## بعدی

فاز D (D1 Web Push، D2 pgvector RAG، D3 کیف پول رفرال، D4 SSE) — تأییدشده توسط MaHDi.
