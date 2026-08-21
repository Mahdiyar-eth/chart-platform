#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1: replace native alert(...) with showToast(msg, ok) across ZAYCHE templates.
Exact-string replacement, count-verified per instance. Persian preserved."""
import io, os, sys
D = "/root/chart-platform/app/templates"

# (file, old, new, expect_count)  count=-1 => replace_all, -2 => one of several
JOBS = [
 ("explore.html", 'alert("اول یک چارت بساز");', 'showToast("اول یک چارت بساز", false);', 1),
 ("explore.html", 'alert(e.message)', 'showToast(e.message, false)', 1),
 ("plans.html", "alert(j.detail || 'خطا در ایجاد سفارش');", "showToast(j.detail || 'خطا در ایجاد سفارش', false);", 1),
 ("plans.html", "alert('خرید با موجودی کیف پول انجام شد ✅ گزارش در حال تولید است.');", "showToast('خرید با موجودی کیف پول انجام شد ✅ گزارش در حال تولید است.', true);", 1),
 ("plans.html", "alert('ارتباط با سرور برقرار نشد');", "showToast('ارتباط با سرور برقرار نشد', false);", 1),
 ("rectify.html", "alert('شهر را از لیست انتخاب کن');", "showToast('شهر را از لیست انتخاب کن', false);", 1),
 ("rectify.html", "alert('حداقل ۲ رویداد با تاریخ کامل لازم است');", "showToast('حداقل ۲ رویداد با تاریخ کامل لازم است', false);", 1),
 ("rectify.html", "alert(d.detail || 'خطا');", "showToast(d.detail || 'خطا', false);", 1),
 ("synastry.html", "alert('شهرها را از لیست انتخاب کن');", "showToast('شهرها را از لیست انتخاب کن', false);", 1),
 ("synastry.html", "alert(d.detail || 'خطا');", "showToast(d.detail || 'خطا', false);", 2),
 ("synastry.html", "alert('لینک نتیجه کپی شد: می‌توانی برای طرف مقابل بفرستی.');", "showToast('لینک نتیجه کپی شد: می‌توانی برای طرف مقابل بفرستی.', true);", 1),
 ("synastry.html", "alert(d.detail || 'خطا در ایجاد سفارش');", "showToast(d.detail || 'خطا در ایجاد سفارش', false);", 1),
 ("account.html", "alert(r.ok ? 'درخواست تسویه ثبت شد ✅ پس از بررسی ادمین، مبلغ واریز می‌شود.' : (j.detail || 'خطا'));", "showToast(r.ok ? 'درخواست تسویه ثبت شد ✅ پس از بررسی ادمین، مبلغ واریز می‌شود.' : (j.detail || 'خطا'), r.ok);", 1),
 # admin.html — alert -> showToast
 ("admin.html", "alert('ذخیره شد ✓ (v' + (r.version || 'new') + ')');", "showToast('ذخیره شد ✓ (v' + (r.version || 'new') + ')', true);", 1),
 ("admin.html", "catch(e) { alert('خطا: ' + e.message); }", "catch(e) { showToast('خطا: ' + e.message, false); }", 3),
 ("admin.html", "return alert('extra JSON نامعتبر است');", "return showToast('extra JSON نامعتبر است', false);", 1),
 ("admin.html", "alert('ذخیره شد ✓'); cmsPages();", "showToast('ذخیره شد ✓', true); cmsPages();", 1),
 ("admin.html", "if (!f) return alert('فایلی انتخاب نشده');", "if (!f) return showToast('فایلی انتخاب نشده', false);", 1),
 ("admin.html", "if (j.ok) alert('ذخیره شد — بعد از ریاستارت سرویس برای سکشن‌های جدید اعمال می‌شود');", "if (j.ok) showToast('ذخیره شد — بعد از ریاستارت سرویس برای سکشن‌های جدید اعمال می‌شود', true);", 1),
 ("admin.html", "else alert('خطا: ' + (j.detail || 'نامشخص'));", "else showToast('خطا: ' + (j.detail || 'نامشخص'), false);", 6),
 ("admin.html", "if (j.ok) alert('ذخیره شد — بعد از ریاستارت سرویس اعمال می‌شود');", "if (j.ok) showToast('ذخیره شد — بعد از ریاستارت سرویس اعمال می‌شود', true);", 1),
 ("admin.html", "if (j.ok) { alert('در صف تولید قرار گرفت (گزارش ' + j.report_id.slice(0,8) + ')'); location.reload(); }", "if (j.ok) { showToast('در صف تولید قرار گرفت (گزارش ' + j.report_id.slice(0,8) + ')', true); location.reload(); }", 1),
 ("admin.html", "if (!content) return alert('متن خالی است');", "if (!content) return showToast('متن خالی است', false);", 1),
 ("admin.html", "if (j.ok) { alert('نسخه ' + j.version + ' ذخیره شد'); location.reload(); }", "if (j.ok) { showToast('نسخه ' + j.version + ' ذخیره شد', true); location.reload(); }", 1),
 ("admin.html", "if (!r.ok) alert(d.detail || 'خطا');", "if (!r.ok) showToast(d.detail || 'خطا', false);", 1),
 ("admin.html", "alert(v.trim() ? 'ذخیره شد ✅ — سرویس را ریاستارت کنید تا اعمال شود' : 'پاک شد — به مقدار محیطی برمی‌گردد');", "showToast(v.trim() ? 'ذخیره شد ✅ — سرویس را ریاستارت کنید تا اعمال شود' : 'پاک شد — به مقدار محیطی برمی‌گردد', v.trim());", 1),
 ("admin.html", "if (j.ok) { alert('پاک شد ✅'); location.reload(); }", "if (j.ok) { showToast('پاک شد ✅', true); location.reload(); }", 1),
]

errors = []
for fn, old, new, count in JOBS:
    p = os.path.join(D, fn)
    txt = io.open(p, encoding="utf-8").read()
    n = txt.count(old)
    if count == -2:
        if n < 1:
            errors.append(f"{fn}: expected >=1 of {old!r}, got {n}")
            continue
    elif n != count:
        errors.append(f"{fn}: expected {count} of {old!r}, got {n}")
        continue
    txt = txt.replace(old, new)
    io.open(p, "w", encoding="utf-8").write(txt)
    print(f"OK {fn}: {old[:40]!r} -> {new[:40]!r} ({n})")

if errors:
    print("\nERRORS:")
    for e in errors: print(" -", e)
    sys.exit(1)
print("\nAll alert->showToast replacements applied.")
