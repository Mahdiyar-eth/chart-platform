# بعد: امنیت

پاسخ مدل: go/deepseek-v4-pro

## تحلیل امنیت چارت تولد — بر اساس OVERVIEW و `app/main.py`

### پیش‌فرض و محدودیت‌ها
فایل `app/main.py` را بررسی کردم؛ اما کد `app/auth.py`، `app/security.py`، `app/report/renderer.py`، `app/payment/orders.py` و `app/bots/state.py` در اختیارم نیست.  
بنابراین مواردی که به این ماژول‌ها وابسته است، «نامشخص» اعلام می‌شود. در ارجاع‌ها به نام تابع/مسیر در `app/main.py` اشاره می‌کنم؛ چون کد پیوست شماره‌خط ندارد، آدرس دقیق خط ممکن نیست.

---

## 🔴 P0 — بحرانی / باید فوراً اصلاح شود

### ۱) فقدان کنترل دسترسی شیء‌محور روی دانلود گزارش، DOCX و صوت
**مسیرها:** `api_report_pdf`، `api_report_docx`، `api_report_audio` در `app/main.py`

**شواهد:**
```python
# در هر سه تابع:
paid = session.exec(
    select(Order).where(Order.chart_id == rep.chart_id, Order.status == "paid")
).first()
if not paid:
    raise HTTPException(403, ...)
```

این بررسی فقط وجود **یک سفارش پرداخت‌شده برای آن چارت** را چک می‌کند؛ در حالی که:
- نمی‌پرسد سفارش متعلق به کاربرِ درخواست‌دهنده است یا نه.
- هیچ احراز هویتی (`get_current_user`) یا مقایسه‌ی مالکیت انجام نمی‌شود.
- با دانستن `report_id` (و چون `chart_id` از `rep.chart_id` به‌دست می‌آید) هر فردی می‌تواند PDF/DOCX/MP3 را دریافت کند، **حتی بدون لاگین**، به شرطی که برای آن چارت حداقل یک سفارش paid وجود داشته باشد.

**ریسک:** افشای اطلاعات خصوصی تولد و تحلیل روان‌شناختی کاربران، نقض حریم شخصی و قرارداد فروش.

**پیشنهاد:**
- در این سه endpoint حتماً `request` بگیرید، کاربر را با `get_current_user` شناسایی کنید و بررسی کنید که کاربر، مالک چارت یا دارنده‌ی سفارش است.
- یا حداقل `order.user_id` را با کاربر فعلی مقایسه کنید.

---

### ۲) عدم idempotency در callback پرداخت زرین‌پال
**مسیر:** `api_payment_verify` در `app/main.py`

**شواهد:**
```python
if Status == "OK":
    client = ZarinpalClient()
    try:
        v = client.verify(Authority, order.amount_rial)
        order.status = "paid"
        ...
    except ZarinpalError:
        order.status = "failed"
        session.commit()
```

هیچ بررسی قبل از verify وجود ندارد که `order.status` اگر قبلاً `paid` یا `refunded` است، عملیات تکراری رد شود.  
اگر کاربر یا درگاه، callback را بیش از یک بار صدا بزند (refresh یا retry خودکار)، بسته به رفتار زرین‌پال ممکن است `verify` دوم خطا برگرداند و سفارشِ پرداخت‌شده به `failed` تغییر کند.

**ریسک:** از دست رفتن دسترسی کاربر به گزارش که پولش را پرداخت کرده؛ پشتیبانی و ریفاند بی‌دلیل؛ به‌هم‌ریختن داده‌های مالی.

**پیشنهاد:**
- قبل از verify:
  ```python
  if order.status in ("paid", "refunded"):
      return RedirectResponse(...)
  ```
- وضعیت‌ها را به‌صورت ماشین حالت `pending → paid / failed / refunded` مدیریت کنید.

---

### ۳) دسترسی گفت‌وگوی هوش مصنوعی (AI Chat) به هر سفارش paid، نه فقط پلن gold
**مسیرها:** `api_chat_access` و `api_chat` در `app/main.py`

**شواهد:**
```python
order = session.exec(
    select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
).first()
if not order:
    raise HTTPException(403, ...)
```

طبق OVERVIEW، چت فقط در پلن **gold** فعال است، اما این کد هر سفارش paid را مجاز می‌کند؛ یعنی خریدار basic، full، synastry یا monthly هم می‌تواند از چت استفاده کند.

**ریسک:** شکستن مدل درآمدی پلن gold، افزایش هزینه‌ی LLM، امکان سوءاستفاده برای مصرف سهمیه.

**پیشنهاد:**
- شرط را به `order.plan_key == "gold"` یا بررسی feature-based تغییر دهید.
- مقدار `order` را از روی `chart_id` و `user_id` فعلی دریافت کنید.

---

## 🟠 P1 — مهم / باید به‌زودی اصلاح شود

