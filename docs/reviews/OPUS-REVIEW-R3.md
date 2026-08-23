# 🔍 OPUS-REVIEW-R3 — بازبینی دور ۲.۱

**بازبین:** Opus 5 · **تاریخ:** ۲۰۲۶-۰۸-۲۳ · **حالت:** REVIEW-ONLY (هیچ کدی تغییر نکرد)
**دامنه:** `70fbb85..0753f93` — ۴ کامیت · ۴۷ فایل · ‎+۴۹۵ / ‎−۱۳۵
**پاسخ به:** اجرای `Y1`–`Y17` از `OPUS-REVIEW-R2`
**تمرکز درخواستی:** (۱) آیا فیکس‌های Y حفرهٔ جدید باز کردند؟ (۲) کیفیت مهاجرت‌های Alembic (۳) پایداری مسیر پول بعد از سه دور

---

## STATUS

| محور | نتیجه |
|---|---|
| `Y1`–`Y17` | **۱۵ فیکس‌شده و تأییدشده** · ۱ نیمه (`Y7`) · ۱ تصمیم مالک (`Y15`) |
| کیفیت فیکس‌ها | **بالاترین دور تا امروز** — `Y2` و `Y6` و `Y9` از نظر مهندسی درست‌اند |
| کیفیت تست‌ها | **جهش واقعی** — `AC-1` بدون monkeypatch گیت، `AC-2` پارامتریک سه‌ردیفه ✅ |
| **مهاجرت‌های Alembic** | 🔴 **ضعیف‌ترین بخش این دور** — یک FK حذف شد، یک جدول اصلاً مهاجرت ندارد، یک DELETE داده‌ی پولی را تهدید می‌کند |
| **پایداری مسیر پول** | 🟠 مسیر «خرید اول» پایدار شد؛ **«خرید دوم/ارتقا» هنوز پول می‌گیرد و تحویل نمی‌دهد** |
| حذف حساب کاربری | 🔴 **شکسته** برای هر کاربری که اعتبار خرج کرده (نقض FK) |

**حکم:** دور ۲.۱ کیفیت بالایی داشت و هر ۱۷ مورد را واقعاً لمس کرد.
اما تمرکز روی «رفع ایرادهای بازبینی» باعث شد **دو ناحیهٔ مجاور** آسیب ببینند:
**چرخهٔ عمر داده (حذف حساب)** و **سلامت طرحوارهٔ تولید**.
🔴 سه مورد P0 باید قبل از هر دیپلوی دیگری بسته شوند.

---

## TRUTH-NOTES (صریح، طبق درخواست)

1. **سوئیت تست را اجرا نکردم.** این کانتینر بازبینی همچنان `venv` ندارد، PostgreSQL ندارد،
   Redis ندارد. ادعای «۷۰۱ passed + ۱ skipped، پوشش ۸۲٪» **راستی‌آزمایی نشده**.
   تنها چیزی که اجرا کردم: `python -m compileall app/` ⇒ **OK**.
2. **`scripts/ci.sh` اجرا نشد** ⇒ گیت‌های bandit / ruff / pip-audit / alembic-drift تأیید نشده‌اند.
3. 🔴 **فایل مدرک CI وجود ندارد.** گزارش شما به `docs/qa/CI-ROUND21-2026-08-23.log` ارجاع می‌دهد؛
   این فایل **در مخزن نیست**:
   - `ls docs/qa/CI-ROUND21-2026-08-23.log` ⇒ `No such file or directory`
   - `git ls-files | grep -i CI-ROUND` ⇒ **خالی**
   - `ls docs/qa/*.log` ⇒ **هیچ فایل log‌ای وجود ندارد**
   ⇒ مدرک اصلی «اولین CI کاملاً سبز» **کامیت نشده**. (`docs/reports/HERMES-ROUND21.md` موجود است.)
4. **مهاجرت‌ها را روی دیتابیس واقعی اجرا نکردم.** یافته‌های M1–M5 از خواندن SQL مهاجرت‌هاست.
   ادعای «applied to prod DB» را نمی‌توانم تأیید کنم.
5. **هیچ تست مرورگری اجرا نکردم.** یافتهٔ P1-1 (کلاس‌های Tailwind) از تطبیق نام کلاس‌ها با فایل‌های CSS است، نه از رندر.
6. **صحت نجومی خروجی گذر بررسی نشد** (نیازمند LLM/ephemeris واقعی).

