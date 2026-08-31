# ZAYCHE — FULL UI/UX REDESIGN PLAN

**وضعیت:** پیش‌نویس اجرایی؛ منتظر تأیید مالک
**محدوده:** کل رابط کاربری زایچه؛ public، کاربر، خرید/گزارش، CMS و admin
**قاعده:** تا قبل از تأیید این سند، هیچ production template/CSS/JS تغییر نمی‌کند.
**جهت مصوب ماکاپ:** Dark Premium Editorial + Asymmetric Bento؛ شبانه، خلوت، دقیق، نه «glass روی همه‌چیز».

---

## ۰. یافتهٔ تحقیق فعلی

### ۰.۱ فهرست صفحات موجود

در ممیزی route/template فعلی این گروه‌ها شناسایی شد:

**Public / acquisition**

- `/` فرود
- `/plans` کاتالوگ و خرید
- `/birth-form` ساخت چارت
- `/synastry` سازگاری
- `/rectify` بازبینی ساعت تولد
- `/today` آسمان امروز
- `/sky` و `/sky-today`
- `/articles` و `/articles/{slug}`
- `/learn` و `/learn/{slug}`
- `/glossary`
- `/faq`, `/guide`, `/about`, `/contact`
- `/moon`, `/moon-in/{slug}`, `/signs/{slug}`
- `/birth-chart/{slug}`
- `/solar-guide`, `/relocation-guide`, `/deep-report`, `/self-discovery`
- `/gift-guide`, `/disclaimer`, `/privacy`, `/terms`, `/refund`
- صفحات share عمومی و `/payment/result`

**کاربر واردشده**

- `/dashboard`
- `/account`
- `/settings`
- `/credits`
- `/orders`
- `/reports`
- `/chats`
- `/chart/{chart_id}`
- `/chat/{chart_id}`
- `/today` و لایهٔ روزانه
- `/transit/{chart_id}` و `/transits/{chart_id}`
- `/solar/{chart_id}`
- `/relocation/{chart_id}`
- `/account/export` و حذف حساب

**ادمین و CMS**

- `/admin/login`
- `/admin`
- KPI و funnel
- سلامت سرویس و صف
- مالی، سفارش‌ها و استرداد
- کاربران و اعطای اعتبار
- فروش و قیمت‌گذاری
- محتوا: مقاله، صفحه، revision و restore
- media/R2
- provider/model و تست LLM
- secrets، token caps، هزینه و درآمد
- flags و تنظیمات اعلان

### ۰.۲ مشکل‌هایی که باید از پایه حل شوند

1. در بعضی صفحات فاصله و سلسله‌مراتب از یک سیستم واحد پیروی نمی‌کند.
2. داشبورد فعلی بیشتر فهرست لینک‌هاست تا «قدم بعدی کاربر».
3. `/reports` و `/orders` بیش از حد شبیه جدول خام هستند و stateهای loading/error/empty ضعیف‌اند.
4. `/credits` اقتصاد اعتبار را واضح و قابل مقایسه نشان نمی‌دهد.
5. `/admin` از نظر داده غنی است اما از نظر چگالی، گروه‌بندی و تصمیم‌پذیری سنگین است.
6. قالب‌ها هنوز aliasهای ماشینی `u-*` دارند؛ این‌ها باید در سطح کامپوننت ادغام شوند، نه فقط تعویض نام.
7. stateهای واقعی محصول — empty، loading، failed، degraded، insufficient credits، success — باید طراحی مستقل داشته باشند.
8. «HTTP 200» معیار طراحی نیست؛ هر صفحه باید در browser، در موبایل و دسکتاپ، با داده و بدون داده دیده شود.

---

## ۱. اسکیل‌ها و منابع طراحی مورد استفاده

### ۱.۱ ده منبع برتر انتخاب‌شده از جست‌وجوی skills

این‌ها برای طراحی این پروژه انتخاب شده‌اند؛ install count جست‌وجوی همان روز است و کیفیت با خود منبع و کاربرد پروژه سنجیده می‌شود:

