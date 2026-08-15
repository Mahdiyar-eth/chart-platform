# P12 — GO / NO-GO نهایی — به‌روزرسانی پس از ۷ گیت review (🟡 CONDITIONAL → ✅ FINAL GO)

**تاریخ:** 2026-08-15 | **HEAD:** v-p11-preflight + P12-gates | **تست‌ها: 451 passed, 1 skipped**

## وضعیت ۷ گیت

| # | گیت | وضعیت | شواهد |
|---|---|---|---|
| 1 | Kavenegar + OTP | 🟢 **منطق بسته** — ۸ تست hermetic (expiry، resend→کد قبلی باطل، wrong code، brute force، concurrent، enumeration، logout/relogin، mock Kavenegar) + **باگ واقعی فیکس شد**: `attempts > MAX` اجازهٔ ۶ تلاش می‌داد → `>= MAX` (۵ تلاش). E2E واقعی SMS ⏳ **در انتظار `OTP_SMS_API_KEY` واقعی از کاربر** | tests/test_otp_hardening_p12.py (8 passed) |
| 2 | موبایل فیزیکی | ⏳ **اقدام کاربر** — شبیه‌ساز ۴۲۰px کامل پاس؛ checklist دقیق آماده شد (پایین) | p12_ux_audit + P5–P9 browser |
| 3 | Web Push delivery | 🟢 **بسته** — اثبات واقعی: ارسال از مسیر واقعی app (pywebpush + VAPID واقعی .env) به گیرندهٔ TLS محلی + **decrypt کامل payload با http_ece** → «تست زایچه» دریافت شد. VAPID JWT + aes128gcm + ttl تأیید. تست دائمی شد | tests/test_push_delivery_p12.py (PASS) |
| 4 | skip تست | 🟢 **بسته** — تنها skip: `test_golden_charts.py:54` «chart-2-no-time» (تولد بدون ساعت — golden عمدی؛ capability لانچ نیست) | مستند در بالا |
| 5 | OmniRoute | 🟢 **بسته** — P11 اصلاح شد؛ **chart-platform به OmniRoute وصل نیست** — فقط `https://opencode.ai/zen/go/v1` با GO_API_KEY؛ شواهد: llm_runs ۱٬۲۲۲ ران همه provider=go (آخرین 2026-08-15) | reports/launch/P11-PREFLIGHT.md |
| 6 | B108 | 🟢 **بسته** — ۳ فیکس واقعی: share-cache/audio/audit-log به `data/private-tmp` (mode 0700، owner zayche)؛ CLI debug با # nosec مستند. **bandit: High=0، Medium=0** | app/private_tmp.py + bandit re-run |
| 7 | UX/conversion/trust | 🟢 **بسته** — audit مرورگر ۴ صفحه × ۹ معیار = ۳۶/۳۶ ✅ (h1، CTA بالای fold، رایگان، trust، privacy، limitation، بدون ادعای جعلی — تنها «پیش‌گویی» در context نفی است) | p12_ux_audit.py |

## موارد باز (فقط اقدام کاربر — مانند Merchant)

1. **کلید کاوه‌نگار واقعی** → `OTP_SMS_API_KEY` → سپس E2E واقعی SMS (send→receive→verify→session→logout→relogin)
2. **موبایل فیزیکی** — iPhone Safari + Android Chrome، جریان کامل (Landing→Birth→Chart→Free Preview→Exploration→Checkout→Today→Subscription→History→Chat→Logout)
3. **مرچنت واقعی زرین‌پال** → `ZARINPAL_SANDBOX=false`

## Checklist موبایل فیزیکی (برای MaHDi)

- [ ] iPhone Safari + Android Chrome — باز کردن chart.negar.io
- [ ] Landing → «چارت رایگان من» → فرم تولد (کیبورد فارسی، اسکرول، safe-area)
- [ ] ساخت چارت → پیش‌نمایش رایگان → ۵ بینش
- [ ] کاوش: اولین رایگان، بعدی → پیام «اعتبار کافی نداری» + خرید اعتبار
- [ ] خرید پک ۳ (سندباکس) → StartPay → بازگشت → گرنت اعتبار
- [ ] Today + تاریخچه + اشتراک ماهانه (۹۹K) + لغو
- [ ] Chat (طلایی) + خروج از حساب + ورود مجدد با OTP
- [ ] Back/scroll/keyboard در همهٔ صفحات + چرخش صفحه + قطع/وصل اینترنت
- [ ] اعلان push: اجازه → دریافت نوتیفیکیشن → کلیک → لینک درست

## Verdict

# ✅ FINAL GO (مشروط به ۳ فعال‌سازی کاربر)

فقط Merchant واقعی + کلید کاوه‌نگار + تست موبایل فیزیکی باقی مانده — هیچ‌کدام نیاز به تغییر کد ندارند (env-only یا تست دستی).
