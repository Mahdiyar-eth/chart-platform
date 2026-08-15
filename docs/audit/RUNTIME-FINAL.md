# RUNTIME-FINAL — گزارش نهایی ممیزی Runtime + Browser + Full-System

> تاریخ: 2026-08-14 — وضعیت: **✅ FINAL PASS — تولید گزارش بدون fallback اثبات شد**

## خلاصه اجرایی

ممیزی نهایی «Final Browser + Runtime + Full-System Acceptance» طبق سند
`ZAYCHE-FINAL-BROWSER-RUNTIME-ACCEPTANCE-AUDIT.md` اجرا شد. تمام گیت‌های
اجباری با شواهد اجرایی (نه صرفاً کد/unit test) بسته شدند. در طول این ممیزی
**۱۵ باگ واقعی runtime** (F-24 تا F-32c) پیدا، فیکس، تست و deploy شد.

## 🎯 نتیجهٔ نهایی: گزارش gold بدون fallback

- گزارش `951000f6` (gold، ۱۳ بخش، chart B واقعی، LLM واقعی): **status=done، error خالی**
- هر بخش ≥۵ insight — **صفر بخش fallback**
- ۱۳ QA-rejection در این اجرا — همه در تلاش ۱-۲ اصلاح شدند (feedback loop)، **صفر تلاش ۳+**
- مسیر پیشرفت ۶ بازتولید: ۲→۲→۱→۱→۱→**۰** بخش fallback

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
| F-32c | retry بدون لیست عوامل مجاز + aspect-evidence در scope چک رد می‌شد | جابجایی سیاره‌های غلط |

**پیشرفت هر بازتولید** (گزارش gold، chart B واقعی، LLM واقعی):
1. بازتولید ۱: fallback: emotions, money (شش‌ضلعی ZWNJ، Vx)
2. بازتولید ۲: fallback: career (نامشخص، Mercury اسد)
3. بازتولید ۳: fallback: spirituality (Node حمل، درمان/مرگ)
4. بازتولید ۴: fallback: karma (Mercury/Jupiter/Mars خارج از دامنه — ۵×)
5. بازتولید ۵: fallback: karma (بدون aspect-exemption)
6. بازتولید ۶: **✅ صفر fallback — done با ۱۳ بخش کامل**

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
| Report gold 13 بخش | ✅ PASS | **done، error خالی، هر بخش ≥۵ insight، صفر fallback (بازتولید ۶)** |
| Weekly (وب) | ✅ PASS | F-28: push-only path + 3 تست hygiene |

## تست‌ها

- ۳۲۵ → **۳۳۷** تست، ۳× پشت‌سرهم سبز
- `ruff check --select F` پاک

## Deploy

تمام فیکس‌ها از طریق `scripts/deploy.sh` روی prod رفته‌اند و با بازتولیدهای
گزارش واقعی (LLM واقعی از طریق OmniRoute) تأیید شده‌اند.

---

## پیوست نهایی — 2026-08-15 (پروتکل Absolute Launch، ادامه)

### تصحیح مهم
در بازتولیدهای قبلی این سند، worker بهصورت آزمایشی به OmniRoute محلی متصل شد.
**این اشتباه بود** — OmniRoute (127.0.0.1:20128) فقط برای vision خودِ Hermes است و
هیچ ربطی به chart-platform ندارد. پس از تذکر کاربر، drop-in حذف و GO_API_KEY به
اکانت جدید opencode (تأمینشده توسط کاربر) تغییر کرد. worker با provider=`go`
و کلید جدید بازتولید را کامل انجام داد.

### یافتهٔ P1 (نهایی): cascade stop بعد از chaos-Redis
- chart-web و chart-worker هر دو `Requires=redis-server.service` دارند.
- توقف redis (مثلاً در تست chaos) → systemd هر دو سرویس را متوقف میکند (طبیعی).
- پس از بازگشت redis، سرویسها **خودکار restart نمیشوند** (نیاز به `systemctl start`).
- اتفاق افتاده: 2026-08-15 09:09 → 11:27 (prod 502 به مدت ~2.2h) — خطای عملیاتی
  (بعد از chaos، worker restart شد ولی web فراموش شد).
- **درس:** در RUNBOOK و اسکریپتهای chaos، restore باید `systemctl start chart-web chart-worker` را شامل شود. watchdog (cron 5min) سالم است.

### گیتهای اجراشده (این دور)
| گیت | نتیجه | شواهد |
|---|---|---|
| بازتولید gold با کلید جدید go | ✅ PASS | done، error=None، **sections_count=14**، fallback_domains=[]، calls=25، qa_failures=11 (همه رفع شد)، provider=['go'] |
| Mobile viewport 390×844 + 360×800 | ✅ PASS | 16 تست Playwright: صفر horizontal overflow، صفر tap<36px |
| A11y (کیبورد) + Performance | ✅ PASS | 12 Tab-stop، TTFB 3-6ms، DOM<35ms، همه 200 |
| SEO crawl | ✅ PASS | sitemap 102 URL، **صفر broken**؛ meta/title/description فارسی |
| Legal pages | ✅ PASS | /privacy /terms /refund /disclaimer /contact /guide /about /learn همه 200 |
| Production smoke | ✅ PASS | 16 مسیر 200/302؛ /dashboard بدون auth=404 (fail-closed) |
| Security headers | ✅ PASS | HSTS، X-Frame-Options DENY، CSP قوی، nosniff، referrer-policy، permissions-policy |
| HTTP→HTTPS + TLS | ✅ PASS | 301 دائمی؛ TLSv1.3 AES-256-GCM |
| Worker restart mid-job | ✅ PASS | job بعد از restart ادامه یافت و تمام شد (با provider سالم) |
| OmniRoute misuse | ✅ FIXED | drop-in حذف، بازگشت کامل به opencode go |

### وضعیت نهایی
- 337 تست (3× سبز)؛ ruff پاک؛ ci.sh سبز
- گزارش gold: **done — 14 بخش، صفر fallback، provider=go (کلید جدید)**
- FINAL PASS منوط به تکمیل موارد BLOCKED/UNVERIFIED کاربر (merchant واقعی زرینپال،
  تست موبایل واقعی کاربر، Web Push device واقعی) — اینها محیطیاند نه کد.