1. `nexu-io/open-design` — حدود 91.5K؛ مرجع design workflow و جایگزین Claude Design
2. `nextlevelbuilder/ui-ux-pro-max-skill@design` — حدود 21.1K؛ الگوهای UI/UX و تصمیم‌گیری طراحی
3. `nextlevelbuilder/ui-ux-pro-max-skill@design-system` — حدود 21.8K؛ توکن و component system
4. `wshobson/agents@kpi-dashboard-design` — حدود 13.2K؛ داشبورد KPI و اولویت‌بندی داده
5. `github/awesome-copilot@penpot-uiux-design` — حدود 12.3K؛ الگوهای طراحی محصول و Penpot
6. `sickn33/agentic-awesome-skills@ui-ux-designer` — حدود 2.8K؛ جریان طراحی UX
7. `ulpi-io/skills@frontend-design-ui-ux` — حدود 2.1K؛ تبدیل design direction به frontend
8. `lotosbin/claude-skills@ui-ux-designer` — حدود 1.8K؛ الگوهای UX و component thinking
9. `manutej/luxor-claude-marketplace@ui-design-patterns` — حدود 764؛ pattern reference
10. `starchild-ai/official-skills@ui-design` — حدود 1.7K؛ اصول طراحی رابط

### ۱.۲ اسکیل‌های محلی قبلی که در این پروژه اعمال می‌شوند

- `design-taste-frontend` — ضد AI-slop، جهت بصری مشخص و خودبازبینی
- `high-end-visual-design` — تایپوگرافی، فاصله، سایه و حس پریمیوم
- `impeccable-design-polish` — polish بعد از ساخت، نه cosmetic churn
- `frontend-design` — طراحی production-grade با state واقعی
- `design-system` — primitive → semantic → component tokens
- `plan-design-review` — امتیازدهی و تشخیص AI-slop قبل از merge
- `design-review` — audit بصری و before/after
- `web-design-guidelines` — چک layout، color، motion و accessibility
- `ui-skills` — قواعد منسجم برای تمام قطعات رابط
- `responsive-admin-panel-ux` — admin responsive، drawer، modal و touch target
- `accessibility` — WCAG 2.2 و keyboard/focus/contrast
- `kpi-dashboard-design` — hierarchy داشبورد و metric governance
- `sketch` — ماکاپ قابل مشاهده پیش از production
- `fullstack-testing` — browser proof، state و flow واقعی

> نکتهٔ صداقت: بعضی entryهای upstream، ازجمله entry کاتالوگی `ui-ux-pro-max`، فقط metadata هستند و full database upstream در آن entry محلی موجود نیست. ادعا نمی‌کنیم دیتابیس کامل آن نصب است؛ از اصول قابل‌دسترسی و اسکیل‌های محلی کامل استفاده می‌کنیم.

---

## ۲. Design Contract نهایی

### ۲.۱ جهت بصری

**نام:** Observatory at Night — رصدخانه در شب

- زمینه: obsidian/navy عمیق، نه مشکی تخت
- لهجه: طلایی برنجی فقط برای action، status مهم و active state
- لهجهٔ دوم: violet بسیار محدود برای data visualization؛ نه gradient تزئینی
- سطح‌ها: حداکثر سه سطح واضح — page، panel، elevated action
- glass فقط برای chrome یا یک کارت برجسته؛ نه تمام کارت‌های صفحه
- سایه کم و دقیق؛ بدون glow بی‌دلیل
- کنتراست و typography اولویت بالاتر از decoration
- آیکون‌ها فقط از SVG sprite موجود؛ emoji به‌عنوان icon ممنوع

### ۲.۲ تایپوگرافی

- Vazirmatn برای خوانایی فارسی
- display بزرگ فقط در hero و page title
- حداکثر چهار اندازهٔ عنوان در هر page
- متن body با line-height مناسب RTL
- اعداد KPI با tabular/monospace treatment در صورت نیاز
- متن‌های انگلیسی فنی مثل slug/model با `dir=ltr` و container جدا

### ۲.۳ layout

- موبایل: ۳۹۰px baseline؛ ۳۶۰ و ۴۳۰ هم بررسی
- دسکتاپ: ۱۲۸۰px baseline؛ ۷۶۸، ۱۹۲۰ هم بررسی
- grid بر اساس intent، نه فهرست بلند کارت‌ها
- هر page یک primary action دارد
- bottom nav فقط پنج مقصد اصلی؛ باقی در drawer
- admin در موبایل: tab rail افقی یا drawer؛ هرگز ردیف فشردهٔ ۹ تب
- فرم‌ها: یک سؤال در هر مرحله، helper text کوتاه، خطای نزدیک فیلد
- هیچ کنترل اصلی زیر ۴۴×۴۴px

