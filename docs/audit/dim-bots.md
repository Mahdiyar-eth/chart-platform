# بعد: ربات‌های تلگرام/بله

پاسخ مدل: go/deepseek-v4-pro

## تحلیل ربات‌های تلگرام/بله (بر اساس کد موجود)

**محدودیت تحلیل:** فایل کامل `app/bots/handler.py` و `app/bots/state.py` در اختیار من نیست؛ بنابراین تحلیل دقیقِ منطق داخلی button-driven ،callback ،state و نحوه‌ی جداسازی callback با `_` ممکن نیست. اما بخش‌های وب‌هوک، مسیرهای فراخوانی و تعامل با سرور در `app/main.py` به‌وضوح دیده می‌شود و مبنای این تحلیل است.

---

### ۱) وضعیت فعلیِ نقاط ورود ربات‌ها در `main.py`

**تلگرام:**
```python
@app.post("/api/v1/telegram/webhook")
async def telegram_webhook(request: Request):
    if TELEGRAM_WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(403, "bad secret")
    update = await request.json()
    await handle_update(update, "telegram")
    return {"ok": True}
```

**بله:**
```python
@app.post("/api/v1/bale/webhook")
async def bale_webhook(request: Request):
    # Bale has no secret_token support (v140 pitfall) — accept updates directly
    update = await request.json()
    await handle_update(update, "bale")
    return {"ok": True}
```

مشاهدات کلیدی:

- **تلگرام:** فقط در صورتی که `TELEGRAM_WEBHOOK_SECRET` در `.env` مقدار داشته باشد، هدر `X-Telegram-Bot-Api-Secret-Token` بررسی می‌شود. اگر این متغیر تنظیم نشده باشد، شرط `if TELEGRAM_WEBHOOK_SECRET:` نادیده گرفته می‌شود و **هر درخواست بدون هیچ احرازی پذیرفته می‌شود**. این یک شکاف امنیتی جدی در استقرار production است.
- **بله:** کاملاً بدون احراز هویت و بدون هیچ sanity check اولیه. کامنت صریحاً می‌گوید «Bale has no secret_token support» و همه‌ی update ها مستقیم پذیرفته می‌شوند. این یعنی هر شخصی که آدرس وب‌هوک را بداند (و در اینترنت قابل دسترسی است)، می‌تواند درخواست‌های دلخواه به `handle_update` بفرستد.
- هر دو endpoint بعد از `await handle_update(...)` خروجی `{"ok": True}` برمی‌گردانند، اما اگر `handle_update` exception پرتاب کند، FastAPI به‌طور پیش‌فرض پاسخ 500 می‌دهد. تلگرام روی خطای 5xx و network errors به‌صورت تصاعدی retry می‌کند، که می‌تواند به پردازش تکراری و رفتارهای ناخواسته منجر شود.
- `handle_update` در بدنه‌ی async route با `await` صدا زده شده؛ بنابراین باید از نوع async باشد. اگر در داخل آن از `Session(engine)` به‌صورت همگام (blocking) استفاده شود، event loop در FastAPI قفل می‌شود. از کد موجود قابل تشخیص نیست؛ باید در `handler.py` بررسی شود.

---

### ۲) خطاهای احتمالی و سطح اولویت

