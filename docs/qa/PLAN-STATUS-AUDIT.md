# 📋 صورت‌وضعیت پلن اصلی — PLAN-STATUS-AUDIT
**روش:** برای هر بند، رفتارِ قابل‌مشاهده با منبع را بررسی کردم (نه «بررسی شد»). فقط وقتی `DONE` است که اثبات رفتار موجود باشد. بندهای `NARROWED`/`NOT-DONE` صریح علامت خورده‌اند.

## A — اقتصاد اعتبار و مسیر خرید
| بند | خواسته | واقعیت اجراشده | وضعیت | مدرک |
|---|---|---|---|---|
| A1 | مدل داده + مهاجرت | `users.credits`, `credit_transactions`, `credit_prices`, `entitlements` + مهاجرت‌ها | ✅ DONE | `app/models.py`, `alembic/versions/*` |
| A2 | سرویس مرکزی اعتبار | `balance/spend/refund/get_price` در `app/credits.py` | ✅ DONE | `app/credits.py` |
| A3 | لایهٔ استحقاق + بازنویسی گیت‌ها | `has/consume/grant_from_credits`؛ گیت‌های چت/گزارش/سیناستری | ✅ DONE | `app/entitlements.py` |
| A4 | مسیر خرید یکپارچه UI+API | `api/purchase` + `credit_cta` ساخته شد؛ ولی **`plans.html` تا R.10 از `api/orders` تومانی می‌فروخت** | 🟠 **NARROWED** → در R.10 رفع شد | `app/main.py:909`, `plans.html` |
| A5 | اجبار حساب برای خرید | `api/purchase` بدون لاگین → 401 `login_required` | ✅ DONE | `app/main.py:914` |
| A6 | مهاجرت داده و سازگاری | `backfill_entitlements(session, dry_run)` | ✅ DONE | `app/entitlements.py:204` |
| A7 | پنل ادمین اقتصاد اعتبار | `admin_credit_report` + UI؛ **تا R.9 `p.key` → ۵۰۰** | 🟠 **NARROWED** → R.9 رفع | `app/routes/admin.py` |

## B — موتور گذر و تحلیل
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| B1 | موتور پیش‌بینی گذر قطعی | `transit_forecast.forecast()` (Swiss Ephemeris، بدون LLM) | ✅ DONE | `app/astrology/transit_forecast.py` |
| B2 | لایهٔ تحلیل (LLM مقید به شواهد) | `narrate_transit` + QA gate + retry/refund | ✅ DONE | `app/report/transit_narrative.py` |
| B3 | API + صفحهٔ گذرها | `/api/charts/{id}/forecast` + `transits_forecast.html` + `analyze` | ✅ DONE | `app/main.py`, template |
| B4 | اعلان گذر | `run_transit_alerts` + `transit_alert_log` | ✅ DONE | `app/report/transit_alerts.py` |
| B5 | رفع وعدهٔ شکسته (F5/F6) | `rectify` رایگان شد (Y15)؛ refund کامل در QA | ✅ DONE | `app/credits.py` |

## C — دیزاین‌سیستم و UI
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| C1 | استخراج دیزاین‌سیستم | `tokens.css` + `components.css` + `generated.css`؛ همگرا شده ولی **با دیزاین‌سیستم نام‌گذاری‌شده در پلن (tailwind) تفاوت دارد** | 🟠 **NARROWED** | `app/static/css/*` |
| C2 | مهاجرت قالب‌ها | ۹۹۴ استایل inline → utility CSS (کامیت `fb85446`) | ✅ DONE | `base.html`, CSS |
| C3 | ممیزی صفحه‌به‌صفحه UI/UX | `scripts/ui_audit.py` + ۱۶ صفحه × ۵ سایز (صفر تخلف) | ✅ DONE | `docs/qa/UI-AUDIT-*` |
| C4 | الگوهای UX که باید ساخته شوند | توست/دیالوگ/Chip/بک‌لینک (کامیت `c8c5d47`) | ✅ DONE | `base.html` |
| C5 | دسترس‌پذیری + کارایی | aria/labels/touch >40px؛ `form.html` تا R.9 ۲ ورودی بدون label | 🟠 **NARROWED** → R.9 رفع | `form.html` |

