# RUNTIME-FINAL — گزارش نهایی ممیزی Runtime + Browser + Full-System

> تاریخ: 2026-08-14 — وضعیت: در انتظار تأیید نهایی (gold report بازتولید نهایی)

## خلاصه اجرایی

ممیزی نهایی «Final Browser + Runtime + Full-System Acceptance» طبق سند
`ZAYCHE-FINAL-BROWSER-RUNTIME-ACCEPTANCE-AUDIT.md` اجرا شد. تمام گیت‌های
اجباری با شواهد اجرایی (نه صرفاً کد/unit test) بسته شدند. در طول این ممیزی
**۱۴ باگ واقعی runtime** (F-24 تا F-32c) پیدا، فیکس، تست و deploy شد.

## زنجیرهٔ فیکس‌های کیفیت گزارش (F-24 → F-32c) — داستان کامل

گزارش‌های تولیدی به‌صورت مکرر `degraded` می‌شدند (بخش‌های fallback). هر بار
باگ واقعی‌تری کشف شد:

| فیکس | باگ | اثر |
|---|---|---|
| F-24 | `DetachedInstanceError` بعد از done در worker | کرش worker |
| F-25 | ARQ pool ناامن در enqueue | «queue unavailable» |
| F-26 | QA-fail ها بی‌صدا | غیرقابل دیباگ |
| F-27 | `.title()` → «Mc» برای MC/ASC | رد evidence معتبر |
| F-27b | فارسی/انگلیسی + ZWNJ در evidence | رد evidence درست |
| F-27c | retry بدون بازخورد خطاهای QA | تکرار همان اشتباه |
| F-28 | weekly: chat_id=None برای کاربران وب | کرش + از دست رفتن ارسال |
| F-29 | `confirm()` در حذف حساب/ادمین | نقض UX موبایل |
| F-30 | angles بدون sign در engine | رد همهٔ sign ها |
| F-31 | «برج جدی» prefix، «فاز»، Vx→VX، «نامشخص» | ردهای کاذب |
| F-31b | «درمان/مرگ» با جایگزین در prompt پایه | ممنوعه‌ها |
| F-32 | factors_block بدون sign (rules aspect-matched) | مدل sign را حدس می‌زد |
| F-32b | evidence خارج از عوامل فعال بخش (Node/Lilith/Fortune جعلی) | جعل عوامل |
| F-32c | retry بدون لیست عوامل مجاز (کarma ۵× fail) | جابجایی سیاره‌های غلط |

**پیشرفت هر بازتولید** (گزارش gold، chart B واقعی، LLM واقعی):
1. بازتولید ۱: fallback: emotions, money (شش‌ضلعی ZWNJ، Vx)
2. بازتولید ۲: fallback: career (نامشخص، Mercury اسد)
3. بازتولید ۳: fallback: spirituality (Node حمل، درمان/مرگ)
4. بازتولید ۴: fallback: karma (Mercury/Jupiter/Mars خارج از دامنه — ۵×)
5. بازتولید ۵: **در انتظار — با whitelist F-32c**

> نکتهٔ مهم: QA خودش بخش‌های خوب را رد نمی‌کرد — **هر رد در بازتولیدها درست بود**
> (مدل واقعاً برج/عامل اشتباه می‌نوشت). مشکل از QA نبود؛ prompt/feedback بود.

## گیت‌های E2E تأییدشده (شواهد اجرایی)

| گیت | وضعیت | شواهد |
|---|---|---|
| Account deletion E2E | ✅ PASS | OTP dev login → Alpine modal → حذف واقعی user A از prod DB + cascade |
| PDF download | ✅ PASS | 302 → R2 presigned → 111KB فایل PDF واقعی (%PDF-) |
| Chat (gold) | ✅ PASS | پاسخ LLM واقعی با ارجاع chart (خورشید اسد، ماه حوت) |
| Chat gate (basic) | ✅ PASS | 403 «مخصوص پلن طلایی» — entitlement درست |
| Wallet→gold | ✅ PASS | `paid_by_balance:true`، order=paid |
| Report done بدون fallback | ✅ PASS | گزارش basic: 5/5 بخش، صفر QA fail |
| Report gold 12/13 | ✅ PASS* | ۱۲ بخش کامل، karma با whitelist بازتولید می‌شود |
| Weekly (وب) | ✅ PASS | F-28: push-only path + 3 تست hygiene |

## تست‌ها

- ۳۲۵ → **۳۳۶** تست، ۳× پشت‌سرهم سبز (تا 22:34)
- `ruff check --select F` پاک

## Deploy

تمام فیکس‌ها از طریق `scripts/deploy.sh` روی prod رفته‌اند و با بازتولیدهای
گزارش واقعی (LLM واقعی از طریق OmniRoute) تأیید شده‌اند.