---

## FINDINGS

### 🔴 P0-1 — حذف حساب کاربری برای **هر کاربر دارای اعتبار** می‌شکند (نقض FK)

**شدت:** بحرانی — خطای ۵۰۰ در مسیر حقوق کاربر (حریم خصوصی)، و تست‌ها پوشش نمی‌دهند.

- `app/models.py:152` — `CreditTransaction.user_id` دارای `foreign_key="users.id"`
- `app/models.py:189` — `Entitlement.user_id` دارای `foreign_key="users.id"`
- `alembic/versions/a1c0de000001_...py:50` — `sa.ForeignKeyConstraint(["user_id"], ["users.id"])`
  **بدون `ondelete`** ⇒ رفتار پیش‌فرض `NO ACTION` (منع حذف)
- `app/main.py:2801` — `session.delete(u)` کاربر را حذف می‌کند

اما فهرست حذف در `account_delete` این‌ها را پاک می‌کند و بس:
`ChatMessage · LLMRun · ReportChunk · Report · Order · Subscription · WeeklyReflection ·
ReferralEvent · ReferralCode · WithdrawalRequest · Chart · BirthProfile · User`

**هرگز پاک نمی‌شوند:** `credit_transactions` · `entitlements` · `explorations` ·
`transit_forecasts` · `subscribers` · `funnel_events` · `transit_alert_log` ·
`push_subscriptions` · `consent_log` · `notification_prefs` · `daily_reflections`

⇒ کاربری که **حتی یک اعتبار خرج کرده** (هر خرید، هر کاوش، هر اعطای اشتراک) یک ردیف
`credit_transactions` دارد ⇒ `session.delete(u)` با `IntegrityError` می‌شکند ⇒ **۵۰۰**.
با ورود اقتصاد اعتبار در دورهای ۱-۲، این تقریباً **همهٔ کاربران پولی** را شامل می‌شود.

**چرا تست نگرفت:** `grep -n "CreditTransaction\|Entitlement\|credits" tests/test_data_lifecycle.py
tests/test_account_delete_rag.py` ⇒ **خالی**. کاربر تستیِ حذف، هیچ‌وقت اعتباری ندارد.

> `Entitlement` در دور ۱ اضافه شد (`1adbae5`) — یعنی **یک جدول FK‌دار جدید بدون به‌روزرسانی مسیر حذف**.
> مشکل `credit_transactions` قدیمی‌تر است، ولی حالا برای اولین بار در مسیر اصلی محصول فعال شده.

---

### 🔴 P0-2 — مهاجرت `c8d2e3f4a5b6` یک FK با `CASCADE` را **حذف می‌کند** تا `alembic check` سبز شود

**شدت:** بحرانی — جهت فیکس اشتباه است و یک رگرسیون حریم خصوصی می‌سازد.

`alembic/versions/c8d2e3f4a5b6_align_schema_with_models.py`:
```python
# transit_forecasts.chart_id: model declares a PLAIN column (no FK) — drop it
op.drop_constraint('transit_forecasts_chart_id_fkey', 'transit_forecasts', type_='foreignkey')
```
`downgrade` نشان می‌دهد قید حذف‌شده `ondelete='CASCADE'` داشته است.

مدل (`app/models.py`، `class TransitForecast`) واقعاً FK ندارد:
`chart_id: str = Field(index=True, max_length=64)`.

⇒ به‌جای **درست‌کردن مدل** (افزودن `foreign_key="charts.id"`)، **طرحوارهٔ دیتابیس تضعیف شد**
تا با مدلِ ناقص جور دربیاید. پیامدها:
1. حذف چارت دیگر ردیف‌های `transit_forecasts` را پاک نمی‌کند ⇒ **ردیف یتیم برای همیشه**.
2. جدول `transit_forecasts` حاوی **روایت‌های پولی گذر** است — یعنی تفسیر شخصی چارت تولد کاربر = **دادهٔ شخصی**.
   پیش از این مهاجرت، CASCADE آن‌ها را هنگام حذف چارت پاک می‌کرد. حالا **از حذف حساب جان سالم به در می‌برند**.
3. این مستقیماً با `docs/PRIVACY.md` و `tests/test_data_lifecycle.py` در تضاد است.

