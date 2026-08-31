# ZAYCHE — دور ۴ (پاسخ به بازبینی Opus R4) — ۱۴۰۴/۰۶/۰۱

## نتیجه: W1–W10 اجرا شد؛ **CI واقعاً از مخزن سبز** (GitHub Actions run #249 SUCCESS)؛ prod لایو.

## راستی‌آزمایی Opus R4 (قبل از فیکس)
با `act` (اجرای محلی دقیق همان workflow) **عین خطاهای CI را بازتولید کردم** و هر ادعا را با کد/اجرا تأیید کردم:
- P0-1: pgvector در requirements نبود (فقط در venv) → نصب تازه می‌مرد
- P0-2: `ADMIN_PIN` در ci.yml/conftest نبود → collection می‌شکست
- P0-3: ۷ مسیر مطلق `/root/chart-platform` (فقط sky/engine واسمدار getenv داشتند)
- P0-4: فیکس Z2 (برگرداندن FK) دو تست b1 را با ForeignKeyViolation شکست (تست‌ها chart قلابی می‌ساختند)
- P1-1: موکِ E2E `transit_narrative.build_router` را پچ می‌کرد ولی اندپوینت روتر را از `core.llm` می‌ساخت → موک بی‌اثر و LLM پولی واقعی صدا زده می‌شد
- P1-2: مسیر ارتقا/گزارش (buy gold بعد full → plan_key غلط و دانلود 403)

## فیکس‌ها (کامیت 0ca60e6)
| ID | فیکس |
|---|---|
| W1 | `pgvector==0.5.0` به requirements.txt + تصویر `pgvector/pgvector:pg16` |
| W2 | ADMIN_PIN + AUTH/SECRETS/ADMIN در conftest (setdefault) و ci.yml — **فقط** secretهای import-blocking، نه R2/VAPID (که ۳ تست واقعی را می‌شکستند) |
| W3 | تست‌های b1 cache با چارت واقعی (FK-safe) — روی اسکیمای تازه ۱۸ تست سبز |
| W4 | موک اصلاح شد: `app.core.llm.build_router` + `build_chat_router` پچ می‌شود — هرمتیک، ۵ تست بدون کلید |
| W6/W7 | هر ۷ مسیر مطلق → `BASE_DIR`/`__file__` + گیت CI منع رشتهٔ `/root/chart-platform` |
| W8 | صفحهٔ گذرها بازطراحی: مرتب‌سازی وزن، گروه ماهانه، CTA + سلکتور بالا، نمونهٔ تحلیل (teaser) — با مرورگر واقعی + vision تأیید |
| W9 | حذف Subscriber در account_delete (بر اساس phone) |
| W10 | تست مسیر صوت بدون monkeypatch گیت (با Order پولی واقعی) |

## CI — سبز واقعی از مخزن (مدرک: GitHub Actions run #249)
https://github.com/Mahdiyar-eth/chart-platform/actions/runs/32667575117

ریشه‌های پنهانی که فقط در CI ظاهر می‌شدند و فیکس شدند:
1. **pgvector extension**: «permission denied to create extension vector» — اپ (chart_test که superuser است) خودش می‌سازد؛ mount initdb حذف شد (EACCES در checkout می‌داد)
2. **venv**: برنامه‌های مخزن `venv/bin/*` استفاده می‌کنند ولی workflow `pip` سراسری بود → حالا venv می‌سازد
3. **R2/VAPID تست‌های integration**: `upload_bytes` fallback لوکال (prod fail-closed می‌ماند) + تست 503-tolerance برای VAPID + Chromium نصب شد
4. **prod-boot smoke بدون .env**: RATE_LIMIT_BACKEND=redis + R2 سه‌تایی dummy در subprocess
5. **fake-positive برند**: ۲ خط anti-فال‌بازی whitelist شد

نتیجهٔ نهایی روی اسکیمای تازه و بدون هیچ وابستگی خارجی:
- **703 passed + 1 skipped**، پوشش ۸۲٪
- drift gate روی DB واقعاً خالی: **CLEAN**
- boot smoke های prod-mode (fail-closed secrets/R2/rate-limit) ✓ · prod-boot + critical routes ✓
- compileall ✓ · ruff F,E9 ✓ · bandit ✓ · pip-audit ✓ · secret scan ✓ · brand ✓ · abs-path ✓
- **CI-EXIT=0 → CI OK**

## استقرار
main=0ca60e6 پوش شد؛ chart-web/worker ریاستارت؛ /health سبز. گزارش قبلی: HERMES-ROUND21.md (R2.1).

## مانده (تصمیم مالک / ریز)
- GSC sitemap + SMS آنبوردینگ (سمت کاربر)
- بازبینی دور ۵ برای کلود آماده شود
