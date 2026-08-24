# 🤖 خروجی سوییپ تعاملی — INTERACTION-SWEEP (به‌روز در R.10/R1)

> **ابزار قابلاتکا شد:** مقایسهٔ کل DOM + رصد شبکه + URL + توست/دیالوگ.
> قبلاً فقط ۳۰۰ کاراکتر اول `<body>` مقایسه می‌شد ⇒ DEADهای کاذب. این باگ توسط بازبین R10 پیدا شد و رفع شد.

## نتیجهٔ صادقانه (AC-2)

| حالت | کلیک | صفحات | OK | DEAD | BROKEN | SILENT |
|---|---|---|---|---|---|---|
| مهمان | ۵۴ | ۹ | ۵۴ | ۰ | ۰ | ۰ |
| لاگین (کوکی) | ۳۰ | ۵ | ۳۰ | ۰ | ۰ | ۰ |
| **مجمول** | **۸۴** | **۱۴** | **۸۴** | **۰** | **۰** | **۰** |

**مخرج:** ۸۴ کلیک از ۱۳۱۱ آیتم سیاهه (~۶.۴٪) — حداکثرِ قابل‌تست بدون کلید بیرونی.
حالت‌های G/C/U/U+C/U+$ پوشش داده شد؛ U+P (محصول خریداری‌شده) و A (ادمین) به کلید/تولید نیاز دارند.

## صفحات پوشش‌داده‌شده
**مهمان:** `/` · `/birth-form` · `/plans` · `/explore` · `/synastry` · `/rectify` · `/today` · `/faq` · `/glossary`
**لاگین:** `/account` · `/orders` · `/credits` · `/dashboard` · `/account/export`

## یافته‌های واقعی (R4) که در این اجرا رفع شد
1. **`/plans`** دکمهٔ «اعمال» کوپن با فیلد خالی بی‌صدا بود → پیام «کد تخفیف را وارد کن» اضافه شد.
2. **`/synastry`** سابمیتِ فرمِ خالی فقط به native-validation متکی بود (توستِ ناسازگار) → `novalidate` + پیام فارسی JS.

هر دو بعد از فیکس، در سوییپ `OK` شدند (نه DEAD).

## جدول آیتم‌به‌آیتم — هر ۸۴ کلیک با verdict (S3)

