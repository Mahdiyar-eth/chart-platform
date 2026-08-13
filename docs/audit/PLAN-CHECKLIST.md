# PLAN-CHECKLIST — پلن نهایی چارت تولد v3.0 (منبع حقیقت اجرا)

> **قانون:** قبل از هر ادعای «تمام شد»، این فایل + پلن اصلی (doc_a5342d63779e) دوباره خوانده شود.
> هر آیتم: `[x]` = تأییدشده در کد/تست · `[~]` = ناقص/انحراف مستند · `[ ]` = انجامنشده · `[u]` = نیازمند کاربر
> **هشدار:** بعد از هر context compaction، اول این فایل را load کن — پلن را از حافظهی خلاصهشده حدس نزن.
> **بهروزرسانی:** 2026-08-12 شب — فاز ۱۰ (کامیت 48de0dc) ۸ مورد گمشده را بست؛ جزئیات در reports/v0.7.1-phase10.md

## §4 معماری
- [x] FastAPI + SQLModel + PostgreSQL
- [x] Redis + ARQ (worker فعال، PONG)
- [x] pyswisseph + لایه انتزاعی (engine.py)
- [x] zoneinfo Asia/Tehran (DST خودکار — بدون جدول دستی)
- [x] LLMProvider: DeepSeek + GeminiFree + AvalAI (کلاسها؛ کلید AvalAI/DeepSeek [u])
- [x] Router با fallback (health/quota)
- [x] WeasyPrint + وزیرمتن base64 در PDF
- [x] python-docx + bidi (Word RTL)
- [x] HTMX + Alpine.js + Tailwind (لوکال)
- [x] R2 presigned (302) — bucket hermes-voice-clone, prefix chart-reports/
- [x] زرینپال (سندباکس — مرچنت واقعی [u])
- [x] OTP تنبل Kavenegar (کلید SMS [u]؛ dev-code فعال)
- [~] دیتاست شهرها: ۳۳۷ شهر در ماژول cities_ir.py (انحراف مستند: نه جدول DB)

## §5 موتور نجومی
- [x] خط لوله قطعی (LLM هرگز محاسبه نمیکند)
- [x] حالت «ساعت ندارم» (فرم: سؤال «ساعت تولد را میدانی؟»؛ ASC/خانه حذف)
- [x] Birth Time Finder (rectify.py — با هشدار «تخمین نجومی»)
- [x] Golden Suite ۲۱ تست (پلن: حداقل ۸)
- [x] کش چارت در DB
- [x] tropical + سیدریال/ودیک Lahiri (پارامتر zodiac)

## §6 تفسیر
- [x] Rule Engine داده-محور در کد (rules.py) — [~] انحراف مستند: نه جدول DB
- [x] ۱۳ حوزه با Evidence (تأیید در گزارش واقعی)
- [x] فصل فرهنگی-اسلامی (فاز ۱۰ — پرامپت مجزا، QA تطبیقی، در PDF/Word/JSON)
- [x] QA خودکار (qa.py) + Retry حداکثر ۳
- [x] llm_runs ثبت هر اجرا (provider/tokens/cost/qa_result)
- [x] AI Chat retrieval-based (chat/ — rate limit 40/min)

## §7 مدل داده (انحراف مستند: سادهسازیها)
- [x] users, birth_profiles, charts, reports, plans, orders, coupons, subscriptions, audit_logs, llm_runs, referral_events
- [~] ادغامشده/حذفشده: birth_data (در charts), chart_factors/rules/interpretations (در کد), payments (در orders), transits (محاسبهی لحظهای), synastry_reports (محاسبهی لحظهای), share_cards (سرویس/مسیر), ai_conversations (در فایل سشن), prompt_versions/qa_runs/analytics_events (لاگ ساده) — انحراف مستند، هیچکدام عملکرد را محدود نمیکند

## §8 API
- [x] auth: otp/request, otp/verify
- [x] cities, birth-data(→form), charts, charts/{id}, svg (چرخ/گرید/دونات/بار/KPI/ترانزیت-سالانه)
- [x] preview رایگان ۳-۵ اینسایت (rule-engine، بدون LLM) — فاز ۱۰
- [x] plans, orders, payments/zarinpal (request/callback idempotent)
- [x] reports: status, download pdf/docx (گیت خرید §8 + 302 R2)
- [x] ai-chat (access + messages)
- [x] transits (روزانه) + هفتگی (کرون `0 7 * * 6`) — فاز ۱۰
- [x] synastry (تیزر رایگان + تحلیل کامل پولی — فاز ۱۰)
- [x] share-cards
- [x] ادمین: coupons/refund/stats + plans/users/audit/llm-cost — فاز ۱۰ (پنل کامل)
- [x] ادمین: coupons/refund/stats + plans/users/audit/llm-cost + پرامپتها (prompt_versions — فاز ۱۰) — کامل
- [~] ماشین حالت گزارش: queued/running/done/failed (انحراف مستند از ۷ حالته — خطا/رترای درون job)