| اولویت | مشکل | توضیح / ارجاع | راه‌حل پیشنهادی |
|--------|------|---------------|-----------------|
| **P0** | **بله وب‌هوک بدون هیچ احرازی** | `main.py` ، تابع `bale_webhook` — کامنت صریح + عدم وجود secret/ip check | حداقل یک secret در URL یا body اضافه شود؛ یا nginx فقط رنج IP رسمی بله را allow کند؛ یا HMAC امضا شود. بدون این، هر کسی می‌تواند state بوت را به‌هم بریزد، سفارش/پرداخت جعلی بسازد یا DoS ایجاد کند. |
| **P0** | **تلگرام در صورت عدم تنظیم `TELEGRAM_WEBHOOK_SECRET` بدون احراز می‌ماند** | `main.py` ، تابع `telegram_webhook` — شرط `if TELEGRAM_WEBHOOK_SECRET:` و عدم وجود else | در production این متغیر باید **اجباری** باشد. در `lifespan` یا startup چک شود که در حالت production مقدار دارد؛ در غیر این صورت fail-fast شود. همچنین همیشه برای همه‌ی درخواست‌های رسیده هدر secret اجباری باشد. |
| **P1** | **نبود try/except حول `handle_update`** | `main.py` ، هر دو endpoint | هر خطای غیرمنتظره (DB, LLM, pyswisseph, JSON) منجر به 500 و retry بی‌پایان تلگرام می‌شود. یک wrapper امن اضافه کنید که exception را log کند و پاسخ 200 برگرداند تا از retry جلوگیری شود، مگر خطای بحرانی که باید به‌طور صریح handle شود. |
| **P1** | **عدم validation و sanity check اولیه روی update** | `main.py` ، `bale_webhook` و `telegram_webhook` | هر JSON خالی یا مخرب می‌تواند در `handle_update` خطای `KeyError`/`ValidationError` بدهد. قبل از فراخوانی، ساختار اصلی update (وجود `update_id`, `message` یا `callback_query`) بررسی شود. به‌ویژه برای بله که هیچ احرازی ندارد ضروری است. |
| **P1** | **عدم rate limit اختصاصی برای bot endpoints** | `main.py` (مشاهده نمی‌شود که middleware چگونه عمل می‌کند) | `security_guard` ممکن است برخی محدودیت‌ها را اعمال کند (نامشخص). باید برای bot endpoints جداگانه rate limit سخت‌گیرانه و همچنین محافظت در برابر تلگرام/بله‌های جعلی داشته باشیم. |
| **P2** | **احتمال blocking I/O در handler** | نامشخص از کد موجود | اگر `handle_update` از `Session(engine)` همگام استفاده کند، رویداد لوپ مسدود می‌شود. باید تمام DB/شبکه داخل handler با `run_in_threadpool` یا session پس‌زمینه اجرا شود. این نیازمند بازبینی `handler.py` است. |
| **P2** | **خطر اجرای تکراری callbackها هنگام retry** | منطق داخلی `handler.py` (نامشخص) | تلگرام ممکن است یک update را چند بار بفرستد؛ به‌ویژه callbackهای پرداخت/خرید. باید idempotency در سطح state/callback پردازش شود. از کد `main.py` فقط می‌بینیم که `create_order` در بخش‌های دیگر تلاش برای idempotency دارد، اما مسیر bot مشخص نیست. |

---

### ۳) تحلیل button-driven و callback (مبتنی بر اطلاعات OVERVIEW و بخش‌های مرتبط در `main.py`)

از آنچه در `OVERVIEW` آمده، ربات‌های تلگرام و بله «button-driven کامل» هستند و callback با جداکننده‌ی `_` پردازش می‌شود. اما چون کد `handler.py` موجود نیست، نمی‌توانم موارد زیر را به‌طور قطعی تأیید کنم:

- **صحت جداکننده‌ی `_`:** اگر داده‌های داخل callback خود حاوی `_` باشند (مثلاً نام شهر فارسی یا شناسه‌های بلند)، تجزیه‌ی callback می‌تواند خطا ایجاد کند. بهتر است از یک جداکننده‌ی غیرممکن در داده‌ها (مثل `||`) یا JSON encoding استفاده شود.
- **مدیریت state:** جدول `bot_chat_states` باید constraint یکتا روی (`chat_id`,`platform`) داشته باشد تا در شرایط race از ایجاد ردیف‌های تکراری جلوگیری کند. از کد موجود نمی‌توان وجود این constraint را تأیید کرد.
- **انقضای state:** اگر کاربر مکالمه را نیمه‌کاره رها کند، state باید به‌طور خودکار منقضی شود (TTL یا cron). این جزئیات در `state.py` است.
- **پرداخت از طریق ربات:** مسیر `POST /api/orders` که در `main.py` دیده می‌شود، با پارامترهای فرم صدا زده می‌شود و `create_order` از `app.payment.orders` استفاده می‌کند. در بستر ربات باید مطمئن شویم `platform` و `chat_id` به‌درستی پاس داده می‌شوند و بعد از پرداخت، کاربر به همان چت هدایت می‌شود.