### ۴) احتمال SSRF و تزریق HTML از طریق خروجی LLM در رندر PDF
**مسیر مرتبط:** `app/main.py: api_create_report` → `worker.py` → `generator.py` → `renderer.py`

**شواهد:**
- `name` و `focus_areas` ورودی کاربر مستقیماً در `_compute_and_save_chart` ذخیره می‌شوند.
- طبق OVERVIEW، این داده‌ها وارد `prompt_builder` و سپس خروجی LLM در `renderer.py` می‌شود.
- خروجی LLM ممکن است شامل تگ‌های HTML مانند `<img src="http://127.0.0.1:8767/...">` یا `<link rel=...>` باشد.

**ریسک:**
- اگر `renderer.py` از WeasyPrint با تنظیم پیش‌فرض استفاده کند، ممکن است منابع خارجی را fetch کند و باعث SSRF شود.
- اگر Jinja2 autoescape در قالب گزارش خاموش باشد، خروجی LLM می‌تواند HTML/JS تزریق کند (هرچند در PDF اجرای JS نداریم، اما در DOCX/WebView ممکن است مشکل شود).

**وضعیت:** `renderer.py` در اختیار من نیست → «نامشخص» ولی به‌عنوان ریسک واقعی باید بررسی شود.

**پیشنهاد:**
- در `renderer.py` از `url_fetcher` سفارشی برای WeasyPrint استفاده کنید و اجازه‌ی دسترسی به localhost/شبکه داخلی را ندهید.
- خروجی LLM را قبل از رندر HTML-escape و sanitize کنید (مگر تگ‌های مجاز محدود).
- طول `name` و `focus_areas` را محدود کنید (مثلاً ۱۰۰ کاراکتر).

---

### ۵) نبود محدودیت نرخ روی عملیات‌های پرهزینه
**مسیرها:** `api_rectify`، `api_chat`، `api_synastry`، `api_synastry/full`، `api_share/{chart_id}.png`، `api_report_audio`

**شواهد:**
- در `main.py` هیچ تزئین‌کننده‌ی rate limit برای این endpointها دیده نمی‌شود.
- `api_rectify` حلقه‌ی محاسباتی سنگینی دارد (تست زمان‌های مختلف).
- `api_chat` مستقیماً LLM (گوگل فری/دیپ‌سیک) را صدا می‌زند.
- `api_report_audio` در هر فراخوانی، فایل MP3 را با edge_tts تولید می‌کند و روی دیسک می‌نویسد.

**ریسک:** امکان DoS و افزایش هزینه‌ی سرویس توسط کاربر مجاز یا نیمه‌مجاز.

**پیشنهاد:**
- Rate limit برای هر endpoint (مثلاً ۲۰ درخواست در هر ۱۰ دقیقه).
- برای TTS، کش کردن نتیجه و محدودیت سقف طول متن.
- برای rectify، محدودیت ورودی رویدادها و سقف تعداد اجرا.

---

### ۶) CSP با `unsafe-inline/eval`
**مدرک:** OVERVIEW بخش امنیت: `unsafe-inline/eval` برای Alpine.js.

**ریسک:** اگر هرگونه XSS ذخیره‌ای یا بازتابی وجود داشته باشد، CSP نمی‌تواند جلوی اجرای آن را بگیرد؛ عملاً لایه‌ی دفاعی CSP خنثی است.

**پیشنهاد:**
- بررسی امکان استفاده از Alpine با `nonce` یا `hash` و حذف `unsafe-eval`.
- تا زمانی که `unsafe-eval` لازم است، ورودی‌های کاربر را در هر قالبی با autoescape سخت‌گیرانه کنترل کنید.

---

### ۷) دریافت webhook بله بدون احراز هویت
**مسیر:** `api_v1_bale_webhook` در `app/main.py`

**شواهد:**
```python
@app.post("/api/v1/bale/webhook")
async def bale_webhook(request: Request):
    # Bale has no secret_token support (v140 pitfall) — accept updates directly
    update = await request.json()
    await handle_update(update, "bale")
```

هیچ secret، امضا یا محدودیت IP وجود ندارد.  
هر کسی می‌تواند update جعلی بفرستد و `handle_update` را اجرا کند.

**ریسک:** ارسال فرمان‌های جعلی به ربات، تحریک کاربران، مصرف منابع، DoS روی صف.

**پیشنهاد:**
- برای بله حداقل یک هدر سفارشی (`X-Bot-Token`) یا محدودیت IP سرویس بله را بررسی کنید.
- اگر پشتیبانی نمی‌کند، از طریق توکن در URL (با ولیدیشن) یا پروکسی معکوس فیلتر کنید.

---

### ۸) ورود کاربر به پرامپت‌ها — prompt injection
**مسیر:** `_compute_and_save_chart` و `api_create_chart`

**شواهد:**
```python
name: str = Form(""),
focus_areas: str | None = Form(None),
...
focus_areas=[a.strip() for a in (focus_areas or "").split(",") if a.strip()],
```