> قاعده: `alembic check` قرمز یعنی «مدل و طرحواره اختلاف دارند» — نه «طرحواره را خراب کن».
> در مواردی که طرحوارهٔ تولید **درست‌تر** است، مدل باید اصلاح شود.

---

### 🔴 P0-3 — جدول `subscribers` **هیچ مهاجرتی ندارد** ⇒ استقرار تازه می‌شکند

- مدل: `app/models.py:515` — `__tablename__ = "subscribers"` (دور ۱، ویژگی G3)
- `grep -rn "subscriber" alembic/versions/` ⇒ **صفر نتیجه**

⇒ روی یک دیتابیس تازه، `alembic upgrade head` جدول `subscribers` را **نمی‌سازد**.
سپس `POST /api/subscribe` و `/gift-guide` و `/guide/download/{token}` و `/unsubscribe/{token}`
همگی با خطای «relation does not exist» ⇒ **۵۰۰**.
(`.env.example` تصریح می‌کند تولید فقط Alembic-managed است: `CREATE_ALL_ON_BOOT=0`.)

گزارش دور ۲ خودش به «subscribers-table prod migration fix» اشاره می‌کند ⇒ تولید **دستی** وصله شده
⇒ **طرحوارهٔ تولید از زنجیرهٔ مهاجرت‌ها جدا افتاده**.

**و نکتهٔ مهم‌تر:** اگر جدولی در مدل باشد و در مهاجرت‌ها نباشد، `alembic check` باید drift بدهد.
سبز بودنش یعنی چک روی دیتابیسی اجرا شده که **آثار `create_all` را از اجرای قبلی داشته**.
⇒ **گیت drift عملاً بی‌اثر است.** خودِ وجود مهاجرت `c8d2e3f4a5b6` («هم‌ترازی نام ایندکس‌ها»)
شاهد همین است: دارد آثار `create_all` را تمیز می‌کند، نه drift واقعی مدل را.

---

### 🟠 P1-1 — صفحهٔ پرچم‌دار گذر با کلاس‌های **Tailwind** نوشته شده و پروژه Tailwind ندارد

`app/templates/transits_forecast.html` سرتاسر با utilityهای Tailwind نوشته شده:
`max-w-2xl mx-auto px-4 py-6` · `space-y-4` · `border rounded-xl p-3` · `text-sm opacity-70` ·
`bg-indigo-600 text-white border-indigo-600` · `dark:border-white/20` …

اما:
- `grep -rn "tailwind" app/templates/base.html app/static/css/*.css` ⇒ **خالی**
- هیچ‌کدام از `rounded-xl` / `space-y-4` / `bg-indigo-600` / `text-sm` / `opacity-60`
  در **هیچ‌کدام از** `tokens.css` · `base.css` · `components.css` · `generated.css` تعریف نشده‌اند.

⇒ صفحهٔ محصول پولی جدید **بدون استایل** رندر می‌شود: بدون کارت، بدون فاصله، بدون
`max-width`، دکمهٔ انتخاب ۳/۱۲ ماه بدون هیچ حالت بصریِ «انتخاب‌شده».
تنها بخش استایل‌دار صفحه، `credit_cta` است که از کلاس‌های واقعی پروژه (`.glass` / `.btn`) استفاده می‌کند.

**چرا ممیزی UI صفر تخلف داد:** `scripts/ui_audit.py` کنتراست، هدف لمسی و اسکرول افقی را می‌سنجد —
هیچ‌کدام «آیا این کلاس اصلاً وجود دارد؟» را چک نمی‌کنند. متن بدون استایل معمولاً هر سه را پاس می‌کند.

> این نقطهٔ کور را کارِ دیزاین‌سیستم (C1/C2) هم نگرفت، چون آن کار روی قالب‌های **موجود** انجام شد
> و این قالب **بعداً** در B3 ساخته شد.
> **این تا حدی تقصیر پلن من است:** در توصیف استک، «Tailwind» را از README نقل کردم بدون اینکه بگویم
> پروژه هیچ مرحلهٔ build فرانت ندارد. آن را در REQUIRED_FIXES جبران می‌کنم.

---

### 🟠 P1-2 — باقی‌ماندهٔ `Y1`: **خرید دوم / ارتقای گزارش** پول می‌گیرد و تحویل نمی‌دهد

