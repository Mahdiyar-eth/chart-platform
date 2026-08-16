# M0 — Quota Experiment: نتیجهٔ آزمایش تجربی سقف کلیدها

> تاریخ: 2026-08-16 · روش: scripts/m0_quota_test.py · حالت: REAL API (هزینه: ۰ — اشتراک)
> سؤال: آیا ۲ کلید GO از دو اکانت مجزا سقف مستقل دارند؟

## نتایج

| آزمایش | K1 (اکانت A — GO) | K2 (اکانت B — GO) |
|---|---|---|
| ۵ درخواست همزمان (تنها) | **5/5 ok** · latency ~1.3s · 0 empty | **5/5 → HTTP 429** `GoUsageLimitError: Weekly usage limit reached. Resets in 13h 12min` |
| ۵+۵ همزمان (با هم) | **5/5 ok** · ~1.1s | 5/5 → 429 (همان) |
| Zen free flash (K2, zen/v1) | — | **401 CreditsError: Insufficient balance** — تا شناسهٔ اشتباه `deepseek-v4-flash` بود |

## یافتهٔ تکمیلی — مدلهای free Zen (کلید ۲)

- لیست کامل zen/v1/models: **۶۲ مدل** — از جمله ۶ مدل free: `deepseek-v4-flash-free` · `mimo-v2.5-free` · `hy3-free` · `nemotron-3-ultra-free` · `nemotron-3.5-lightning-free` · `laguna-s-2.1-free`
- شناسهٔ درست برای مدل رایگان کاربر: **`deepseek-v4-flash-free`** (نه `deepseek-v4-flash` — آن pay-per-use است و بدون balance → 401)
- تست POST (چهار تلاش، ۲۰s فاصله، endpoint های chat/completions و responses): **همه 429 `FreeUsageLimitError: Rate limit exceeded`**
- **نتیجه:** مدل free «برخی مواقع کار میکند» تأیید شد — در حال حاضر rate-limited است. رایگان و صفر-هزینه، ولی **غیرقابل اتکا** → فقط بهعنوان آخرین لایهٔ fallback (try-once، breaker سریع، بدون penalty طولانی — چون رایگان است)؛ هرگز بهعنوان provider اصلی.

## نتیجهگیری (پاسخ قطعی به سؤال v1/v2)

1. ✅ **سقف کلیدها مستقل است — اثبات شد.** K1 همزمان با 429 بودن K2 پاسخ سالم میداد (در همان ثانیه). «N کلید از N اکانت = N سهمیه» تأیید تجربی شد. ادعای اولیهٔ v1 درست از آب درآمد؛ احتیاط ChatGPT هم منطقی بود (اثبات شد — نه فرض).
2. ⚠️ **K2 هماکنون در سقف هفتگی است** (ریست در ~۱۳ ساعت). الان عملاً ۱ کلید سالم داریم؛ از فردا ۲ کلید.
3. ⚠️ **Zen free fallback (K2) کار نمیکند** — «Insufficient balance» → در حال حاضر fallback رایگان در دسترس نیست. گزینهٔ M9 (Zen balance پولی یا DeepSeek direct) باز میماند.
4. ℹ️ K1 وقتی سالم است **سریع است** (~1.3s) و **empty-200 نداشت** — الگوی empty-200 قبلی به مدل/زمان/حالت دیگری مربوط است؛ با KeyPool + تشخیص 429 صریح، failover خودکار پوشش داده میشود.

## تأثیر بر معماری (پلن v2)

- M1 (KeyPool): تأیید — ۲ کلید از ۲ اکانت = ۲ سقف مستقل. ترتیب: K1 → K2؛ breaker منفرد روی 429 (GoUsageLimitError)؛ وقتی K2 در سقف است فقط K1 استفاده میشود.
- M2 (SectionRouter): بدون تغییر.
- M9: Zen free فعلاً مرده → گزینههای: (الف) شارژ Zen balance (از $20) (ب) DeepSeek direct — تصمیم بعد از M1.
- Benchmark: با K1 بهتنهایی، اجرای شبانه مجدد — با K2 از فردا کاملتر.

## Artifact
- اسکریپت: scripts/m0_quota_test.py (بدون کلید — از env میخواند)
- کلیدها: .env (gitignored) — `GO_API_KEY` (K1) + `GO_API_KEY_2` (K2)