### ۲.۴ motion

- فقط برای state change، progress، reveal و feedback
- بدون animation بی‌نهایت تزئینی
- transform/opacity؛ بدون layout thrash
- reduced-motion کامل
- loading واقعی با progress/elapsed time؛ نه spinner ابدی

---

## ۳. معماری کامپوننت‌ها

قبل از بازطراحی pageها، این کامپوننت‌های semantic ساخته یا تکمیل می‌شوند:

### Foundation

- `AppShell`: appbar، main، bottom nav، drawer
- `PageHeader`: eyebrow، title، description، primary action
- `SectionHeader`: عنوان، توضیح، action
- `Surface`: page/panel/elevated variants
- `Button`: primary، secondary، ghost، danger، loading، disabled
- `IconButton`: tooltip، label، focus
- `Badge/Status`: ready، processing، failed، degraded، paid
- `Metric`: value، label، comparison، context
- `Tabs`: desktop + mobile scroll rail با active indicator
- `Toast/Alert`: success، warning، error، info
- `Modal/Sheet`: حذف، لغو، تأیید پرداخت، توضیح خطا
- `EmptyState`: عنوان، علت، CTA، next step
- `Skeleton`: برای هر layout اصلی، نه یک spinner عمومی

### Product components

- `ChartCard`
- `ReportCard`
- `ReportStatusTimeline`
- `CreditBalanceCard`
- `ProductCard`
- `PurchaseSummary`
- `EvidenceChip`
- `TransitTimeline`
- `InsightCard`
- `ConversationPreview`
- `CityPicker`
- `BirthFieldGroup`

### Admin components

- `AdminShell`
- `KpiStrip`
- `HealthSignal`
- `DataTable`
- `FilterBar`
- `AuditRow`
- `RevisionList`
- `MediaTile`
- `ProviderHealthCard`
- `CreditAdjustmentForm`
- `ConfirmDangerSheet`

تمام کامپوننت‌ها باید state matrix داشته باشند: default، hover، focus، active، disabled، loading، empty، error، success و reduced-motion.

---

## ۴. فازهای اجرای واقعی

### فاز ۰ — baseline و قرارداد (بدون تغییر production)

1. ثبت screenshot واقعی تمام template groupها در ۳۹۰ و ۱۲۸۰.
2. ثبت DOM/console/network و status برای تمام routeهای عمومی.
3. map کردن هر template به route و stateهای قابل تولید.
4. استخراج تمام aliasهای `u-*` و تعیین destination semantic آن‌ها.
5. تهیهٔ inventory کنترل‌ها، formها، fetchها و endpointهای هر صفحه.
6. تعیین golden copy فارسی برای title، CTA، empty و error.
7. تکمیل DESIGN.md/contract و ثبت تصمیم‌های نهایی.

**خروجی:** baseline report + route matrix + component matrix.

### فاز ۱ — shell و design system

1. بازسازی token architecture با یک مقیاس واحد؛ حذف موازی‌کاری `--fs/--font-size`، `--r/--radius` و shadow aliases.
2. طراحی appbar، drawer، bottom nav و main container.
3. هماهنگ‌کردن dark theme به‌عنوان default اصلی.
4. نگه‌داشتن light theme به‌عنوان theme دوم، اما با chrome و contrast مستقل و تست‌شده.
5. ساخت foundation components در `partials/ui/` با API مشخص.
6. حذف استفادهٔ مستقیم از کلاس‌های hash در templateهای بازطراحی‌شده.
7. ساخت `/design-system` با نمونهٔ واقعی تمام variants و states.

**گیت:** component screenshot در موبایل/دسکتاپ، axe، zero overflow، zero default-blue.

### فاز ۲ — public و acquisition

به‌ترتیب زیر بازطراحی می‌شوند:

1. `/` — فرود: hero، نمونهٔ واقعی، trust، CTA و مسیر ورود
2. `/plans` — کاتالوگ: one-credit entry، products by intent، comparison، purchase state
3. `/birth-form` — فرم چندمرحله‌ای، progress، validation، city picker و success
4. `/synastry` — دو نفر، city picker، تفاوت عاطفی/کاری، خطا و نتیجه
5. `/rectify` — timeline رویدادها، confidence، نتیجه و free boundary
6. `/today`, `/sky`, `/sky-today` — today layer و transit teaser
7. `/articles`, `/articles/{slug}` — editorial index، filter، article reading
8. `/learn`, `/learn/{slug}`, `/glossary` — آموزش و reference navigation
9. `/faq`, `/guide`, `/about`, `/contact` — content pages با hierarchy یکسان
10. SEO clusters: moon، signs، birth-chart city و landings محصول
11. share/payment/error pages — نتیجهٔ واضح، برگشت، retry و no-dead-end