فیکس `Y1` (`app/main.py:711`) درست است ولی فقط برای **اولین** خرید:
```python
if _u and not paid and ent is not None and not ent.ref_id:
    ...
    ent.ref_id = rep.id
```
دو مشکل ساختاری در کنار هم:
1. `app/entitlements.py` — `has()` **اولین** استحقاق قابل‌استفاده را برمی‌گرداند.
2. استحقاق‌های `report` هرگز مصرف نمی‌شوند — `consume()` فقط برای چت صدا زده می‌شود
   (`app/main.py:1880`) ⇒ `used` همیشه ۰ ⇒ `_usable()` برای همیشه True.

سناریوی واقعی:
1. کاربر `report_full` می‌خرد (۷ اعتبار) ⇒ گزارش #۱ ⇒ `ent1.ref_id = rep1` ✅ قابل دانلود.
2. بعداً `report_gold` می‌خرد (**۱۴ اعتبار**) ⇒ `ent2` با `ref_id=None`.
3. `POST /api/charts/{id}/report` ⇒ گزارش #۱ با وضعیت `done` وجود دارد ⇒ **بازگشت زودهنگام**،
   گزارش تازه‌ای ساخته نمی‌شود، `ent2` دست‌نخورده می‌ماند.
4. با `?regenerate=1` گزارش #۲ ساخته می‌شود، ولی `ent_has(...)` باز هم **`ent1`** را برمی‌گرداند
   (اولین قابل‌استفاده) ⇒ `not ent.ref_id` نادرست است ⇒ **bind انجام نمی‌شود** ⇒ گزارش #۲ **۴۰۳**.
5. `_credit_plan` هم از `ent1.source_ref` مشتق می‌شود ⇒ `report_full` ⇒ گزارش **full** به‌جای **gold**.

⇒ ۱۴ اعتبار پرداخت می‌شود، `ent2` هرگز استفاده نمی‌شود، و خروجی از سطح پایین‌تر است.

**فیکس ریشه‌ای:** `has()` باید بتواند «استحقاق **بدون** ref_id» را هدف بگیرد
(مثلاً `unbound_only=True`)، و استحقاق `report` بعد از bind باید `used=1` بگیرد تا از استخر خارج شود.

---

### 🟠 P1-3 — `Y7` نیمه‌تمام: صفحه بعد از رفرش هنوز فقط ۱۲ ماه را می‌خواند

- ✅ انتخابگر ۳/۱۲ ماه به UI اضافه شد (`transits_forecast.html:46-51`) و
  `analyze()` حالا `this.months` را می‌فرستد (خط ۹۷) و قیمت را درست نشان می‌دهد (خط ۴۳).
- ❌ ولی `transits_page` هنوز هاردکد است: `cached_forecast(session, chart_id, 12, ...)` و
  `app/main.py:2537` — `TransitForecast.months == 12`.

⇒ کاربری که `transit_3m` می‌خرد (۲ اعتبار): روایت‌ها فقط در پاسخ همان POST دیده می‌شوند؛
با **یک رفرش صفحه ناپدید می‌شوند** (چون ردیف `months=3` هرگز خوانده نمی‌شود).
یافتهٔ N4 نیمه‌بسته است.

---

### 🟠 P1-4 — DELETE حذف تکراری‌ها ممکن است **تحلیل‌های پولی را نابود کند**

`alembic/versions/c7f1a2b9d4e6_y4_unique_transit_chart_months.py`:
```sql
DELETE FROM transit_forecasts a USING transit_forecasts b
WHERE a.chart_id = b.chart_id AND a.months = b.months AND a.id < b.id
```
ردیفِ با **بزرگ‌ترین `id`** نگه داشته می‌شود — یعنی «جدیدترین»، نه «آنکه `narratives` پولی دارد».

اگر در تولید جفتی وجود داشته باشد که ردیف قدیمی‌تر تحلیل خریداری‌شده دارد و ردیف تازه‌تر
فقط یک لیست رویداد ساده است (**دقیقاً همان حالتی که نبودِ قید یکتایی می‌سازد**)،
این مهاجرت **محتوای پولی کاربر را برای همیشه حذف می‌کند**.

**درست:** اول ردیف‌های دارای `narratives` را در اولویت نگه‌داشتن بگذار (یا merge کن)، بعد حذف کن.
و قبل از اجرا، تعداد جفت‌های در معرض خطر را گزارش کن.

