# وب‌اپ — گزارش این دور

بازطراحی به‌صورت وب‌اپ + درست‌کردن منطق‌ها + حافظهٔ گفت‌وگو.
شاخه: `claude/hermes-project-review-plan-kaziw5`

## دربارهٔ Sleek — صادقانه

راه‌اندازی نشد. `sleek.design` از این محیط پشت پروکسی بسته است (`curl` = `000`،
هم `/agents.md` هم `/api/v1/device/start`). مسئلهٔ کلید یا اشتراک نیست. طبق
انتخاب خودت، طراحی را خودم انجام دادم با زبان iOS / Human Interface.

## آنچه واقعاً شکسته بود

هر مورد با **اجرا** تأیید شده، نه از روی خواندن کد.

| # | مشکل | چطور ثابت شد |
|---|---|---|
| 1 | `account.html` تمپلیت شکسته — ۳۵ خط جاوااسکریپت به‌صورت **متن خام** روی صفحه؛ `dashSearch()` و `wallet()` مرده | `grep -c '<script'` = **0** در برابر `'</script>'` = **1** |
| 2 | Service Worker **هرگز نصب نمی‌شد** — کل PWA کد مرده بود | `sw.js` فایلی precache می‌کرد که وجود نداشت؛ `addAll` اتمیک است. حالا در مرورگر `active:activated` + هر ۴ فایل shell کش شده |
| 3 | خرید گزارش، **گزارش تولید نمی‌کرد** | `POST /api/charts/{id}/report` فقط یک caller داشت که تنها در حالت failed/stalled mount می‌شد |
| 4 | «تلاش دوباره» **جاب و هزینهٔ LLM را دوبرابر** می‌کرد | worker می‌نویسد `running`، API چک می‌کرد `processing` |
| 5 | پک `chat_pack_20` **هرگز مصرف نمی‌شد** | `ent_consume` فقط در `/api/chat` بود؛ UI فقط به `/api/chat/stream` پست می‌کند |
| 6 | چارت مهمان **هرگز claim نمی‌شد** | کوکی `chart_access` وقتی `httpOnly` است، از JS خواندنی نیست — پس `cap` هرگز فرستاده نمی‌شد |
| 7 | `next=` را همه می‌فرستادند و **هیچ‌کس نمی‌خواند** | `account_login.html` مقصد `/account` را hardcode کرده بود |
| 8 | **۲۲ آیکون ناوبری** ۰×۰ رندر می‌شدند | `<use href="#icon-x">` در برابر sprite خارجی |
| 9 | `icon-grid` و `icon-star` **اصلاً در sprite نبودند** — FAB «چارت من» دایرهٔ طلایی خالی | اندازه‌گیری در مرورگر |
| 10 | ۷ دکمهٔ «سؤال پیشنهادی» چت **خطا می‌دادند** | `\|tojson` داخل attribute دابل‌کوت، attribute را زودتر می‌بست |
| 11 | فونت‌ها TTF با پسوند `.woff2` — دانلود دوباره | `file` روی هر ۴ جفت |
| 12 | پروگرس‌بار گزارش **دروغ** بود | `rep.sections` فقط یک‌بار، بعد از پایان همه‌چیز نوشته می‌شد |
| 13 | تیتر H1 و H2 صفحهٔ `/plans` **نامرئی** در تم تیره | کنتراست ۱.۰۷ (نیاز: ۳.۰) |
| 14 | چیپ اعتبار در تم روشن نامرئی | طلایی تیره روی navy = ۱.۸۳ |
| 15 | `solar_return_for` هر بار **۴ برابر** محاسبه می‌کرد | شمارش کال: `assert 4 == 2` |
| 16 | relocation از کاربر **عرض و طول دستی** می‌خواست | بعد از خرج ۶ اعتبار |
| 17 | خطاهای solar هرگز رندر نمی‌شدند → اسکلتون بی‌نهایت | `err` ست می‌شد و هیچ‌جا نمایش داده نمی‌شد |
| 18 | چت **هیچ حافظه‌ای نداشت** | `chat_answer`/`chat_stream` پارامتر history نداشتند |
| 19 | حباب کاربر و دستیار **یکسان** بودند | یک ternary جاوااسکریپت داخل CSS نشسته بود |
| 20 | ۱۹ صفحه **عنوان اختصاصی نداشتند** | با ناوبری کلاینتی، عنوان تب هر بار عوض می‌شود |