برای هر صفحه این stateها طراحی می‌شوند:

- مهمان
- بعد از ساخت چارت
- بدون نتیجه
- در حال بارگذاری
- خطای سرویس
- rate limit
- successful completion
- mobile keyboard/open drawer/long Persian text

### فاز ۳ — داشبورد کامل کاربر

#### `/dashboard`

- header با greeting کوتاه و chart switcher
- «قدم بعدی تو» به‌عنوان primary block
- KPIهای قابل‌اقدام: اعتبار، گزارش فعال، گذر نزدیک
- کارت برجستهٔ today
- bento actions: reports، chat، synastry، add credit
- recent activity با status timeline
- onboarding فقط برای کاربر جدید و قابل بستن
- empty state کاملاً طراحی‌شده برای بدون چارت

#### `/chart/{id}`

- chart header و privacy indicator
- Big Three و key placements
- insight sections با evidence chips
- CTAهای واضح برای preview/report/chat
- download stateهای PDF/DOCX/audio
- access denied و expired/missing chart state

#### `/today`, `/transit/{id}`, `/transits/{id}`

- context header: چارت فعال، تاریخ، timezone
- today cards با priority و action
- transit timeline با past/current/upcoming
- تحلیل پولی جدا از دادهٔ رایگان
- failure/timeout state با توضیح اینکه اعتبار دوباره کم نمی‌شود

#### `/reports`, `/chats`, `/orders`

- فهرست واقعی، نه divهای ساده
- filter/status rail
- report progress timeline
- action menu برای view/download/retry
- empty state با یک CTA مشخص
- mobile rows تبدیل به cards compact

#### `/credits`, `/plans`

- balance hero
- ledger خوانا با sign و reason فارسی
- product purchase summary
- pack comparison و entry offer
- insufficient-credit modal/sheet
- success receipt و link مستقیم به محصول

#### `/account`, `/settings`

- account overview جدا از settings
- profile، notifications، subscriptions، privacy، export/delete
- هر destructive action در sheet با متن صریح
- notification permission و degraded browser state

### فاز ۴ — خرید، گزارش و اقتصاد اعتبار

1. مسیر `chart → preview → one-credit question → full report` با UI واحد.
2. checkout قبل/حین/بعد از پرداخت.
3. تفکیک دقیق product، pack و subscription در copy و visual hierarchy.
4. جلوگیری از ابهام «چیزی کم شد یا نشد» در هر action.
5. failure stateهای worker: timeout، retry، degraded، saved-for-later.
6. نمایش صریح invariant: اعتبار دوباره کم نمی‌شود.
7. report generation progress با زمان سپری‌شده و حداکثر انتظار.
8. download center برای PDF/DOCX/audio.
9. refund/failed/canceled/pending states.
10. browser E2E با ledger؛ تست واقعی هر مسیر بدون خرج واقعی در CI.

### فاز ۵ — پنل ادمین و CMS

#### IA پیشنهادی ادمین

- **Overview:** KPIهای ۵–۷تایی، trend، alerts و next action
- **Operations:** health، queue، LLM، backups، readiness
- **Commerce:** revenue، orders، refunds، coupons، credit economics
- **Users:** search، profile، charts، reports، credit adjustment
- **Content:** articles، pages، revisions، media
- **Configuration:** providers، models، caps، flags، secrets

#### desktop

- sidebar گروه‌بندی‌شده
- top context bar با زمان آخرین sync
- KPI strip محدود و actionable
- tables با filter، sort، pagination و row action
- detail drawer به‌جای modalهای عمیق

#### mobile

- پنج مقصد اصلی در bottom/drawer
- tabهای اضافی در horizontal rail قابل scroll
- table به stacked rows
- formها one-column
- همهٔ actionهای خطرناک در bottom sheet

#### CMS