---

### 🟡 P2 — موارد کوچک‌تر

| # | یافته | محل |
|---|---|---|
| P2-1 | `c8d2e3f4a5b6` ستون `notification_prefs.transit_alerts` را **nullable** می‌کند. `NULL` در پایتون falsy است ⇒ کاربر بی‌صدا از اعلان گذر خارج می‌شود. `downgrade` هم `NOT NULL` را بدون پرکردن NULLها برمی‌گرداند ⇒ downgrade می‌شکند | مهاجرت |
| P2-2 | همان مهاجرت، `drop_index` بدون `IF EXISTS` دارد. اگر نام ایندکس در تولید فرق کند (میراث `create_all`)، استقرار وسط کار می‌شکند — دقیقاً همان مشکلی که این مهاجرت برای رفعش نوشته شده | مهاجرت |
| P2-3 | `refund()` وقتی `room <= 0` است **`original`** (ردیف خرجِ منفی) را برمی‌گرداند. فراخواننده `abs(rr.amount)` می‌زند ⇒ به کاربر گزارش می‌دهد کل مبلغ برگشت خورده، در حالی که **هیچ برگشتی رخ نداده** | `app/credits.py` |
| P2-4 | `rectify` (۲ اعتبار) در کاتالوگ `app/db.py:122` باقی مانده ولی هیچ گیتی نمی‌خواندش (تصمیم `Y15`). همان الگوی R8 برگشت: **پنل ادمین قیمتی نشان می‌دهد که هرگز گرفته نمی‌شود** و گزارش مالی را دروغین می‌کند ⇒ `active=False` بگذار | `app/db.py:122` |
| P2-5 | `test_r8_audio_request_402_when_broke` هنوز `_report_gate` را monkeypatch می‌کند. حالا که `AC-1` مستقل وجود دارد قابل قبول است، ولی مسیر صوت **هرگز** بدون پچ تست نشده | تست |
| P2-6 | `TransitAlertLog` / `FunnelEvent` / `Subscriber` هیچ سیاست نگه‌داری (retention) ندارند و در حذف حساب هم پاک نمی‌شوند ⇒ رشد بی‌پایان + دادهٔ شخصی باقی‌مانده | چرخهٔ عمر داده |

---

## آنچه واقعاً درست شد (تأییدشده با کد)

| مورد | تأیید |
|---|---|
| **Y1** bind کردن `ref_id` | `app/main.py:711` — و `AC-1` واقعاً بدون monkeypatchِ گیت تست می‌کند ✅ |
| **Y2** استخراج پلن | از `ent.source_ref → CreditTransaction.reason` — **رویکرد درست** (فیلد ساختگی `source_action` حذف شد) ✅ |
| **Y3** کش قبل از خرج | ترتیب واقعاً برعکس شد؛ مسیر cached با **صفر خرج** برمی‌گردد ✅ |
| **Y6** سقف تجمعی بازگشت | `SELECT SUM(amount) ... WHERE reason='refund' AND ref_id=:rid` + clamp ✅ |
| **Y8** اشتراک سالانه | `"yearly": "chat"` در `_kind_for_plan` **و** هر سه تاپل گیت چت ✅ |
| **Y9** انقضا در `consume()` | داخل خود `UPDATE`: `AND (expires_at IS NULL OR expires_at >= :now)` — اتمیک و درست ✅ |
| **Y10** بهداشت تست | همهٔ تست‌ها به `environ.setdefault` منتقل شدند؛ صفر بازنویسی `DATABASE_URL` ✅ |
| **Y11** assertهای گمشده | `AC-1` و `AC-2` (پارامتریک basic/full/gold) و `Y3`/`Y6`/`Y8` همه assert واقعی دارند ✅ |
| **Y13** سقف روزانهٔ چت | کد حالا با داکسترینگ می‌خواند (entitlement-only = gold، ۵/روز) ✅ |
| **Y14** `credit_cta` | در chat / synastry / explore هم include شد ✅ |
| **Y4** ساخت مهاجرت | مهاجرت‌ها ساخته شدند و زنجیره **تک‌سر** است (`c8d2e3f4a5b6`) ✅ — کیفیتشان جداگانه در P0-2/P1-4 |