---

### ۴) ارتقاهای پیشنهادی

1. **امنیت وب‌هوک (P0/P1):**
   - برای تلگرام: `TELEGRAM_WEBHOOK_SECRET` در environment اجباری شود؛ در `lifespan` در حالت production خطا بده اگر خالی باشد.
   - برای بله: یک secret token در خود URL قرار دهید (مثلاً `https://chart.negar.io/api/v1/bale/webhook?token=...` یا مسیر شامل secret) و در nginx دسترسی به این مسیر را محدود کنید. یا از HMAC signature با استفاده از `X-Bale-...` استفاده کنید (اگر Bale ارائه می‌دهد). اگر هیچ امکانی نیست، حداقل IP allowlist از سرویس Bale یا استفاده از یک middleware کوچک برای امضای درخواست‌ها.
   - در هر دو endpoint، فقط درخواست‌هایی را بپذیرید که `Content-Type: application/json` و ساختار تلگرام/بله را دارند.

2. **مدیریت خطا و retry (P1):**
   - تابع `handle_update` را در یک `try/except Exception` قرار دهید. خطاها را به‌صورت structured log (شامل `update_id`, `chat_id`, `platform`, stacktrace) ذخیره کنید و همیشه 200 برگردانید تا از retry تلگرام جلوگیری شود. برای خطاهای بحرانی که باید واقعاً 5xx باشند (مثلاً DB down)، با سیستم هشدار مانیتور شوید.
   - استفاده از `Update` کلاس کتابخانه‌ی تلگرام برای parse و validation خودکار؛ برای بله نیز یک schema سبک تعریف کنید.

3. **Idempotency در callbackها (P2/P1):**
   - یکتا بودن `update_id` را در دیتابیس ذخیره کنید (جدول `processed_updates`) و قبل از پردازش، بررسی کنید که قبلاً پردازش نشده باشد. تلگرام `update_id` را یکتا ارسال می‌کند؛ بنابراین بهترین کلید برای جلوگیری از پردازش تکراری است. برای بله نیز در صورت وجود مشابه.
   - برای پرداخت‌های از طریق ربات، از `create_order` idempotent استفاده کنید و دقت کنید که `authority` تکراری، دوباره verify نشود.

4. **بهبود معماری (P2):**
   - جدا کردن منطق handler از webhook؛ بهتر است `handle_update` یک سرویس مستقل باشد که در تست‌ها mock شود.
   - استفاده از `BackgroundTasks` یا worker جدا برای پردازش به‌روزرسانی‌ها به‌صورت async، به‌جای `await` مستقیم در route، اگر پردازش سنگین است.
   - افزودن endpoint مدیریتی برای بررسی `webhook_info` تلگرام (تعداد pending update ،آخرین خطا) و تنظیم خودکار webhook در CI/استقرار.

---

### جمع‌بندی این بُعد

از نظر معماری، ربات‌ها در FastAPI با دو endpoint جداگانه تلگرام و بله گره خورده‌اند. **مهم‌ترین چالش امنیتی فعلی، نبود احراز در webhook بله و احراز شرطی در تلگرام است (P0).** بعد از آن، نبود مدیریت خطا/retry و عدم validation اولیه (P1) می‌تواند به پردازش تکراری، خطاهای پنهان و تجربه‌ی بد کاربران ربات منجر شود. در لایه‌ی داخلی (button-driven و callback) بدون دیدن `handler.py` نمی‌توان نظر قطعی داد، اما توصیه می‌شود `_` به‌عنوان جداکننده بازنگری شود، `update_id` برای idempotency ذخیره شود و state دارای constraint و انقضا باشد. پیش از هر تغییر، کد `app/bots/handler.py` و `app/bots/state.py` باید به‌صورت کامل ممیزی شود.