این مقادیر بدون محدودیت طول یا نرمال‌سازی سخت‌گیرانه ذخیره می‌شوند و طبق OVERVIEW به پرامپت LLM می‌روند.

**ریسک:** کاربر می‌تواند با `name="... <دستور تزریقی> ..."` خروجی گزارش را دستکاری کند؛ از تبلیغات پنهان تا دریافت اطلاعات سیستم (در صورت SSRF).

**پیشنهاد:**
- اعتبارسنجی طول: `name` حداکثر ۸۰ کاراکتر، `focus_areas` حداکثر ۵۰ کاراکتر.
- هر ورودی متنی قبل از ارسال به پرامپت، از کاراکترهای کنترل و دستورالعمل‌های LLM پاک‌سازی شود.

---

### ۹) احراز هویت ادمین و OTP — نامشخص در کد ارائه‌شده
**مدرک:** در `main.py` فقط `_is_admin(request)` صدا زده شده؛ پیاده‌سازی آن در `app/auth.py` یا `app/security.py` است.

**ریسک بالقوه:** اگر `_is_admin` فقط یک PIN ساده در کوکی باشد، قابل حدس یا جعل است.  
OTP هم اگر rate limit واقعی نداشته باشد، brute-force می‌شود.

**پیشنهاد:**
- `app/auth.py` را برای نرخ‌محدودیت واقعی OTP (مثلاً ۵ تلاش در ۱۵ دقیقه) بازبینی کنید.
- `_is_admin` باید از کوکی امضاشده HttpOnly با طول عمر کوتاه و گره‌خورده به `session_id` استفاده کند.
- در روت‌های ادمین CSRF هم بررسی شود.

---

## 🟡 P2 — بهبود

### ۱۰) webhook تلگرام — secret اختیاری
در `telegram_webhook` اگر `TELEGRAM_WEBHOOK_SECRET` در env نباشد، هیچ احرازی انجام نمی‌شود.  
**پیشنهاد:** در محیط production، مقدار secret را اجباری کنید.

### ۱۱) مسیرهای فایل در `/tmp` قابل پیش‌بینی
`api_report_audio` فایل `/tmp/report-audio-{report_id[:8]}.mp3` را می‌سازد.  
اگر کاربری روی سرور (محلی/سرویس دیگر) بتواند symlink بسازد، امکان overwrite فایل دلخواه وجود دارد.  
**پیشنهاد:** از پوشه‌ی اختصاصی با permission مناسب و فایل با نام کامل UUID تصادفی استفاده کنید.

### ۱۲) نبود هندلینگ خطا برای تاریخ نامعتبر در synastry
`api_synastry` مستقیماً `compute_from_fields` را صدا می‌زند؛ ورودی `month=99` احتمالاً `ValueError` تولید می‌کند که به 500 تبدیل می‌شود.  
**پیشنهاد:** اعتبارسنجی بازه‌ی ماه/روز مشابه `_compute_and_save_chart`.

### ۱۳) callback پرداخت با GET و ثبت در history
`api_payment_verify` از GET استفاده می‌کند و پارامترهای `Authority` و `Status` در URL هستند.  
**ریسک کم:** ثبت در تاریخچه مرورگر، log پروکسی.  
**پیشنهاد:** طبق استاندارد زرین‌پال callback را GET می‌فرستد؛ می‌توان پس از verify بلافاصله redirect داد و از ذخیره‌ی URL طولانی جلوگیری نکرد.

### ۱۴) `api_charts/{chart_id}/report` ممکن است با سفارش synastry اشتباه شود
بررسی `select(Order).where(Order.chart_id == chart_id, Order.status == "paid")` در `api_create_report` ممکن است سفارش synastry با `chart_id` را به‌عنوان سفارش گزارش بپذیرد و `plan_key` اشتباه به کار ببرد.  
**پیشنهاد:** شرط `Order.plan_key in REPORT_PLANS` را اضافه کنید.

---

## جمع‌بندی این بُعد

وضعیت امنیتی محصول در لایه‌ی زیرساخت (CSP، سشن HttpOnly، ORM) نقاط مثبتی دارد، اما **کنترل دسترسی در سطح داده‌ها (object-level authorization) و منطق تجاری پلن‌ها** جدی‌ترین ضعف است.  
سه مشکل P0 (دانلود بدون مالکیت، عدم idempotency پرداخت، چت رایگان برای همه پلن‌ها) مستقیماً روی درآمد، اعتماد کاربر و حریم خصوصی اثر می‌گذارند و باید قبل از هر توسعه‌ی جدید برطرف شوند.  
پس از آن، رسیدگی به SSRF احتمالی در رندر PDF، نرخ محدودیت و webhook بله در اولویت بعدی است.  
توصیه می‌کنم یک بازبینی متمرکز روی `app/auth.py`، `app/security.py` و `app/report/renderer.py` انجام شود، چون بخش مهمی از سطح حمله آنجاست و کد آن در اختیار این تحلیل نبود.
