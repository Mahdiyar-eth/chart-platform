# گزارش فیکس ممیزی هشتم (V8-AUDIT) — پلتفرم زایچه

- **تاریخ:** پنجشنبه ۲۴ مرداد ۱۴۰۵ (2026-08-14)
- **منبع:** ممیزی دستی MaHDi (پس از V7) — ۱×P1 در Entitlement گزارش
- **نتیجهٔ راستیآزمایی:** ✅ ادعا درست بود
- **تستها:** 309 passed + 1 skipped (۳ اجرای متوالی پایدار)
- **migrations:** 15 → **16**

---

## F-17 (P1) — Entitlement گزارش: per-chart → per-report ✅

**ادعا (ممتاز):** `_report_gate()` فقط چک میکرد «هر Order پرداختشدهای برای
همین chart هست» — نه اینکه آن Order متعلق به همین report باشد. سناریوی نشت:

1. خرید GOLD → گزارش GOLD ساخته میشود (order.report_id = گزارش)
2. GOLD ریفاند → گزارش GOLD هنوز موجود
3. خرید BASIC روی همان chart → یک paid order جدید روی chart
4. `_report_gate()` میدید «paid order هست» → **گزارش GOLD ریفاندشده دوباره
   دانلودپذیر میشد** (PDF + DOCX + audio — همه از همین gate)

**راستیآزمایی:** ✅ دقیقاً درست. کد قبلی:
```python
select(Order).where(Order.chart_id == rep.chart_id, Order.status == "paid")
```

**فیکس:**
```python
select(Order).where(Order.report_id == rep.id, Order.status == "paid")
```
Entitlement حالا **per-report** است: فقط order ای که صاحب همان گزارش است
(`orders.report_id = reports.id`) و paid است، دانلود را مجاز میکند.

**Backfill (migration 435333592075):** گزارشهای legacy (ساختهشده قبل از
معرفی linkage) که order.report_id نال دارند، به تنها paid order همان chart
لینک شدند — اما فقط وقتی دقیقاً یک گزارش orphan برای آن chart وجود دارد
(محافظهکارانه؛ حالتهای مبهم دستی میمانند و fail-closed یعنی locked).

**اثبات:**
- `test_refunded_report_stays_locked_after_new_purchase` — دقیقاً سناریوی
  ممیز: GOLD paid → دانلود ✓؛ ریفاند → دانلود ✗؛ خرید BASIC → گزارش GOLD
  قدیمی **still locked** ✗ و گزارش BASIC جدید دانلودپذیر ✓
- prod: ۳ گزارش موجود — گزارش واقعی خرید لینک شد (fb6b8118 ← order paid)؛
  دو گزارش تستی بدون پشتوانه locked ماندند (درست)

---

## وضعیت کامل چرخهٔ ممیزی (V5 → V8)

| دور | یافته | Severity | وضعیت |
|---|---|---|---|
| v5 | F-01 برداشت بدون reserve | P0 | ✅ |
| v5 | F-02 wallet double-spend | P0 | ✅ |
| v5 | F-03..F-09 (۷ مورد) | P1 | ✅ |
| v5 | F-10 referral wallet | P2 | ✅ |
| v6 | F-11 race ساخت برداشت | P0 | ✅ |
| v6 | F-12..F-14 | P1 | ✅ |
| v7 | F-15 race resolve ادمین | P0 | ✅ |
| v7 | F-16 audit fallback | P2 | ✅ |
| v8 | **F-17 entitlement گزارش** | **P1** | ✅ |

- **P0 باقیمانده: صفر**
- **P1 باقیمانده: صفر** (هر ۱۱ مورد بسته شد)
- تستها: 294 → **309**
- migrations: 14 → **16**
