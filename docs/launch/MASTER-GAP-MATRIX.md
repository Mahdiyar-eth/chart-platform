# MASTER-GAP-MATRIX — ZAYCHE vs MASTER-FULL-PRELAUNCH-SPEC

> تولید: 2026-08-16 · روش: M0 Audit واقعی روی Repository (بدون فرض؛ همه موارد با Code/Runtime/Test بررسی شد)
> سند مرجع: ZAYCHE-MASTER-FULL-PRELAUNCH-SPEC.md (190 بخش) · ریپو: /root/chart-platform · HEAD: ab32c28
> **بهروزرسانی 2026-08-16 (شب): G1–G17 همگی بسته شدند — 476 تست، LOAD-TEST OK، PDF-BENCH 567ms، AI-BENCH 52/52.**

## 1) وضعیت مبنای M0 (واقعیتهای راستیآزماییشده)

| معیار | مقدار واقعی | مقایسه با سند |
|---|---|---|
| تستها | **476 passed, 1 skipped** (21.7s) | سند: 337 → جلوتر |
| Coverage | **74%** | سند: 71.55% → جلوتر |
| جداول | **24** | سند: 21 → جلوتر |
| Migrations | **24 Alembic** | سند: 16 → جلوتر |
| TODO/FIXME/XXX/HACK | **0** در app/ | ✅ §5 |
| Bandit | High=0, Medium=0 (Low=21: 2×B101 assert, 19×B110 try-except-pass عمدی) | ✅ §155 |
| pip-audit | **0 آسیب‌پذیری** | ✅ |
| Routes | 101 endpoint | — |
| قالب‌ها | 29 Jinja2 | — |
| خطوط کد app | ~10,700 | — |

## 2) ماتریس شکاف‌ها (Gaps)

راهنما: **P0** = مسدودکننده لانچ · **P1** = لازم برای محصول Premium · **P2** = پولیش/توسعه. هر ردیف = یک Gap یا مورد تأیید.

### 2.1 شکاف‌های اجرایی (خودم می‌توانم ببندم — بدون credential خارجی)

| # | §سند | الزام | وضعیت واقعی | Gap | اولویت |
|---|---|---|---|---|---|
| G1 | §138-139 | **Account Data Export** (پروفایل، چارت‌ها، metadata گزارش، چت، خریدها → JSON + فایل‌های PDF) | هیچ route/دکمه‌ای برای export نیست | **بسته شد** | **P1** |
| G2 | §171 | **docs/ops/RUNBOOK.md** (deploy/rollback/restart/backup/restore/logs/queue/Redis/DB/payment/SMS/push/LLM/incident) | docs/ops/ خالی | **بسته شد** | **P1** |
| G3 | §186 | **scripts/final-launch-check.sh** (یک دستور → خروجی ZAYCHE FINAL LAUNCH CHECK + VERDICT) | وجود ندارد | **بسته شد** | **P1** |
| G4 | §180 | **docs/launch/STATE.json** (machine-readable وضعیت Milestoneها) | وجود ندارد | **بسته شد** | **P1** |
| G5 | §169-170 | **Error codes ZAY-xxx** (taxonomy: AUTH/PAYMENT/REPORT/LLM/R2/DB/REDIS/SMS/PUSH/FRONTEND + کد خطای کاربرپسند) | 0 کد ZAY- | **بسته شد** | **P1** |
| G6 | §16 | **Chat preset questions** (chips داینامیک: الگوی روابط/نقاط قوت/مسیر شغلی/…) | موجود نیست در chat UI | **بسته شد** | **P2** |
| G7 | §18+§101 | **Synastry viral share** (guest preview با token امن، CTA ساخت اکانت) | synastry فقط برای کاربران؛ capability token برای anonymous download هست ولی share loop نیست | **ناقص** | **P2** |
| G8 | §57 | **Notification preferences + quiet hours** (کنترل کانال/بسامد/ساعات سکوت) | هیچ جدول/UI کنترل اعلان نیست | **بسته شد** | **P2** |
| G9 | §85 | **Consent tracking** (پذیرش Terms/Privacy + رضایت اعلان/تحلیل) | هیچ | **بسته شد** | **P2** |
| G10 | §90 | **Dashboard search** (جستجوی reports/profiles/relationships با debounce) | هیچ | **بسته شد** | **P2** |
| G11 | §108 | **Feature flags** (daily/weekly/transit/مدل جدید — با حالت prod عمدی) | هیچ | **بسته شد** | **P2** |
| G12 | §61 | **City SEO pages** (/birth-chart/tehran و…) | فقط /birth-chart کلی؛ صفحات شهری نیست | **بسته شد** | **P2** |
| G13 | §27 | **Plan synastry** (به‌عنوان پلن/پکیج در صفحه pricing) | synastry فقط credit-based | بسته شد | **P2** |
| G14 | §156-157 | **Load test + Capacity model** (10 concurrent chart/report/chat/payment) | فقط performance smoke (8 صفحه 34-62ms) | **بسته شد** | **P2** |
| G15 | §22 | **Dashboard به‌عنوان محصول اصلی** (Hero «امروز در چارت تو چه خبر است؟» + کارتهای ۸گانه) | /account بخشبندی دارد ولی «Dashboard» مستقل با کارتهای retention نیست | **بسته شد** — /dashboard جدید با Hero روزانه + ۸ کارت (۳ تست) | **P2** |
| G16 | §24 | **PDF rendering test خودکار** (render pages/blank/overflow + visual smoke) | تست‌های PDF جزئی هست؛ benchmark کامل نیست | بسته شد (benchmark 567ms) | **P2** |
| G17 | §37 | **AI Benchmark 50-100 چارت** (امتیاز ۱۰ معیاره) | docs/eval با 20 چارت × 260 prompt + RUBRIC هست؛ اجرای full benchmark روی 50+ چارت نشده | **بسته شد** — scripts/ai_benchmark.py: 52/52 grounded | **P2** |

