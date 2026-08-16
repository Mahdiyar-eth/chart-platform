# P13 — MASTER-SPEC GAPS (G1–G17) — ALL CLOSED

> تاریخ: 2026-08-16 · ریپو: /root/chart-platform · برچسب: (بدون tag — HEAD بعد از c80cc63)
> سند مرجع: ZAYCHE-MASTER-FULL-PRELAUNCH-SPEC.md (190 بخش) · ماتریس: docs/launch/MASTER-GAP-MATRIX.md

## خلاصه

تمام ۱۷ شکاف اجرایی (۵ P1 + ۱۲ P2) بسته شد. **OPEN P0/P1/P2 = 0** — فقط ۵ فعالسازی
محیطی (مرچنت زرینپال، کاوهنگار، موبایل فیزیکی، push واقعی، Search Console) باقی است که
همه وابسته به credential/دستگاه کاربر هستند (کد + تست + runbook آماده).

| وضعیت | عدد |
|---|---|
| تستها | **480 passed, 1 skipped** (20.9s) |
| ruff (F/E9) | 0 |
| Load test (local + prod) | **OK** — p95 < 133ms، 0 خطا (360 req prod) |
| PDF benchmark | **567ms** / 38.3 KiB (۱۳ بخش RTL) |
| AI benchmark | **52/52 grounded** (بدون خطا) |
| bandit | High=0 Med=0 |
| final-launch-check | **VERDICT: GO** |

## تغییرات (به تفکیک Gap)

| Gap | پیادهسازی | شواهد |
|---|---|---|
| G1 Data Export (§138) | `/account/export` — JSON اختصاصی (پروفایل/چارت/گزارش/سفارش/چت/لجر + URL امضاشده)، بدون secret؛ دکمه در حساب | ۳ تست + matrix |
| G2 RUNBOOK (§171) | `docs/ops/RUNBOOK.md` (انتقال + بهروزرسانی: ۴۸۰ تست، DR، فاز G3) | — |
| G3 final-launch-check (§186) | `scripts/final-launch-check.sh` — ۱۲ گیت → VERDICT | **GO** |
| G4 STATE.json (§180) | `docs/launch/STATE.json` — machine-readable | — |
| G5 Error codes (§169) | `app/errors.py` + ۱۲ پیام فارسی کددار (ZAY-SMS-001، ZAY-AUTH-003، ZAY-PAY-001…) | ۵ تست |
| G6 Chat presets (§16) | چیپهای داینامیک از Big Three واقعی چارت + ۵ سؤال ثابت | ۱ تست |
| G7 Synastry share (§18) | `/api/synastry/share` (HMAC) + صفحه مهمان `/s/{token}` (فقط نمره+نتیجه، rate-limit، دستکاری→404) | ۳ تست |
| G8 Notif prefs (§57) | جدول `notification_prefs` (migration 5897f4417ccf) + GET/POST + UI Alpine (۳ سوییچ + ساعت سکوت) | ۳ تست |
| G9 Consent (§85) | جدول `consent_logs` (migration 575c0e692ce6) + ثبت خودکار در ثبتنام (terms+privacy v1) + `/api/consent` | ۲ تست |
| G10 Dashboard search (§90) | جعبه جستجو (Alpine، نرمالسازی ی/ک، فیلتر پروفایل/گزارش/سفارش) | ۱ تست |
| G11 Feature flags (§108) | `app/feature_flags.py` (DB>env>default، کش، admin toggle) + گیت chat (503) + گیت SEO شهر | ۳ تست |
| G12 City SEO (§61) | ۱۰ صفحه `/birth-chart/{slug}` (تهران…رشت) + sitemap + flag-gate | ۴ تست |
| G13 Synastry plan (§27) | کارت ۴۹۹هزارتومانی در /plans → /synastry | ۱ تست |
| G14 Load test (§156) | `scripts/load_test.py` — concurrent + XFF متنوع + گزارش p50/p95/err | local+prod OK |
| G15 Dashboard (§22) | `/dashboard` — Hero «امروز در چارت تو چه خبر است؟» + ۸ کارت retention + CTA حالت خالی + لینک nav | ۳ تست |
| G16 PDF bench (§24) | `scripts/pdf_benchmark.py` — render واقعی ۱۳ بخش RTL | 567ms |
| G17 AI bench (§37) | `scripts/ai_benchmark.py` — ۵۲ چارت متنوع، سؤال deterministic، grounded check | 52/52 |

## فایلهای جدید/تغییرکرده اصلی

- app/: `errors.py` (جدید)، `feature_flags.py` (جدید)، `main.py` (+۵ route: export/dashboard/consent/notif-prefs/synastry-share + gate chat)، `auth.py` (consent ثبتنام)، `models.py` (+۲ جدول)، `routes/seo.py` (+۱۰ صفحه شهر)، `routes/admin.py` (+flags)
- templates/: `dashboard.html` (جدید)، `synastry_share.html` (جدید)، `birth_chart_city.html` (جدید)، chat.html/account.html/plans.html/base.html (تغییر)
- scripts/: `load_test.py`، `pdf_benchmark.py`، `ai_benchmark.py`، `final-launch-check.sh` (جدید)
- docs/: `ops/RUNBOOK.md`، `launch/STATE.json`، AUTHORIZATION-MATRIX (تکمیل)
- tests/: ۱۰ فایل تست G6…G17 (۲۶ تست جدید)
- migrations: 5897f4417ccf (notification_prefs) + 575c0e692ce6 (consent_logs) — **deploy شده با --migrate**

## Commits

1. `c80cc63` — G6–G13 (فاز B)
2. (فیکس race تست G9)
3. (فاز C + G15) — matrix بسته، 480 تست

## Rollback

```bash
git reset --hard v-p11-preflight && bash scripts/deploy.sh --migrate
```

## باقیمانده (فعالسازیهای کاربر — G18–G22)

مرچنت واقعی زرینپال · کلید کاوهنگار (OTP prod) · تست موبایل فیزیکی (checklist در P12) · push روی دستگاه واقعی · دسترسی Search Console
