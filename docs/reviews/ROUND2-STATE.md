# ZAYCHE دور ۲ — وضعیت دقیق (snapshot برای ضدفراموشی، آپدیت میشود)

## هدف
اجرای پلن دور ۲ از بازبینی کلود (`docs/reviews/OPUS-REVIEW-R1.md` روی شاخه `claude/hermes-project-review-plan-kaziw5`).
راستیآزمایی کامل شد: هر ۲۵ ادعا TRUE بود → مستند `docs/reviews/HERMES-VERIFICATION-R1.json`.
قانون: هیچ فیچر جدید؛ فقط وصلکردن ساختهشدهها. LLM در تست‌ها mock است ($0).

## کامیت‌های انجامشده روی main (local، هنوز push نشده)
- `49fc709` [R2-phase1 X1-X7] نشتهای مالی:
  R1 کش گذر نرمال (list/dict) · R2 idempotency per-user+period + short-circuit قبل LLM ·
  R3 refund نسبتی (ceil(price×failed/total)) + refund(amount=) · R6 اتمیک grant_from_credits با spend(commit=False)+flush ·
  R5 has() اسکوپ اجباری + purchase chart_id الزامی برای report_*/transit_*/synastry_* (chat_pack کاربر-level) ·
  R7 consume() چت در api_chat بعد از جواب موفق (request.state.chat_ent) + expires_at ۳۰روزه چتپک ·
  R20/R21 رد کلید تهی + IntegrityError-hardening refund/grant.
- `211baac` [R2-phase2 X8-X13,R8] اقتصاد اعتبار وصل به محصول:
  R4/X8 تولید گزارش با اعتبار بدون Order (plan_key از reason تراکنش؛ basic/full/gold) ·
  credit_cta.html دکمه خرید واقعی POST /api/purchase دارد (action_key/chart_id/next) ·
  include در transits_forecast.html (402) + chart.html · have_credits در context دو صفحه ·
  X11 E2E سبز: buy→report→transit→chat→balance (tests/test_round2_e2e_credit_economy.py) ·
  X8b گزارش از اعتبار تست شده · صفحات جدید /credits /orders /reports + قالبها + nav + AUTHORIZATION-MATRIX ·
  R8 rectify گیت اعتبار بعد از نتیجه موفق (session param اضافه شد) + audio request گیت ۱ اعتبار.
- `<phase3>` [R2-phase3 X14-X17,R9-R12] امنیت: subscribe rate-limit ۵/۱۰دقیقه + dedupe contact ·
  unsubscribe GET→صفحه تأیید + POST واقعی · funnel GROUP BY در DB · PDF راهنما مسیر نسبی + commit فایل (+.gitignore exception !app/static/guides/*.pdf) · track request-param NameError fix · tests/test_round2_security.py ۴ تست سبز.
  (کامیت phase3 زده شد ولی hash را در پیام بعدی ببین — git log)

## کار در حال انجام (مرحلهٔ ۴ — UI/تم روشن)
فایلهای تغییر یافته فعلی (کامیت نشده):
- tokens.css: توکنهای --w-d* (سفید آلفا)، --gold-text/--warn-txt تیره در تم روشن (--gold-text:#755404, --warn-txt:#5f3c0c)، --green-ink (#0e7a43 dark/#0b6b3a light)
- generated.css: صفر رنگ خام (همه var())؛ color:var(--bg-glow)→var(--muted-3) ×۱۱؛ st-02f80eba→--green-ink
- base.css/components.css: همه rgba(255,255,255,A)→var(--w-dA,...)؛ متنهای طلایی→--gold-text
- scripts/ui_audit.py: THEME env (AUDIT_THEME) + BASE contrast theme-aware
- main.py: هندلرهای ۴۰۴/۵۰۰ فارسی + قالب error.html
- nav.py: transits state-aware (/transits/{chart} با چارت، وگرنه /sky) + سقف ۶
- R22: TTL rewrite روایتها را حفظ میکند (transit_cache.py) · R23: UniqueConstraint (chart_id,months) در models.py
- R24: _crossing_points حذف شد اما _EventRaw باید قبل از استفادهکنندهاش تعریف باشد (برگردانده شد)
- تست R22 در test_round2_e2e_credit_economy.py سبز

## ماندهٔ مرحلهٔ ۴
- صفحهٔ اصلی تم روشن هنوز ۱۷ عنصر کمکنتراست: `.more` spanها و لینک st-8491e6e3 در index.html رنگ rgb(245,197,24)=--gold دارند → باید --gold-text شوند (در index.html یا generated.css: کلاس more و st-8491e6e3).
- سپس ممیزی کامل ۱۶ صفحه در تم روشن (AUDIT_THEME=light) تا ۰ finding.
- تست دیزاینسیستم (test_design_system_c1) بعد از دستکاری CSS باید re-run شود.

## مرحلهٔ ۵ (آخر)
- رگرسیون کامل chunk-by-chunk با bash /tmp/run_chunks.sh (الگوی قبلی؛ DB تست chart_platform_test)
- کامیت + push main + استقرار prod: merge فقط با git checkout main && git merge --ff-only && systemctl restart chart-web chart-worker
- گزارش docs/reports/HERMES-ROUND2.md

## نکات محیطی
- uvicorn تست: port 8798، DATABASE_URL=postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test CREATE_ALL_ON_BOOT=1 SWISSEPH_EPHE_PATH=/root/chart-platform/ephe (رمز در conftest هست، در لاگ mask نمیشود اگر دستی بدهم)
- سرور ۸GB — pytest فقط chunk-by-chunk
- پرداخت mock/zarinpal sandbox — درگاه واقعی ممنوع
- compression.threshold الان ۰.۷۵ شد (خواستهٔ مهدی)
- قانون: «قابل دسترس بودن» + «تست کلیک کاربر» + «متریک≠هدف» برای همه تسکها