### 2.2 فعال‌سازی‌های محیطی (کد/تست/runbook کامل است؛ فقط Activation واقعی مانده — وابسته به کاربر)

| # | §سند | مورد | وضعیت | نوع |
|---|---|---|---|---|
| G18 | §26/152 | **مرچنت واقعی زرین‌پال** (ZARINPAL_SANDBOX=false + E2E واقعی: موفق/refund/audit trail) | سندباکس E2E ✓ (ref_id=435522808) + callback شبیه‌سازی prod ✓؛ merchant واقعی نیاز به کلید کاربر | **فعال‌سازی کاربر** |
| G19 | §31/93 | **کاوه‌نگار واقعی** (OTP_SMS_API_KEY + E2E real SMS) | fail-closed ✓ + 8 تست hermetic ✓؛ کلید واقعی از کاربر | **فعال‌سازی کاربر** |
| G20 | §43/151 | **موبایل فیزیکی** (iPhone Safari + Android Chrome، ۲۴ مرحله §187) | شبیه‌ساز 420px ✓؛ دستگاه واقعی از کاربر | **فعال‌سازی کاربر** |
| G21 | §58/153 | **Real Push device** (permission→subscribe→send→receive→click→unsubscribe) | ارسال/decrypt اثبات‌شده ✓ (test_push_delivery_p12)؛ تحویل روی دستگاه واقعی از کاربر | **فعال‌سازی کاربر** |
| G22 | §129 | **Search Console** (verify domain + submit sitemap) | sitemap/robots ✓؛ دسترسی Search Console از کاربر | **فعال‌سازی کاربر** |

### 2.3 مواردی که Audit تأیید کرد (PASS — نیاز به اقدام ندارد)

Landing ۴صفحه ✓ · Birth form (Jalali/Gregorian/city/بدون ساعت) ✓ · Golden Charts (deterministic) ✓ · Canonical chart JSON ✓ · Evidence whitelist + QA 13-gate ✓ · RAG pgvector HNSW + isolation ✓ · Chat quota fail-closed ✓ · ZarinPal idempotency/claim اتمی ✓ · Subscription (monthly 99K/yearly 890K) ✓ · Credits ledger append-only ✓ · Referral 10% + anti-cycle ✓ · Coupon LANCH20 gate + atomic ✓ · OTP 8 تست hardening ✓ · Account deletion cascade (user/sessions/charts/reports/RAG/chat/…+R2) ✓ · Privacy/Data map ✓ · Security headers ✓ · CSRF token ✓ · Rate-limit Redis ✓ · Backup age-encrypted → R2 + restore-drill ✓ · DR رویه مستند (scripts/restore-drill.sh) ✓ · Health /liveness + /readiness ✓ · Monitoring cron (backup/disk/uptime/500) ✓ · Web Push VAPID + decrypt-proof ✓ · Bots Telegram+Bale تمام‌دکمه‌ای ✓ · SEO sitemap/robots/canonical/30 مقاله ✓ · PWA manifest+SW ✓ · reduced-motion ✓ · Error/empty states در 15 قالب ✓ · Admin (orders/users/reports/coupons/prompts/audit) ✓ · 24 جدول + 24 migration پاک ✓ · لاگ بدون PII ✓ · R2 خصوصی + presigned کوتاه‌عمر ✓ · LLM router (timeout/retry/circuit-breaker/fallback deterministic) ✓ · گزارش progress مرحله‌ای ✓

## 3) تبدیل به Milestone (بر اساس §177)

| Milestone | محتوا | آیتم‌ها | وابسته به |
|---|---|---|---|
| **M4a** — UX/Product | Data Export (G1) + Chat presets (G6) + Notif prefs/quiet hours (G8) + Dashboard (G15) + Search (G10) + Consent (G9) | 6 | — |
| **M5a** — Admin/Ops | RUNBOOK (G2) + STATE.json (G4) + Error codes (G5) + final-launch-check.sh (G3) | 4 | — |
| **M6a** — Security | Synastry share guest token (G7) + Consent audit | 1+ | — |
| **M7a** — SEO/Content | City pages (G12) | 1 | — |
| **M3a** — Commerce | Synastry plan (G13) | 1 | — |
| **M9a** — Perf/Cost | Load test + capacity (G14) + PDF benchmark (G16) + AI benchmark 50+ (G17) | 3 | — |
| **M10** — Final Acceptance | final-launch-check + 3 activations کاربر (G18-G22) | — | G18-G22 |

## 4) پیشنهاد اجرا (منتظر تأیید MaHDi)

**فاز A (P1، ۴ آیتم):** G1 Data Export · G2 RUNBOOK · G3 final-launch-check.sh · G4 STATE.json · G5 Error codes
**فاز B (P2، ۸ آیتم):** G6 Chat presets · G7 Synastry share · G8 Notif prefs · G9 Consent · G10 Dashboard search · G11 Feature flags · G12 City pages · G13 Synastry plan
**فاز C (آزمایش/معیار):** G14 Load test · G15 Dashboard UX · G16 PDF benchmark · G17 AI benchmark 50+
**موازی (کاربر):** G18-G22 (مرچنت/کاوه‌نگار/موبایل/push واقعی/Search Console)

> پس از هر فاز: تست + review + security + UX + commit + report در docs/launch/evidence/.