## D — ناوبری و CTA
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| D1 | ساختار ناوبری هدف | `NavItem` + `NAV_ITEMS` تنها منبع | ✅ DONE | `app/nav.py` |
| D2 | پیاده‌سازی ناوبری واحد | `nav_for()` در `base.html`؛ گروه‌های کشو | ✅ DONE | `app/main.py:165` |
| D3 | قوانین دکمه‌های CTA | `primary=True` یک CTA + `btn` classes | ✅ DONE | `app/nav.py` |

## E — تست و مسیرها
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| E1 | سیاههٔ کامل مسیرها | `test_route_inventory_e2.py` (همهٔ href/مسیرها) | ✅ DONE | `tests/` |
| E2 | صفحات کم‌دار | `/glossary` ساخته شد (R7)؛ `gift-guide` موجود | ✅ DONE | `app/routes/seo.py` |
| E3 | سوئیت تست واقعی | ۷۴۷+ تست + CI واقعی از مخزن | ✅ DONE | `tests/`, GitHub Actions |
| E4 | «هیچ باگی بدون تست بسته نمی‌شود» | هر فیکس دیوم با تست منفی | ✅ DONE | `tests/test_*` |

## F — محتوا
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| F1 | ممیزی محتوای‌موجود | `content_audit_f1.py` + ۵۰ مقاله؛ لینک‌های مرتبط موضوعی شد (R6) | ✅ DONE | `scripts/`, `tests/` |
| F2 | رفع محتوای ناقص | ۴ مقاله ۳۰۰-۵۰۰ کلمه؛ بالای آستانه ولی کوتاه‌تر از ایده‌آل | 🟠 **PARTIAL** | `content_audit_f1.py` |
| F3 | واژه‌نامه + «حالت ساده/تخصصی» | `/glossary` ۷۸ اصطلاح (R7) + لینک عمیق (R8) | ✅ DONE | `app/seo/glossary.py` |
| F4 | محتوای درون‌محصولی | پشتیبانی شده | ✅ DONE | templates |
| F5 | لحن برند | `brand_language_gate.py` + allowlist | ✅ DONE | `scripts/` |

## G — قیف و رشد
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| G1 | ابزار سنجش قیف | `track.js` (۲۶ رویداد) + `/api/track` + admin funnel | ✅ DONE | `app/static/js/track.js` |
| G2 | بهینه‌سازی قیف | **منتظر ترافیک واقعی** — درست، بدون داده حدس است | ⏳ **PENDING** | — |
| G3 | لید مگنت | `/gift-guide` + `/guide/download` (توکن‌دار) | ✅ DONE | `app/main.py` |
| G4 | دنبالهٔ آنبوردینگ | زیرساخت SMS/enotif | ⏳ **PENDING** (کلید خارجی) | — |
| G5 | رشد ویروسی | referral رمز + پاداش؛ ref_url در نتیجهٔ پرداخت | ✅ DONE | `app/payment/orders.py` |
| G6 | SEO | sitemap ۱۲۸ URL + Schema + ۵۰ مقاله | ✅ DONE | `app/routes/seo.py` |
| G7 | برند | گیت brand-language | ✅ DONE | `scripts/` |
| G8 | کانال‌های جذب (ایران) | — | ⏳ **PENDING** (نیاز به داده/تصمیم مالک) | — |

## Z — محیط کار
| بند | خواسته | واقعیت | وضعیت | مدرک |
|---|---|---|---|---|
| Z1 | بهبود محیط کار | ناسنجیده | ❓ UNVERIFIED | — |

---

## جمع‌بندی
- **DONE:** ۳۱
- **NARROWED (رفع‌شده در R.9/R.10):** A4, A7, C5 → ۳
- **PARTIAL / PENDING / UNVERIFIED:** F2 (۴ مقاله کوتاه), G2/G4/G8 (نیاز به داده/مالک), Z1 (ناسنجیده) → ۶
- **بزرگ‌ترین باریک‌شدگی واقعی که باقی بود:** «دو سیستم پولی موازی» — `plans.html` می‌فروخت `api/orders` (تومانی) در حالی که کل بک‌اند `api/purchase` (اعتباری). **در R.10 با P1-2 (جدول واحد اعتباری) رفع شد.**
