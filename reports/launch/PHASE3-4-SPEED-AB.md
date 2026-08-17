# ⚡ فاز ۳+۴ — سرعت worker، گیت M3 و A/B reasoning (۲۰۲۶-۰۸-۱۷ ~۲۰:۳۰)

## کشف حیاتی P4 (audit — ریشهٔ اصلی سرعت پایین)
worker در startup یک router مشترک میساخت (`build_router()` → deepseek-v4-pro) و آن را به
`generate_sections_async(router=ctx["router"])` پاس میداد؛ `_gen_one` هم قانون
«router ارسالی برنده است» داشت → **تمام سکشنهای گزارش در تولید، همیشه روی deepseek-v4-pro
اجرا میشدند و مسیریابی per-section (M2) عملاً هرگز اجرا نمیشد.**
یعنی کلید «مدل per-domain را عوض کن» در پنل ادمین از ابتدای طراحی بیاثر بود.
فیکس (audit P4): worker دیگر router تزریق نمیکند (`router=None`) — سکشنها از
`section_model(domain)` استفاده میکنند. ۳ تست به قرارداد جدید تطبیق یافت (539 passed).

## تست سرعت واقعی (همان pipeline production، ۲ چارت)
| | deepseek-v4-pro (قبل) | gemini-3.6-flash-high (بعد) |
|---|---|---|
| per-section p50/p95 | 43-59s | **4-17s** |
| کل ۱۴ سکشن طلا (همزمان) | ~195s | **~60s** |
| هزینه/گزارش | ~$0.01 (GO flat) | **$0.27** |
| QA fails | 0 | 0 |
| رفتن به fallback | — | 0 |

## E2E کامل زنده (HTTP→ARQ→RAG→R2) — گزارش 6e93c295 ✅
- POST /api/charts/{id}/report → queues → worker → sections روی omni/gemini
- 14/14 سکشن طلا OK (کانون: basic=5، full=13، gold=14)، ۲ ریترای QA (با بازخورد دلیل، موفق)، صفر fallback
- PDF ساخته شد + آپلود R2 (`chart-reports/...pdf`) + **40 چانک RAG ایندکس شد**
- هزینهٔ کل گزارش: **$0.27** | وضعیت نهایی: done

## باگهای پیدا شده و رفعشده در E2E
1. **HF مدل E5 در worker دانلود میشد و دانلود stall میکرد** (گزارش را ۳۰+ دقیقه
   نگه میداشت) → `asyncio.wait_for(..., 120)` + کش پایدار `HF_HOME` + حالت آفلاین
2. **کش HF ساختهشده با root توسط worker (zayche) خوانده نمیشد** (Permission denied
   → RAG بیصدا skip) → `chown -R zayche` + هشدار در لاگ
3. **خطای ابعاد embedding در بنچمارک RAG** بیصدا بلعیده میشد (e5-large=1024 بُعد
   علیه ستون 384) → رانر v2 (جدول موقت per-model + نمایان کردن stderr) — ۵۰۰ کوئری × ۲

## A/B reasoning (۲۰ چارت × ۲ حالت، پرامپت v2 — همان مدل deepseek-v4-pro)
| معیار (روبریک benchmark) | thinking ON | thinking OFF |
|---|---|---|
| personalization | **5.9** | 1.95 |
| coherence | **6.35** | 5.7 |
| contradiction | **6.95** | 2.95 |
| persian | 8.75 | 8.5 |
| p50 latency | 21.0s | 8.6s |
| tokens خروجی | 20.1k | 6.3k |

یافته: thinking منطق شخصیسازی را ۳× بالا میبرد ولی ۲.۴× کندتر و ۳.۲× توکن بیشتر.
**تصمیم:** چت/پیشنمایش/گزارش = gemini-3.6-flash-high (سرعت + سلامت واقعیت 10/10)؛
برای کیفیت حداکثری در آینده: تغییر env یکخطی به pro+thinking (ولتج از build_router).

## گیت M3 (پنجرهٔ 24h پس از ورود اجراهای جدید gemini)
- fail%: 0.8% ✅ (آستانه 25%) | retry%: 24% ✅ (آستانه 30%)
- p95: 59.5s ❌ → با خروج اجراهای قدیمی pro (تا ~۱۹:۰۰ فردا) و ورود gemini (~10s)
  بهزودی زیر 40s میرسد؛ اندازهگیری دوباره در 05:30 با کرون سابق + دستی فردا عصر.