## آنچه ساخته شد

- **پوستهٔ اپ**: `hx-boost` + View Transitions (htmx از قبل لود می‌شد و صفر استفاده داشت — ۴۸KB وزن مرده)، tab bar، نوار پیشرفت ناوبری، `aria-busy`، بنر نصب، حالت standalone، `viewport-fit=cover`.
- **پروگرس واقعی**: worker بعد از هر بخش به‌صورت اتمیک (jsonb) پیش‌رفت را می‌نویسد؛ مخرج از سرور می‌آید (نه ۱۳ ثابت که برای پلن basic غلط بود)؛ deadline از ۴ دقیقه به ۳۰ دقیقه (هم‌تراز با worker)؛ اسکلتون + شمارندهٔ ثانیه در پیش‌نمایش و solar؛ busy flag روی خریدها.
- **حافظهٔ چت**: آخرین ۶ نوبت از `ChatMessage` (که از قبل همه‌چیز را ذخیره می‌کرد) داخل `<گفت‌وگوی_قبلی>` با مرز اعتماد صریح + خلاصهٔ چارت. سقف توکن با پنجرهٔ کشویی.
- **مسیر محصول**: خرید → خودِ محصول (نه `/account`)؛ ورود → همان‌جا که بودی؛ چارت مهمان claim می‌شود؛ solar/relocation از صفحهٔ چارت دیده می‌شوند؛ انتخاب شهر مقصد از `/api/cities`.

## اثبات (اجرا شده، نه ادعا)

```
pytest                      1355 passed, 13 skipped
bash scripts/ci.sh          CI OK   (coverage 82%، ruff، bandit، pip-audit،
                                     secret scan، brand gate، alembic drift)
scripts/verify/app_shell.py      17/17   (SW = active:activated)
scripts/verify/guest_journey.py  22/22   (مهمان → چارت → ورود → claim)
scripts/verify/contrast.py       0 failure در ۶ صفحه، هر دو تم
scripts/verify/page_sweep.py     23/23 صفحه بدون خطا
```

## گیت‌های جدید (تا این‌ها دوباره برنگردند)

`test_template_integrity` (توازن script/block) · `test_sw` (فایل‌های shell روی
دیسک) · `test_icon_sprite` (هر آیکون ارجاع‌شده وجود دارد) · `test_typography`
(سقف leading + تداخل property بین شیت‌ها) · `test_report_progress` ·
`test_chat_memory` · `test_chat_ui` · `test_purchase_delivers` ·
`test_login_next_and_claim` · `test_report_status_vocab` ·
`test_chat_stream_parity` · `test_font_assets` · `test_solar_cost` ·
`test_purchase_ui_feedback` · `test_chart_page_links` · `test_app_shell`

## تصمیم باز — RAG

خط لولهٔ pgvector کامل، migrate شده و HNSW-index دارد، ولی
`sentence-transformers` در `requirements.txt` نیست، پس تا امروز **صفر chunk**
نوشته شده. torch را به‌ابتکار خودم اضافه نکردم؛ `/readiness` حالا وضعیت را
راست می‌گوید. حافظهٔ گفت‌وگو و چارت بدون آن کار می‌کند.

## کاری که فقط از تو برمی‌آید

کلید `sk-9vsR...` که در چت فرستادی هنوز افشاشده است. هرگز کامیت نشد، ولی
پاک‌کردن پیام کافی نیست — **باید rotate‌اش کنی.**
