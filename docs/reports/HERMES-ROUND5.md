# ZAYCHE — دور ۵ (پاسخ به بازبینی Opus R5) — ۱۴۰۴/۰۶/۰۱

## نتیجه: V1 تا V10 اجرا و راستی‌آزمایی شد؛ **CI واقعاً از مخزن سبز** (GitHub Actions run #1 → SUCCESS)؛ PR باز شد.

## راستی‌آزمایی Opus R5 (قبل از فیکس)
بازبین با اجرای واقعی تأیید کرد که W1 تا W10 دور ۴ (دور قبل) درست انجام شده
(۷۰۲ تست سبز، تست منفی گیت drift، راستی‌آزمایی CI از GitHub API، مرورگر Chromium روی صفحهٔ گذرها).
بقیّه همه سبز بود، جز **یک P0** که واقع باگ بود:

- **P0-1**: `scripts/drift_gate.sh:36` از `alembic check && echo "DRIFT-GATE: CLEAN"` استفاده می‌کرد.
  گذاشتنِ فرمانِ گیت در سمت چپِ `&&` آن را از `set -e` معاف می‌کند ⇒ وقتی drift بود، گیت **بی‌صدا رد** می‌شد
  و همه خیال می‌کردند کار می‌کند.

## فیکس‌ها

### گروه ۱ — فوری (گیت شکسته)
| ID | فیکس | وضعیت |
|---|---|---|
| V1 | `drift_gate.sh` → `if ! alembic check; then echo FAILED; exit 1; fi` | ✅ با تست منفی اثبات شد |
| V2 | جاروی هر `cmd && echo` در `scripts/*.sh` → هر گیت حالا `|| { exit 1; }` صریح دارد | ✅ |
| V3 | تست خودکار گیت drift (`tests/test_drift_gate_negative.py`) — مدل موقتی بدون مهاجرت ⇒ exit≠0 | ✅ |

### گروه ۲ — تکمیل fallback و تست‌ها
| ID | فیکس | وضعیت |
|---|---|---|
| V4 | media fallback واقعاً قابل خواندن: روت `GET /media/{key}` + تست رفت‌وبرگشت (`tests/test_media_fallback_r5.py`) | ✅ + ثبت در AUTHORIZATION-MATRIX |
| V5 | VAPID: به‌جای پذیرش 503، تست `skipif` اختصاصی | ✅ |
| V6 | share endpoint: 503 به‌جای 404 برای «رندرر در دسترس نیست» | ✅ |
| V7 | برند: allowlist فایل:خط (`scripts/brand_language_gate.py`) به‌جای chain substring ضعیف | ✅ + تست منفی |

### گروه ۳ — فروش صفحهٔ گذرها
| ID | فیکس | وضعیت |
|---|---|---|
| V8 | نمونهٔ تحلیل پولی به بالای صفحه (زیر CTA) آمد | ✅ با مرورگر 390px |
| V9 | بخش «۵ گذر مهمِ امسال» با مرتب‌سازی **سراسری weight** (`top_by_weight`) | ✅ + تست واحد ترتیب |
| V10 | ماه‌های جمع‌شونده (`<details>`)؛ فقط ماه جاری + ۲ ماه بعد باز | ✅ ارتفاع < 3000 |

## راستی‌آزمایی (همه با اجرا/مرورگر واقعی)

### گیت drift (AC-1 / V1 / V3)
- مدل موقتی بدون مهاجرت ⇒ `bash scripts/drift_gate.sh` → **exit=1** و «DRIFT-GATE: FAILED» ✅
- کد سالم ⇒ exit=0 و «DRIFT-GATE: CLEAN» ✅
- چنین سناریویی به‌صورت تست خودکار در `tests/test_drift_gate_negative.py` ثبت شد.

### هیچ گیت بی‌صدایی (AC-2 / V2)
`grep -rn '&& echo' scripts/*.sh` → هر مورد حالا «یا bare command زیر set -e، یا if-then-exit صریح» است ✅

### fallback رسانه کامل (AC-3 / V4)
حالت ألف: `upload_bytes` محلی می‌نویسد و `GET /media/{key}` همان بایت را برمی‌گرداند (تست رفت‌وبرگشت) ✅
(رفع «حالت سوم»: قبلاً می‌نوشت ولی هرگز خوانده نمی‌شد.)

### صفحهٔ گذرها می‌فروشد (AC-4 / V8+V9+V10)
با Chromium واقعی در 390px:
| معیار | قبل | بعد |
|---|---|---|
| نمونهٔ تحلیل | y≈4405 | **y=351** (در 1200px اول) ✅ |
| ارتفاع پیش‌فرض | 5439px | **2994px < 3000** ✅ |
| «مهم‌ترین‌ها» سراسری weight | — | ✅ بخش + تست واحد ترتیب |
| خطای صفحه / اسکرول افقی | — | 0 خطا / بدون اسکرول ✅ |

مدرک: `docs/reviews/evidence/r5-transit-fold-390-final.png` و `r5-transit-full-390-final.png`.

### CI سبز از مخزن (AC-5)
PR #1 (`claude/opus-review-r5-round4` → `main`) باز شد؛ GitHub Actions **run #32673129800**:
- **714 passed, 3 skipped, 51 warnings in 58.79s**، `DRIFT-GATE: CLEAN`، «All checks passed!» ⇒ **SUCCESS**
- لینک run#1: https://github.com/Mahdiyar-eth/chart-platform/actions/runs/32673129800
- لینک run#2 (بعد از کامیت docs): https://github.com/Mahdiyar-eth/chart-platform/actions/runs/32673355507 — SUCCESS
- لاگ: `docs/qa/CI-ROUND5-2026-08-23.log`

## کامیت‌های این دور (شاخهٔ claude/opus-review-r5-round4)
- `7bf42ea` — Group 1+2: drift gate fails on drift + strict gates; media fallback readable; VAPID/share/brand strict
- `31694c1` — Group 3: transit page sells (sample under CTA, global-weight '5 مهم', collapsible months)
- `a73f813` — docs: document new GET /media/{key} route in AUTHORIZATION-MATRIX
- `8da2fbb` — lint: ruff autofix (dropped unused imports)

## تست منفی‌های جدید (قانون «گیت را با شکست تست کن»)
- `test_drift_gate_negative.py` — گیت drift وقتی باید fail می‌شود
- `test_brand_gate_r5.py` — گیت برند وقتی خط غیرمجاز اضافه شود fail می‌شود
- `test_media_fallback_r5.py` — fallback رسانه رفت‌وبرگشت + traversal
- `test_transit_page_sort_r5.py` — ترتیب سراسری weight + باز شدن اولین ۳ ماه

## یادداشت
- `runtime_withdrawal_race.sh` یک خطای نحوی از پیشِ موجود دارد (غیر از گیت‌های ci.sh؛ خارج از حیطه).
- گیت authz (AUTHORIZATION-MATRIX) بعد از افزودن روت `/media` شکست؛ با ثبت روت در ماتریس رفع شد.