**کیفیت تست‌ها این دور واقعاً جهش کرد.** `test_y2_ac2_plan_from_tx_reason` با سه پارامتر
(`basic`/`full`/`gold`) دقیقاً همان چیزی است که در دور قبل نبود، و `test_y1_ac1_...` صراحتاً
می‌نویسد «Queue is faked (infra), the ENTITLEMENT GATE IS NOT». این استاندارد را نگه دار.

---

## REQUIRED_FIXES

### گروه ۱ — مسدودکنندهٔ استقرار
| ID | فیکس | یافته |
|---|---|---|
| `Z1` | در `account_delete`، **قبل از** `session.delete(u)`، این‌ها را پاک کن: `credit_transactions`, `entitlements`, `explorations`, `push_subscriptions`, `consent_log`, `notification_prefs`, `daily_reflections`, `subscribers` (بر اساس contact کاربر)، و `transit_forecasts` بر اساس `chart_ids`. برای `funnel_events`/`transit_alert_log` یا حذف یا ناشناس‌سازی | P0-1 |
| `Z2` | مهاجرت جدید: FK `transit_forecasts.chart_id → charts.id ON DELETE CASCADE` را **برگردان** و مدل را با `foreign_key="charts.id"` اصلاح کن. `c8d2e3f4a5b6` را revert نکن — یک مهاجرت رو به جلو بنویس | P0-2 |
| `Z3` | مهاجرت `create_table("subscribers")` بنویس (idempotent با `IF NOT EXISTS` یا بررسی inspector، چون تولید دستی ساخته شده) | P0-3 |
| `Z4` | گیت drift را واقعی کن: `alembic check` باید روی یک **دیتابیس تازه و خالی** اجرا شود که هرگز `create_all` ندیده. در `ci.sh` قبل از چک، DB مخصوص drift را drop/create کن | P0-3 |

### گروه ۲ — مسیر پول و محصول
| ID | فیکس | یافته |
|---|---|---|
| `Z5` | `has(..., unbound_only=True)` اضافه کن؛ در مسیر ساخت گزارش استحقاق **بدون `ref_id`** را انتخاب کن و بعد از bind، `used=1` بگذار تا از استخر خارج شود | P1-2 |
| `Z6` | `transits_page` را با `?months=` پارامتری کن (پیش‌فرض ۱۲) و همان مقدار را به `cached_forecast` و کوئری `TransitForecast` بده | P1-3 |
| `Z7` | مهاجرت `c7f1a2b9d4e6` را با یک مهاجرت جبرانی امن کن: قبل از حذف، ردیف‌های دارای `narratives` را در اولویت نگه‌داشتن بگذار؛ و یک اسکریپت گزارش «چند جفت در معرض خطر بودند» اجرا کن | P1-4 |
| `Z8` | `credit_prices.rectify` را `active=False` کن (یا از کاتالوگ بردار) تا گزارش مالی ادمین درست بماند | P2-4 |

### گروه ۳ — UI و مهاجرت‌های امن
| ID | فیکس | یافته |
|---|---|---|
| `Z9` | `transits_forecast.html` را با **کلاس‌های واقعی پروژه** بازنویسی کن (`.glass`, `.btn`, `.card`, توکن‌ها) — نه Tailwind | P1-1 |
| `Z10` | یک چک جدید به `scripts/ui_audit.py`: هر `class="..."` در قالب‌ها باید در CSS پروژه تعریف شده باشد؛ کلاس تعریف‌نشده = تخلف | P1-1 |
| `Z11` | `notification_prefs.transit_alerts` را در **مدل** `nullable=False` کن و مهاجرت رو به جلو با backfill (`UPDATE ... SET transit_alerts = true WHERE transit_alerts IS NULL`) | P2-1 |
| `Z12` | همهٔ `drop_index`/`drop_constraint` را با بررسی وجود (inspector) امن کن | P2-2 |
| `Z13` | `refund()` وقتی جا ندارد باید `None` برگرداند (نه `original`)؛ فراخواننده `refunded_credits=0` گزارش کند | P2-3 |
| `Z14` | تست مسیر صوت **بدون** monkeypatch گیت | P2-5 |
| `Z15` | سیاست نگه‌داری برای `funnel_events` / `transit_alert_log` (مثلاً ۹۰ روز) + پاک‌سازی در حذف حساب | P2-6 |
| `Z16` | فایل `docs/qa/CI-ROUND21-2026-08-23.log` را واقعاً کامیت کن (یا ارجاع را از گزارش بردار) | TRUTH-NOTE 3 |