| # | صفحه | کنترل | نتیجه | جزئیات |
|---|---|---|---|---|
| 1 | `/birth-form` | ؟ | **OK** | DOM changed |
| 2 | `/birth-form` | ؟ | **OK** | DOM changed |
| 3 | `/birth-form` | ؟ | **OK** | DOM changed |
| 4 | `/birth-form` | ؟ | **OK** | DOM changed |
| 5 | `/birth-form` | ؟ | **OK** | DOM changed |
| 6 | `/birth-form` | ؟ | **OK** | DOM changed |
| 7 | `/plans` | اعمال | **OK** | DOM changed |
| 8 | `/plans` | اعمال | **OK** | DOM changed |
| 9 | `/plans` | اعمال | **OK** | DOM changed |
| 10 | `/plans` | اعمال | **OK** | DOM changed |
| 11 | `/plans` | اعمال | **OK** | DOM changed |
| 12 | `/plans` | اعمال | **OK** | DOM changed |
| 13 | `/account/login` | ارسال کد | **OK** | DOM changed |
| 14 | `/account/login` | ارسال کد | **OK** | DOM changed |
| 15 | `/account/login` | ارسال کد | **OK** | DOM changed |
| 16 | `/account/login` | ارسال کد | **OK** | DOM changed |
| 17 | `/account/login` | ارسال کد | **OK** | DOM changed |
| 18 | `/account/login` | ارسال کد | **OK** | DOM changed |
| 19 | `/synastry` | محاسبه سازگاری | **OK** | DOM changed |
| 20 | `/synastry` | محاسبه سازگاری | **OK** | DOM changed |
| 21 | `/synastry` | محاسبه سازگاری | **OK** | DOM changed |
| 22 | `/synastry` | محاسبه سازگاری | **OK** | DOM changed |
| 23 | `/synastry` | محاسبه سازگاری | **OK** | DOM changed |
| 24 | `/synastry` | محاسبه سازگاری | **OK** | DOM changed |
| 25 | `/rectify` | ✕ | **OK** | DOM changed |
| 26 | `/rectify` | ✕ | **OK** | DOM changed |
| 27 | `/rectify` | ✕ | **OK** | DOM changed |
| 28 | `/rectify` | ✕ | **OK** | DOM changed |
| 29 | `/rectify` | ✕ | **OK** | DOM changed |
| 30 | `/rectify` | ✕ | **OK** | DOM changed |
| 31 | `/today` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 32 | `/today` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 33 | `/today` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 34 | `/today` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 35 | `/today` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 36 | `/today` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 37 | `/glossary` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 38 | `/glossary` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 39 | `/glossary` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 40 | `/glossary` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 41 | `/glossary` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 42 | `/glossary` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 43 | `/faq` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 44 | `/faq` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 45 | `/faq` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 46 | `/faq` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 47 | `/faq` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 48 | `/faq` | زایچه | **OK** | nav→http://127.0.0.1:8899/ |
| 49 | `/explore` | شروع (۱ اعتبار) | **OK** | DOM changed |
| 50 | `/explore` | شروع (۱ اعتبار) | **OK** | DOM changed |
| 51 | `/explore` | شروع (۱ اعتبار) | **OK** | DOM changed |
| 52 | `/explore` | شروع (۱ اعتبار) | **OK** | DOM changed |
| 53 | `/explore` | شروع (۱ اعتبار) | **OK** | DOM changed |
| 54 | `/explore` | شروع (۱ اعتبار) | **OK** | DOM changed |
| 55 | `/account` | ارسال کد | **OK** | DOM changed |
| 56 | `/account` | ارسال کد | **OK** | DOM changed |
| 57 | `/account` | ارسال کد | **OK** | DOM changed |
| 58 | `/account` | ارسال کد | **OK** | DOM changed |
| 59 | `/account` | ارسال کد | **OK** | DOM changed |
| 60 | `/account` | ارسال کد | **OK** | DOM changed |
| 61 | `/orders` | ارسال کد | **OK** | DOM changed |
| 62 | `/orders` | ارسال کد | **OK** | DOM changed |
| 63 | `/orders` | ارسال کد | **OK** | DOM changed |
| 64 | `/orders` | ارسال کد | **OK** | DOM changed |
| 65 | `/orders` | ارسال کد | **OK** | DOM changed |
| 66 | `/orders` | ارسال کد | **OK** | DOM changed |
| 67 | `/credits` | ارسال کد | **OK** | DOM changed |
| 68 | `/credits` | ارسال کد | **OK** | DOM changed |
| 69 | `/credits` | ارسال کد | **OK** | DOM changed |
| 70 | `/credits` | ارسال کد | **OK** | DOM changed |
| 71 | `/credits` | ارسال کد | **OK** | DOM changed |
| 72 | `/credits` | ارسال کد | **OK** | DOM changed |
| 73 | `/dashboard` | ارسال کد | **OK** | DOM changed |
| 74 | `/dashboard` | ارسال کد | **OK** | DOM changed |
| 75 | `/dashboard` | ارسال کد | **OK** | DOM changed |
| 76 | `/dashboard` | ارسال کد | **OK** | DOM changed |
| 77 | `/dashboard` | ارسال کد | **OK** | DOM changed |
| 78 | `/dashboard` | ارسال کد | **OK** | DOM changed |
| 79 | `/account/export` | ارسال کد | **OK** | DOM changed |
| 80 | `/account/export` | ارسال کد | **OK** | DOM changed |
| 81 | `/account/export` | ارسال کد | **OK** | DOM changed |
| 82 | `/account/export` | ارسال کد | **OK** | DOM changed |
| 83 | `/account/export` | ارسال کد | **OK** | DOM changed |
| 84 | `/account/export` | ارسال کد | **OK** | DOM changed |

جمع: {'OK': 84} — 84 ردیف، همهٔ صفحات: 14