## §9 فرانت
- [x] هیبرید HTMX+Alpine (جزایر تعاملی)
- [~] هویت بصری Liquid Glass جزئی (glass+glow+starfield؛ نویز SVG/حباب نور نیست — انحراف زیباییشناختی)
- [x] SVG: چرخ + گرید + دونات + بار + KPI + کارت اشتراک + ترانزیت سالانه — فاز ۱۰
- [x] ترانزیت سالانه (خط زمانی ۱۲ ماهه) — فاز ۱۰
- [x] PWA سبک (مانیفست + آیکون + service worker root-scope /sw.js) — فاز ۱۰

## §10 خروجیها
- [x] PDF (WeasyPrint, RTL, KPI) — حجم بر اساس پلن: پایه ۵ بخش / کامل ۱۳ / طلایی ۱۳+اسلامی+ترانزیت — فاز ۱۰
- [x] Word RTL قابل ویرایش
- [x] صوت (edge-tts فارسی)
- [x] ترانزیت ۴ ماه + نقشه سالانه در PDF طلایی (deterministic، بدون LLM) — فاز ۱۰

## §11 امنیت/DevOps
- [x] callback verify سروربهسرور + idempotency
- [x] OTP rate limit (۵/min) + تلاش محدود
- [x] CSRF + RBAC + audit_logs + Privacy Policy + حذف کامل حساب
- [x] PDF در R2 (DB فقط کلید)
- [x] Secrets فقط env
- [~] systemd (انحراف مستند از Docker Compose)
- [x] CI (scripts/ci.sh ✅ + workflow گیتهاب ci.yml) — فاز ۱۰
- [x] backup روزانه (crontab سیستم)

## §12 درآمد
- [x] پلنها: basic 149k / full 349k / gold 699k + synastry 499k + monthly 399k — seed_plans() idempotent
- [x] اشتراک پولی ماهانه ۳۹۹k (ربات → زرینپال → فعالسازی ۳۰ روزه، /cancel_sub) — فاز ۱۰
- [x] سیناستری پولی ۴۹۹k (تیزر رایگان، فول با سفارش paid) — فاز ۱۰
- [x] گزارش پایه ۵ بخش (تفکیک پلنها) — فاز ۱۰

## §13 فازها (معیار پذیرش)
- [x] فاز ۰ پایه [~] systemd بهجای docker
- [x] فاز ۱ موتور + Golden
- [x] فاز ۲ رایگان (لندینگ+فرم+چارت+BigThree+پیشنمایش رایگان)
- [x] فاز ۳ گزارش + QA + PDF + صف
- [x] فاز ۴ تجاری سندباکس
- [x] فاز ۵ داشبورد + AI Chat
- [x] فاز ۶ Share Cards + SEO + Referral
- [x] فاز ۷ ترانزیت روزانه/هفتگی + اعلان + اشتراک پولی
- [x] فاز ۸ سیناستری پولی
- [x] فاز ۹ Word + ودیک + صوت + BTF

## §15 سؤالات باز مشتری
- [u] نام برند (ستارهنامه/نقشه آسمان/زایچه من...)
- [u] دامنه (chart.negar.io فعلی — برند اختصاصی؟)
- [u] مدارک زرینپال (مرچنت واقعی)
- [u] حساب Kavenegar (کلید SMS)
- [u] تست گوشی واقعی (مقرر: بدون تأیید کاربر روی موبایل، «نهایی» اعلام نمیشود)
- [x] سیناستری: انجام شد
- [x] ودیک: انجام شد

## خلاصه وضعیت (2026-08-12 شب)
- ✅ کامل: ~۷۰ مورد · ⚠️ انحراف مستند: ~۸ (جداول سادهشده، ماشین حالت، Liquid Glass، systemd، شهرها، rules-در-کد) · ❌ باز در کد: **۰** · 👤 نیازمند کاربر: ۵
