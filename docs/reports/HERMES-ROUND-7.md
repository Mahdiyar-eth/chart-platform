# گزارش هرمس — دور ۷ (B4 + B5 · بستن مرحلهٔ ۲)

**تاریخ:** 2026-08-22 · **شعبه:** `hermes/plan-v1-r1` · **Head:** `032821b`

## خلاصه

مرحلهٔ ۲ (محصول گذر) **کامل و بسته شد**. زنجیرهٔ B1→B5 همه با تست پذیرش سبز هستند.

## تغییرات این دور

| آیتم | شرح | شاهد |
|---|---|---|
| **B4** اعلان گذر | `app/report/transit_alerts.py`: کرون هفتگی، فقط وزن ≥ 18، پنجرهٔ ۷ روز، حداکثر ۱ اعلان/هفته (جدول `transit_alert_log`)، احترام به `NotificationPrefs.transit_alerts` (جدید)، لینک مستقیم `/transits/{id}`، اسکریپت `scripts/transit_alerts_cron.py` (شنبه 07:10 تهران) | ۳ تست (انتخاب/prefs+ضدتکرار+لینک) |
| **B5** رفع وعدهٔ شکسته | `transit.html`: وعدهٔ «پلن‌های کامل و طلایی» → لینک محصول واقعی `/transits/{chart_id}`؛ `payment_result.html»: «به زودی» → «در صف تولید + خبر میدهیم» + دکمهٔ «مشاهدهٔ چارت و وضعیت گزارش»؛ گیت جدید: هر href قالبی باید به route واقعی بخورد (`test_all_internal_template_links_resolve`) | ۳ تست |

## نکتهٔ فنی

- ستون `transit_alerts` باید در DB واقعی هم ALTER شود: `ALTER TABLE notification_prefs ADD COLUMN transit_alerts BOOLEAN NOT NULL DEFAULT TRUE;` — در test DB انجام شد؛ **برای prod باید در migration بعدی بیاید** (A6 migration pipeline).
- ثبت کرون سیستم پس از حادثهٔ امنیتی خالی است؛ افزودن خط `10 7 * * 6 venv/bin/python scripts/transit_alerts_cron.py >> /var/log/transit_alerts.log 2>&1` نیازمند تأیید کاربر.

## وضعیت کلی پروژه (پلن HERMES-PLAN-v1)

| مرحله | بخشها | وضعیت |
|---|---|---|
| ۰ زیرساخت | Z1/E1/A1/C1/G1 | ✅ push شده |
| ۱ هستهٔ درآمد | A2→A7 | ✅ push شده |
| ۲ محصول گذر | B1→B5 | ✅ **push شده (این دور)** |
| ۳–۵ UI/RAG/اثبات | C/D/E/G | 🔜 بعدی |

## تست

- B-chunk کامل (B1→B5): **30 passed** در 2.48s ($0 — LLM ماک).
- کل سوئیت chunk-by-chunk در دور ۶: ~627 passed, 0 رگرسیون.
