# M0 — Repository Audit (ZAYCHE)

> تاریخ: 2026-08-16 · روش: بررسی مستقیم Code/Runtime/Test — بدون فرض (طبق §3 سند Master)
> HEAD: ab32c28 (docs: ZAYCHE-FULL-BUNDLE.md) · branch: main

## 1) Inventory

| بخش | تعداد | یادداشت |
|---|---|---|
| تست‌ها | **451 passed, 1 skipped** | 75 فایل تست؛ 21.5s |
| Coverage | **74%** | (سند قبلی: 71.55%) |
| جداول DB | **24** | SQLModel |
| Migrations | **24** Alembic | زنجیره پاک (`alembic check` پاک) |
| Endpoints | **101** | main.py + routes/ |
| قالب‌ها | **29** Jinja2 RTL + Alpine |
| خطوط app/ | ~10,700 | بدون __pycache__ |
| TODO/FIXME | **0** | grep در app/ |
| Bots | Telegram + Bale (handler.py, state.py) |

## 2) وضعیت کیفیت

- ruff F/E9: پاک · bandit: High=0, Medium=0 (Low=21: 2×B101 + 19×B110 — عمدی/مستند) · pip-audit: 0 vuln
- Coverage 74% · تست‌های real (نه mock-only): DB واقعی، Redis واقعی، HTTP واقعی، PDF، push decrypt-proof، زرین‌پال sandbox، callback شبیه‌سازی prod

## 3) ویژگی‌های موجود (تأیید در کد)

daily(/today + /api/today + reflection) · weekly (ترانزیت هفتگی) · transit (timeline + sky-today) · synastry (+order) · subscription (monthly 99K/yearly 890K + grant ماهانه) · referral (10% + 1 credit + anti-cycle) · coupon (LANCH20 gate + atomic) · refund (زرین‌پال + ledger) · account delete (cascade کامل + R2) · guest capability token · push (VAPID + FCM + decrypt-proof) · RAG (pgvector HNSW + isolation) · chat (SSE stream + quota) · audio (edge-tts → R2 presigned) · pdf (RTL + report) · admin (users/orders/reports/coupons/prompts/audit) · umami (analytics.negar.io) · OTP (fail-closed + 8 تست) · PWA (manifest + SW) · legal pages (privacy/terms/refund/disclaimer/contact/about/guide/faq) · sitemap.xml/robots.txt/canonical · 30 مقاله SEO · landing×4 · reduced-motion · error/empty states (15 قالب) · CSRF/security headers/rate-limit Redis · backup age→R2 + restore-drill (DR) · monitoring crons (backup/disk/uptime/500) · /liveness + /readiness · pricing (basic 149K/full 349K/gold 699K/credit3-6-12) · golden charts deterministic · evidence whitelist + QA 13-gate · LLM router (timeout/retry/circuit-breaker/fallback)

## 4) شکاف‌های شناسایی‌شده (خلاصه — جزئیات در MASTER-GAP-MATRIX.md)

**P1 (اجرایی، بدون credential):** Data Export (§138) · RUNBOOK (§171) · final-launch-check.sh (§186) · STATE.json (§180) · Error codes ZAY-xxx (§169)

**P2 (پولیش/توسعه):** Chat presets (§16) · Synastry share loop (§18) · Notif prefs/quiet hours (§57) · Consent (§85) · Dashboard search (§90) · Feature flags (§108) · City SEO pages (§61) · Synastry plan (§27) · Load test/capacity (§156-157) · PDF benchmark (§24) · AI benchmark 50+ (§37) · Dashboard محصول اصلی (§22)

**فعال‌سازی کاربر (کد کامل است):** مرچنت واقعی زرین‌پال · کلید کاوه‌نگار · موبایل فیزیکی · push واقعی · Search Console

## 5) Verdict اولیه

- **Open P0 = 0** (هیچ باگ بحرانی/نقص امنیتی/مسیر از دست رفتن داده در کد یافت نشد)
- Open P1 = 5 · Open P2 = 12 (همه قابل اجرا توسط Hermes بدون credential خارجی)
- 5 فعال‌سازی محیطی = وظیفه کاربر (دستورالعمل کامل در P12)

> طبق §190: اجرای P1/P2 بعد از تأیید کاربر شروع می‌شود.