---

## ACCEPTANCE_CRITERIA

### AC-1 (Z1) — حذف حساب کاربرِ پولی
```
کاربر بساز → ۲۰ اعتبار grant → report_full بخر → گزارش بساز → transit_12m بخر
→ POST /account/delete  → ۲۰۰ (نه ۵۰۰)
→ assert: users, credit_transactions, entitlements, explorations,
          transit_forecasts (برای chartهای او), subscribers  همه صفر ردیف
```
**این تست باید بدون فیکس قرمز شود** — قبل از فیکس اجرا کن و `IntegrityError` را در گزارش بیاور.

### AC-2 (Z2) — CASCADE برگشته
```
alembic upgrade head
assert: قید FK روی transit_forecasts.chart_id در information_schema با delete_rule='CASCADE'
تست: چارت را حذف کن → ردیف transit_forecasts آن چارت خودکار پاک شود
alembic check → صفر drift
```

### AC-3 (Z3/Z4) — طرحوارهٔ تازه سالم است
```
دیتابیس کاملاً خالی (هرگز create_all ندیده) → alembic upgrade head
assert: جدول subscribers وجود دارد
POST /api/subscribe → ۲۰۰ (نه ۵۰۰)
alembic check روی همان DB → صفر drift    ← گیت واقعی
```

### AC-4 (Z5) — خرید دوم/ارتقا
```
report_full بخر (۷) → گزارش#۱ → PDF ۲۰۰
report_gold بخر (۱۴) → گزارش جدید بساز → plan_key == "gold"  ← الان "full" است
→ PDF گزارش#۲ ۲۰۰  ← الان ۴۰۳ است
→ موجودی = شروع − ۲۱
```

### AC-5 (Z6) — گذر ۳ ماهه بعد از رفرش
```
transit_3m بخر (۲ اعتبار) → GET /transits/{id}?months=3 → روایت‌ها در HTML باشند
GET /transits/{id} (بدون پارامتر) → پیش‌فرض ۱۲ ماه، بدون خطا
```

### AC-6 (Z7) — مهاجرت داده‌ی پولی را نمی‌خورد
```
fixture: دو ردیف تکراری (chart_id, months) — قدیمی‌تر دارای narratives، تازه‌تر بدون
اجرای منطق dedupe → ردیف باقی‌مانده narratives را دارد
```

### AC-7 (Z9/Z10) — صفحهٔ گذر استایل دارد
```
scripts/ui_audit.py چک جدید: هر کلاس استفاده‌شده در قالب‌ها در CSS تعریف شده
→ transits_forecast.html صفر کلاس تعریف‌نشده
اسکرین‌شات ۳۷۵px قبل/بعد در گزارش
```

### AC-8 — گیت سراسری با مدرک
```
bash scripts/ci.sh → سبز
خروجی کامل در docs/qa/CI-<round>.log  کامیت شود  (این بار واقعاً)
```

---

## دو قانون برای دور ۴

1. **قانون «شعاع انفجار».** وقتی یک ماژول را عوض می‌کنی، فهرست کن چه چیزهای دیگری به آن
   **جدول** وابسته‌اند — نه فقط به آن **تابع**. `Entitlement` و `CreditTransaction` اضافه شدند
   ولی `account_delete` (که هر جدول FK‌دارِ کاربر را باید بشناسد) به‌روز نشد. برای هر جدول جدید
   با FK به `users`، سه جا را چک کن: **حذف حساب · خروجی داده (export) · سیاست نگه‌داری**.

2. **قانون «drift را با تخریب حل نکن».** اگر `alembic check` قرمز شد، اول بپرس **کدام طرف درست است**.
   در `c8d2e3f4a5b6` هر سه تغییر، دیتابیس را به سمت مدلِ ضعیف‌تر بردند (حذف FK، nullable کردن ستون).
   پیش‌فرض باید عکسش باشد: **مدل را غنی‌تر کن تا با طرحوارهٔ درست جور شود.**

---

*بازبینی توسط Opus 5 — فقط از روی کد. تست، CI و مهاجرت اجرا نشد (TRUTH-NOTES بند ۱-۴).*
