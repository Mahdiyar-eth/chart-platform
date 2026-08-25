# ماتریس Authorization (ZAYCHE / زایچه) — audit r4 C8

**سطوح دسترسی:**
- **Public** — بدون هیچ گاردی (rate limit جداگانه)
- **Capability** — مالکیت چارت از طریق توکن capability (امضای HMAC) یا ورود کاربرِ مالک (`_owns_chart`)
- **User** — کوکی ورود معتبر (`get_current_user`)
- **Paid** — دسترسی پرداختی (سیناستری/اشتراک) — همیشه بالای Capability
- **Admin** — `_is_admin` (کوکی `chart_admin` + HMAC)

| Resource (route) | سطح | گارد در کد |
|---|---|---|
| `GET /sw.js` | Public | — (PWA) |
| `GET /liveness` | Public | — (ops heartbeat) |
| `GET /readiness` | Public | — (ops probe: DB+Redis+worker+R2+disk) |
| `GET /health` | Public | — (alias خوانی readiness) |
| `GET /` | Public | — |
| `GET /birth-form` | Public | — |
| `GET /chart/{chart_id}` | Capability | `_owns_chart` (توکن در URL/کوکی) |
| `GET /api/cities` | Public | — |
| `POST /api/charts` | Public | rate limit 20/min (B5) |
| `POST /api/subscribe` | Public |
| `GET /moon` | Public | SEO cluster index (no auth) |
| `GET /moon-in/{slug}` | Public | SEO moon-sign page (no auth) | G3 — رضایت صریح؛ rate limit مشترک |
| `GET /gift-guide` | Public | G3 — لندینگ لید مگنت |
| `GET /guide/download/{token}` | Capability | توکن یک‌بارمصع Subscriber |
| `GET /unsubscribe/{token}` | Capability | توکن لغو اشتراک (بدون لاگین، طبق حریم خصوصی) |
| `POST /api/charts/{chart_id}/report` | Capability | `_owns_chart` |
| `GET /api/charts/{chart_id}/preview` | Capability | `_owns_chart` |
| `GET /api/charts/{chart_id}/transit-year.svg` | Capability | `_owns_chart` |
| `GET /api/charts/{chart_id}/report` | Capability | `_owns_chart` |
| `GET /api/charts/{chart_id}/forecast` | Capability | `_owns_chart` (B3) |
| `POST /api/charts/{chart_id}/forecast/analyze` | Capability + User | `_owns_chart` + login؛ هزینهٔ transit_3m/transit_12m (B3) |
| `GET /transits/{chart_id}` | Capability | `_owns_chart` (صفحهٔ گذرها B3) |
| `GET /api/reports/{report_id}.docx` | Capability | `_owns_chart` |
| `GET /api/reports/{report_id}/pdf` | Capability | `_owns_chart` |
| `GET /api/reports/{report_id}/audio` | Capability | `_owns_chart` (C1) |
| `POST /api/reports/{report_id}/audio` | Capability | `_owns_chart` (H1.5 queue) |
| `GET /api/reports/{report_id}/audio-status` | Capability | `_owns_chart` (H1.5 poll) |
| `GET /api/share/{chart_id}.png` | Capability | `_owns_chart` |
| `GET /plans` | Public | — |
| `GET /payment/result` | Public/Page | صفحه پرداخت: `_owns_order` |
| `GET /api/plans` | Public | — |
| `POST /api/orders` | Capability (+User optional) | `_owns_chart` ×2 (سیناستری) |
| `POST /api/purchase` | Logged-in user | unified credit purchase (401 no-auth, 402 insufficient + packs) |
| `GET /api/credits/me` | Logged-in user | `get_current_user` (401 no-auth) |
| `GET /api/orders/{order_id}` | Capability | `_owns_order` |
| `GET /api/payments/verify` | Public | idempotent + state machine (B7) |
| `GET /sitemap.xml` | Public | — |
| `GET /robots.txt` | Public | — |
| `GET /synastry` | Public | — |
| `POST /api/synastry` | Public | rate limit |
| `POST /api/synastry/share` | Public | HMAC-signed guest link, rate limit (G7) |
| `POST /api/insight/share` | Public (auth optional) | HMAC-signed guest link; payload limit 120/400/40 (A8) |
| `GET /si/{token}` | Guest | HMAC-verified; headline/title only — no birth data; rate limit 30/60s (A8) |
| `GET /api/admin/kpi` | Admin | `_is_admin` (chart_admin cookie) — live KPI matrix (A7) |
| `GET /s/{token}` | Public | HMAC verify, rate limit (G7) |
| `POST /api/synastry/order` | Capability | `_owns_chart` |
| `POST /api/synastry/full` | Capability | `_owns_chart` |
| `POST /api/synastry/charts` | Public | rate-limit only — saves charts, no gate (R13) |
| `GET /api/synastry/access` | Paid/Capability | access check |
| `GET /design-system` | Dev/QA | 404 in prod (W1.4 styleguide) |
| `GET /api/notifications/prefs` | User | session cookie (G8) |
| `POST /api/notifications/prefs` | User | CSRF + validated ranges (G8) |
| `GET /api/consent` | User | session cookie, owner-only (G9) |
| `POST /api/track` | Public | anonymous funnel beacon (G1) — ثبت رویداد قیف بدون احراز |
| `GET /api/admin/flags` | Admin | `_is_admin` (G11) |
| `PUT /api/admin/flags/{name}` | Admin | `_is_admin` + audited (G11) |
| `GET /birth-chart/{slug}` | Public | flag-gated, static SEO (G12) |
| `GET /rectify` | Public | — |
| `POST /api/rectify` | Capability | `_owns_chart` |
| `GET /chat/{chart_id}` | Capability | `_owns_chart` |
| `GET /api/chat/access/{chart_id}` | Capability | 403 «دسترسی به این گفتگو ندارید» |
| `GET /api/chat/history/{chart_id}` | Capability | 403 (همان) |
| `POST /api/chat` | Capability | 403 (همان) + سهمیه اتمیک (A9) |
| `POST /api/chat/stream` | Capability | D4: SSE استریم — همان گاردها؛ سهمیه فقط پس از اولین توکن مصرف می‌شود |
| `GET /api/charts/{chart_id}/transits` | Capability | `_owns_chart` |
| `GET /transit/{chart_id}` | Capability | `_owns_chart` |
| `POST /api/v1/telegram/webhook` | Public | secret در URL + امضای تلگرام |
| `POST /api/v1/bale/webhook/{secret}` | Public | secret در URL |
| `POST /api/auth/otp/request` | Public | rate limit + هش OTP (P1-2) |
| `POST /api/auth/otp/verify` | Public | rate limit + هش OTP (P1-2) |
| `GET /api/push/vapid-public-key` | Public | کلید عمومی VAPID (503 اگر پیکربندی نشده) |
| `POST /api/push/subscribe`, `POST /api/push/unsubscribe` | User/Optional | ثبت/حذف اشتراک اعلان مرورگر؛ با ورود → اتصال به user |
| `GET /api/wallet` | User | موجودی کیف پول + کد دعوت (D3) |
| `GET /api/coupons/check` | Public | اعتبارسنجی کد تخفیف بدون مصرف (§13) — report_only با چک اولین گزارش |
| `POST /api/wallet/withdraw` | User | درخواست تسویه موجودی (وارد جدول ادمین) |
| `POST /api/admin/withdrawals/{wid}/resolve` | Admin | تأیید/رد درخواست تسویه + AuditLog |
| `GET /api/auth/me` | User | کوکی ورود |
| `POST /api/auth/logout` | User | کوکی ورود |
| `GET /account` | User | کوکی ورود |
| `GET /credits` | User | کوکی ورود — کیف اعتبار + تاریخچه (R2-X12) |
| `GET /orders` | User | کوکی ورود — سفارش‌های خود کاربر (R2-X13) |
| `GET /reports` | User | کوکی ورود — گزارش‌های چارت‌های خود کاربر (R2-X13) |
| `GET /account/login` | Public | rate limit |
| `GET /account/export` | User | owner-only JSON export (G1 — no secrets) |
| `GET /dashboard` | User | session cookie; hero + 8 cards (G15) |
| `POST /account/delete` | User | CSRF + cascade (C6) |
| `GET /privacy` | Public | — |
| `GET /terms` | Public | — |
| `GET /refund` | Public | — |
| `GET /disclaimer` | Public | — |
| `GET /contact` | Public | — |
| `GET /guide` | Public | — |
| `GET /about` | Public | — |
| `GET /faq` | Public | — |
| `GET /glossary` | Public | R.7/T2 — واژه‌نامهٔ ۶۰+ اصطلاح (F3) |
| `GET /learn` | Public | — |
| `GET /learn/{slug}` | Public | — |
| `GET /signs/{slug}` | Public | — |
| `GET /articles` | Public | — |
| `GET /articles/{slug}` | Public | — |
| `GET /sky` | Public | — |
| `GET /deep-report` | Public | Landing 2 — گزارش عمیق (§14) |
| `GET /self-discovery` | Public | Landing 3 — کاوش خودشناسی (§14) |
| `GET /sky-today` | Public | Landing 4 — آسمان امروز (§14) |
| `GET /admin/login` | Public | rate limit |
| `POST /admin/login` | Public | rate limit |
| `GET /admin/logout` | Public | — |
| `GET /admin` | Admin | `_is_admin` |
| `PUT /api/admin/plans/{plan_key}` | Admin | `_is_admin` |
| `POST /api/admin/coupons` | Admin | `_is_admin` |
| `GET /api/admin/coupons` | Admin | `_is_admin` |
| `GET /api/admin/prompts` | Admin | `_is_admin` |
| `POST /api/admin/prompts/{prompt_key}` | Admin |
| `POST /api/admin/credit-price/{action_key}` | Admin | admin-only (A7) |
| `POST /api/admin/credits/grant` | Admin | admin-only manual grant + AuditLog (A7) |
| `GET /api/admin/credit-report` | Admin | admin-only credit economy report (A7) | `_is_admin` |
| `POST /api/admin/orders/{order_id}/refund` | Admin | `_is_admin` |
| `POST /api/admin/orders/{order_id}/regenerate` | Admin | `_is_admin` |
| `GET /api/admin/llm-cost` | Admin | `_is_admin` |
| `GET /api/admin/stats` | Admin | `_is_admin` |
| `GET /api/admin/funnel` | Admin | `_is_admin` (G1) — داشبورد قیف |
| `GET /api/admin/secrets` | Admin | `_is_admin` |
| `POST /api/admin/secrets/{key}` | Admin | `_is_admin` |
| `POST /api/admin/secrets/{key}/reveal` | Admin | `_is_admin` |
| `POST /api/admin/llm/test` | Admin | `_is_admin` |
| `GET /api/admin/token-caps` | Admin | `_is_admin` (MASTER W14) |
| `POST /api/admin/token-caps/{product}` | Admin | `_is_admin` + audit (W14) |
| `GET /api/admin/cost-revenue` | Admin | `_is_admin` (W14) |
| `GET /solar/{chart_id}` | Owner | `_owns_chart` (MASTER W6) |
| `POST /api/solar/purchase` | Owner+Login | `_owns_chart` + credit spend (W6) |
| `GET /api/solar/{chart_id}` | Owner+9cr | `_owns_chart` + entitlement solar (W6) |
| `GET /api/solar/{chart_id}/teaser` | Owner | `_owns_chart` — free teaser (W6) |
| `GET /relocation/{chart_id}` | Owner | `_owns_chart` (MASTER W7) |
| `GET /api/relocation/{chart_id}` | Owner+6cr | `_owns_chart` + entitlement relocation (W7) |
| `POST /api/relocation/purchase` | Owner+Login | `_owns_chart` + credit spend (W7) |
| `GET /api/today/daily` | Owner | `_owns_chart` — free daily layer (W5) |
| `GET /api/explore/cards` | Public | none (catalog) |
| `GET /explore` | User | `get_current_user` + `_owns_chart` (or redirect) |
| `POST /api/explore/{card_key}` | User | `get_current_user` + `_owns_chart` + credit spend (atomic, 1 credit) |
| `GET /api/explore/history` | User | `get_current_user` (own rows) |
| `DELETE /api/explore/{exploration_id}` | User | `get_current_user` + row.user_id == user.id |
| `GET /today` | User | `get_current_user` + `_owns_chart` (or redirect) |
| `GET /api/today` | User | `get_current_user` + `_owns_chart` |
| `POST /api/today/reflection` | User (gold/monthly) | `get_current_user` + `_owns_chart` + `_today_plan_access == full` |
| `GET /api/subscriptions` | User | `get_current_user` + profile/chart chain (owner) |
| `POST /api/subscriptions/{id}/cancel` | User (owner) | `get_current_user` + chart→profile→user match |
| `GET /api/admin/health` | Admin | `_is_admin` (chart_admin cookie) |
| `GET /api/admin/content/articles` | Admin | `_is_admin` |
| `GET /api/admin/content/articles/{aid}` | Admin | `_is_admin` |
| `POST /api/admin/content/articles` | Admin | `_is_admin` |
| `PUT /api/admin/content/articles/{aid}` | Admin | `_is_admin` |
| `DELETE /api/admin/content/articles/{aid}` | Admin | `_is_admin` |
| `GET /api/admin/content/articles/{aid}/revisions` | Admin | `_is_admin` |
| `POST /api/admin/content/articles/{aid}/restore/{version}` | Admin | `_is_admin` |
| `GET /api/admin/content/pages` | Admin | `_is_admin` |
| `GET /api/admin/content/pages/{key}` | Admin | `_is_admin` |
| `PUT /api/admin/content/pages/{key}` | Admin | `_is_admin` |
| `POST /api/admin/content/media` | Admin | `_is_admin` |
| `DELETE /api/admin/content/media/{mid}` | Admin | `_is_admin` |
| `GET /media/{key:path}` | Public | R.5/V4 — serves a CMS media object from the LOCAL MEDIA_DIR fallback; **only reachable when R2 is NOT configured** (dev/fresh CI). When R2 is configured (prod) it 404s and media is served via presigned URL instead, so no object is exposed. |

**نکات:**
- Capability token: HMAC-امضاشده (P0-1) — قابل اشتراک با لینک شخصی، قابل Revoke با تغییر `capability_salt`.
- Admin کوکی: `chart_admin` (امضا با `_ADMIN_SECRET` جدا از کاربران).
- Webhooks: تلگرام از طریق `secret_token` ستشده؛ Bale فقط secret در URL.
- هر route جدید باید در این ماتریس + `tests/test_authz_matrix.py` ثبت شود (تست ساختاری فایل را میخواند).