- article editor با preview، autosave state، revision history و restore confirmation
- page editor با section blocks
- media manager با upload progress، type/size/status
- هیچ endpointی که در UI نیست یا UIای که endpoint ندارد
- همهٔ HTMX/fetchها از browser واقعی تست می‌شوند

### فاز ۶ — صفحات تولیدنشده و gap closure

قبل از ساخت هر route جدید، این سه سؤال اجباری است:

1. از navigation یا CTA قابل رسیدن است؟
2. backend دادهٔ واقعی و ownership gate دارد؟
3. empty/loading/error/paid state دارد؟

صفحات یا stateهای ناقص که باید تکمیل شوند:

- product landings و لینک ورودی‌شان
- report failure/saved state
- empty reports/orders/chats
- admin content detail/revision/media states
- dashboard بدون چارت و چندچارتی
- payment result و retry
- share pages با token و privacy copy
- unavailable/degraded provider state

### فاز ۷ — QA، تکمیل و انتشار

برای هر batch:

1. ساخت screenshot قبل/بعد.
2. اجرای Playwright در ۳۶۰، ۳۹۰، ۴۳۰، ۷۶۸، ۱۲۸۰ و ۱۹۲۰.
3. اجرای هر دو theme؛ dark معیار اصلی است.
4. بررسی browser console و failed requests.
5. axe-core روی تمام page groupها.
6. بررسی touch target، keyboard focus و RTL.
7. اجرای interaction sweep با کنترل واقعی و whitelist مستند.
8. اجرای user flows با cookie واقعی: guest، logged-in، no-credit، paid.
9. اجرای full pytest، ruff، CSS integrity، brand gate و drift gate.
10. deploy فقط بعد از سبزشدن همهٔ گیت‌ها؛ سپس curl + browser روی prod.

---

## ۵. معیار پذیرش نهایی

### visual

- هیچ صفحه‌ای شبیه raw HTML یا template عمومی نباشد.
- هر گروه page یک identity مشترک و hierarchy مشخص داشته باشد.
- dark mode بدون washed-out chrome یا label کم‌کنتراست باشد.
- هیچ لینک blue پیش‌فرض یا emoji به‌عنوان icon باقی نماند.
- هیچ overlap، clipping، horizontal overflow یا text collision در Persian وجود نداشته باشد.
- هر صفحه یک primary action و یک next step واضح داشته باشد.

### interaction

- تمام دکمه‌های قابل‌دیدن feedback دارند.
- هیچ fetch/hx target بی‌مسیر وجود ندارد.
- loading بیش از حد طولانی به timeout/degraded state تبدیل می‌شود.
- empty state به dead-end تبدیل نمی‌شود.
- destructive action تأیید قابل‌فهم دارد.

### technical

- page gate تمام routeهای public و auth را با cookie مناسب بسنجد.
- axe در صورت error قرمز شود، نه سبز کاذب.
- سوییپ interaction همهٔ کنترل‌های قابل‌دسترسی را ثبت کند.
- تست‌های مالی ledger را verify کنند.
- `pytest` بدون حذف/ضعیف‌کردن تست‌های قدیمی سبز بماند.
- CSS integrity و token validation سبز باشد.
- deploy و browser verification روی prod انجام شود.

---

## ۶. ترتیب دقیق اجرا بعد از تأیید

1. baseline report و screenshot inventory
2. foundation shell + tokens + components
3. dashboard user (`/dashboard`) — طرح مرجع
4. `/chart/{id}`, `/reports`, `/chats`
5. `/credits`, `/plans`, checkout/report states
6. `/settings`, `/account`, `/orders`
7. public `/`, `/birth-form`, `/synastry`, `/rectify`, `/today`
8. articles/learn/SEO/reference pages
9. admin overview و IA
10. admin commerce/users/operations
11. CMS/content/media/revisions
12. missing pages و empty/error states
13. full browser QA و accessibility/performance
14. full test suite، commitهای batch، deploy و prod proof
15. گزارش نهایی با before/after screenshot و route matrix

**قاعدهٔ توقف:** اگر یک page group در موبایل یا یکی از stateهای اصلی خراب باشد، batch سبز اعلام نمی‌شود و به گروه بعدی نمی‌رویم.

**خروجی مورد انتظار:** یک رابط کامل، یکپارچه، dark-premium، قابل استفاده برای موبایل و دسکتاپ، برای تمام صفحات کاربر، خرید، گزارش، CMS و ادمین — نه فقط چند screenshot زیبا.
