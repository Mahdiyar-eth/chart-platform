# AUDIT REPORT — Chunk 3: Security & Payment

## FINDINGS

---

### 1. OTP Dev Mode Leaks Code in Production if Misconfigured
**[SEV: critical — P0]**
**File:** `app/auth.py:36`

**Evidence:**
```python
_OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "false").lower() == "true"
```
There is no guard preventing `OTP_DEV_MODE=true` in production. If an operator accidentally sets this env var in prod, OTP codes are logged in plaintext (line 101: `log.info("OTP DEV MODE: code for %s = %s", phone, code)`) AND returned in the HTTP response (line 117: `out["dev_code"] = code`), completely bypassing authentication.

**Fix:**
```python
_OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "false").lower() == "true"
if IS_PROD and _OTP_DEV_MODE:
    raise RuntimeError("OTP_DEV_MODE=true is forbidden in production (APP_ENV=prod)")
```

---

### 2. Phone Number Input Not Validated — OTP Abuse / Injection
**[SEV: major — P1]**
**File:** `app/auth.py:107,125`

**Evidence:**
```python
def request_otp(phone: str) -> dict:
    phone = phone.strip()
    # ... immediately used as Redis key and sent to Kavenegar
```
No validation of phone format (e.g., must be `09xxxxxxxxx` or `+989xxxxxxxxx`). An attacker can:
- Send OTPs to arbitrary international numbers (cost leak via Kavenegar).
- Use crafted strings as Redis keys (e.g., containing newlines or colons) for key confusion.
- Abuse rate limits by varying whitespace/prefix variants of the same number.

**Fix:** Add a strict regex validator at the top of `request_otp` and `verify_otp`:
```python
import re
_PHONE_RE = re.compile(r"^(?:\+98|0)9\d{9}$")
def _normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if not _PHONE_RE.match(phone):
        raise ValueError("شماره موبایل نامعتبر است")
    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    return phone
```

---

### 3. `set_user_cookie` Returns a Redirect, Ignoring Caller Context
**[SEV: mod — P2]**
**File:** `app/auth.py:78-82`

**Evidence:**
```python
def set_user_cookie(request: Request, user_id: str):
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse("/account", status_code=303)
    resp.set_cookie(USER_COOKIE, _user_cookie_value(user_id), httponly=True,
                    max_age=30 * 24 * 3600, samesite="lax", secure=True)
    return resp
```
This always redirects to `/account` with a 303. For API-based OTP verify (JSON clients, bot flows), this is wrong — the caller cannot set a cookie on a JSON response. The function also takes `request` but never uses it.

**Fix:** Separate cookie-setting from response creation; let the endpoint decide the response type.

---

### 4. CSRF Origin Check Allows Bypass When `Origin` Header Is Absent
**[SEV: major — P1]**
**File:** `app/security.py:138-143`

**Evidence:**
```python
def csrf_protect(request: Request) -> bool:
    if request.method in SAFE_METHODS:
        return True
    origin = request.headers.get("origin")
    if not origin:
        # Non-browser clients (curl, bots, server-to-server) — allow
        return True
```
Browsers may omit the `Origin` header on same-origin navigational POSTs (e.g., `<form>` submissions in some older browsers, or cross-origin requests downgraded by privacy extensions). A CSRF attack using `<form method=POST>` from a cross-origin page in a browser that strips `Origin` bypasses this entirely. The double-submit CSRF token (`verify_csrf`) exists but is not enforced in the middleware — it's only a helper function.

**Fix:** For state-changing endpoints that use session cookies (OTP verify, payment, admin), enforce the double-submit CSRF token check in the middleware or at the endpoint level. At minimum, also check `Referer` when `Origin` is absent:
```python
if not origin:
    referer = request.headers.get("referer", "")
    if referer:
        from urllib.parse import urlparse
        return urlparse(referer).netloc == host
    # No origin AND no referer: block for cookie-authenticated endpoints
    return True  # keep for API-token-only endpoints
```

---

### 5. Coupon Atomic Reservation Uses Raw SQL Without ORM Sync
**[SEV: major — P1]**
**File:** `app/payment/orders.py:83-89`

**Evidence:**
```python
reserved = session.exec(_text(
    "UPDATE coupons SET used_count = used_count + 1 "
    "WHERE id = :cid AND used_count < max_uses RETURNING id"
), params={"cid": coupon_row.id}).first()
if not reserved:
    raise ValueError("کد تخفیف مصرف شده")
session.refresh(coupon_row)
```
The raw SQL `UPDATE ... RETURNING` is correct for atomicity, but `session.refresh(coupon_row)` may not see the updated value if the session's identity map is stale (SQLAlchemy caches the ORM object). More critically, the `_text` import is done inline from `sqlalchemy` but `text` is also imported at the top from `sqlalchemy`. This is fine functionally but confusing. The real issue: if the DB is PostgreSQL, this works; if SQLite (dev/tests), `RETURNING` is only supported in SQLite ≥ 3.35. Tests on older SQLite will silently fail.

**Fix:** Add `session.expire(coupon_row)` before `session.refresh(coupon_row)`, and document the SQLite 3.35+ requirement.

---

### 6. Self-Import Circular Reference Risk
**[SEV: mod — P2]**
**File:** `app/payment/orders.py:76`

**Evidence:**
```python
if coupon_row.report_only:
    from app.payment.orders import REPORT_PLANS
```
The module imports from itself (`app.payment.orders`). While Python handles this because `REPORT_PLANS` is defined later in the same module, this is fragile and confusing. If the constant is moved or the module is refactored, this breaks.

**Fix:** Reference `REPORT_PLANS` directly (it's in the same module scope) — remove the self-import:
```python
if plan_key not in REPORT_PLANS:
```

---

### 7. `pay_order_with_balance` Missing Credit-Pack Grant
**[SEV: major — P1]**
**File:** `app/payment/orders.py:401-420`

**Evidence:**
```python
def pay_order_with_balance(session: Session, order: Order, user: User | None) -> bool:
    ...
    if order.plan_key == "monthly":
        activate_subscription(session, order)
    if order.plan_key in REPORT_PLANS and order.chart_id and not order.report_id:
        rep = Report(...)
        ...
```
When `order.plan_key` is in `CREDIT_PACKS` (e.g., `"credit3"`, `"credit6"`, `"credit12"`), the balance-pay path does **not** call `grant_credits(session, order)`. The user pays from their wallet but never receives the credits. The `yearly` subscription plan is also not handled (only `monthly`).

**Fix:**
```python
if order.plan_key in SUBSCRIPTION_PLANS:
    activate_subscription(session, order)
if order.plan_key in CREDIT_PACKS:
    grant_credits(session, order)
if order.plan_key in REPORT_PLANS and order.chart_id and not order.report_id:
    ...
```

---

### 8. Zarinpal Verify Does Not Validate Amount Server-Side Against Order
**[SEV: critical — P0]**
**File:** `app/payment/zarinpal.py:73-86`

**Evidence:**
```python
def verify(self, authority: str, amount_rial: int) -> dict:
    payload = {
        "merchant_id": self.merchant_id,
        "authority": authority,
        "amount": amount_rial,
    }
```
The `verify` method accepts `amount_rial` as a parameter. If the **caller** passes a wrong amount (e.g., from user input or a tampered callback), Zarinpal will reject it — but the caller's responsibility to pass the correct order amount is not enforced here. This is correct at the client level (Zarinpal does server-side amount matching), but the **calling code is not shown in this chunk**. If the verify endpoint reads the amount from the request instead of the DB order, it's a payment bypass.

**Fix:** Document clearly (or assert) that `amount_rial` MUST come from `order.amount_rial` in the DB, never from the callback query string. Add a guard:
```python
def verify(self, authority: str, amount_rial: int) -> dict:
    assert amount_rial > 0, "amount must be positive and from DB"
```

---

### 9. Presigned URL Expiry Allows 30-Minute Window for Leaked Links
**[SEV: mod — P2]**
**File:** `app/storage.py:93`

**Evidence:**
```python
def presigned_url(key: str, expires: int = 1800) -> str | None:
```
30 minutes is reasonable. **This is correct.** The docstring accurately describes the trade-off. No issue.

---

### 10. Bot Webhook Secret Not Verified for Bale
**[SEV: major — P1]**
**File:** `app/bots/handler.py:30-31`

**Evidence:**
```python
TELEGRAM_WEBHOOK_SECRET = get_secret("telegram_webhook_secret", "TELEGRAM_WEBHOOK_SECRET", "")
# No BALE_WEBHOOK_SECRET usage visible in handle_update
```
`BALE_WEBHOOK_SECRET` is defined in the secret catalog (`app/secret_store.py`) but is never loaded or checked in `handler.py`. The `handle_update` function processes any incoming JSON without verifying the webhook signature for either platform. For Telegram, the `X-Telegram-Bot-Api-Secret-Token` header should be checked. For Bale, similarly. Without this, anyone who discovers the webhook URL can inject fake updates (send messages as the bot, trigger payments, etc.).

**Fix:** In the webhook endpoint (not shown but implied), verify:
```python
if platform == "telegram":
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(token, TELEGRAM_WEBHOOK_SECRET):
        return JSONResponse({"error": "unauthorized"}, 403)
```

---

### 11. Bot Creates Charts Without User Authentication
**[SEV: mod — P2]**
**File:** `app/bots/handler.py:222-230`

**Evidence:**
```python
row = Chart(chart_json=chart.chart_json,
            access_token=secrets.token_urlsafe(32))
s.add(row)
```
Charts created via the bot have no `profile_id` or `user_id`. This is by design (anonymous chart creation), but when the bot then creates a subscription order with `new_user_id=str(chat_id)` (line 316), the `chat_id` (an integer) is used as a user ID string. This is not a real `User.id` from the database — it's a Telegram chat ID. This means:
- `order.user_id` points to a non-existent User record.
- Coupon `report_only` checks against `new_user_id` will never find prior orders.
- Referral self-referral checks compare against a fake user ID.

**Fix:** Either create/lookup a proper `User` record for bot users (keyed by `platform:chat_id`), or explicitly handle the bot flow separately in `create_order`.

---

### 12. `_client()` Creates a New boto3 Client on Every Call
**[SEV: mod — P2]**
**File:** `app/storage.py:42-50`

**Evidence:**
```python
def _client():
    if not configured():
        return None
    import boto3
    endpoint = R2_ENDPOINT if R2_ENDPOINT.startswith("http") else f"https://{R2_ENDPOINT}"
    return boto3.client(
        "s3", endpoint_url=endpoint, ...)
```
Every upload/download/presign call creates a new boto3 S3 client. boto3 client creation involves credential resolution, session setup, and HTTP connection pool initialization. Under load (many report downloads), this is a performance issue and potential resource leak.

**Fix:** Cache the client at module level or use a singleton pattern:
```python
_s3_client = None
def _client():
    global _s3_client
    if _s3_client is None and configured():
        import boto3
        _s3_client = boto3.client(...)
    return _s3_client
```

---

### 13. `reveal_secret` Has No Access Control at the Function Level
**[SEV: major — P1]**
**File:** `app/secret_store.py:195-200`

**Evidence:**
```python
def reveal_secret(key: str) -> str:
    """Admin-only: decrypted current value (DB first, else env)."""
    val = _db_secret(key)
    ...
    return val or ""
```
The docstring says "Admin-only" but the function itself has no authorization check. If the admin endpoint that calls this doesn't properly gate access (not shown in this chunk), any caller can decrypt all secrets. The function should at minimum log the access.

**Fix:** Add audit logging inside `reveal_secret`, and ensure the calling endpoint is verified in the routes chunk:
```python
def reveal_secret(key: str, admin: str = "unknown") -> str:
    log.warning("SECRET REVEAL: key=%s by=%s", key, admin)
    ...
```

---

### 14. Fernet Key Derivation Uses Raw SHA-256 (No Stretching)
**[SEV: mod — P2]**
**File:** `app/secret_store.py:100-103`

**Evidence:**
```python
def _derive_fernet_key(master: str) -> bytes:
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)
```
SHA-256 is not a key derivation function — it has no salt, no iterations, no memory-hardness. If the master key has low entropy (e.g., a human-chosen passphrase), this is trivially brutable. For a `token_urlsafe(32)` auto-generated key this is acceptable, but the env var `SECRETS_MASTER_KEY` could be anything.

**Fix:** Use PBKDF2 or HKDF:
```python
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
def _derive_fernet_key(master: str) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"zayche-secrets-v1", info=b"fernet")
    return base64.urlsafe_b64encode(hkdf.derive(master.encode("utf-8")))
```

---

### 15. In-Memory Secret Cache Never Expires
**[SEV: mod — P2]**
**File:** `app/secret_store.py:137-138`

**Evidence:**
```python
_cache: dict[str, str] = {}
```
The cache is only cleared by explicit `invalidate_cache()` calls. If an admin updates a secret via the DB directly (not through `set_secret`), or if another worker updates it, this worker's cache is stale forever. The docstring acknowledges this ("Module-level constants read at import still need a restart") but the in-process cache has no TTL.

**Fix:** Add a TTL-based cache (e.g., 60 seconds) or use Redis pub/sub for cross-worker invalidation.

---

### 16. `withdraw_request` Catches All Exceptions Silently on Unique Violation
**[SEV: mod — P2]**
**File:** `app/payment/orders.py:316-319`

**Evidence:**
```python
    except Exception:  # noqa: BLE001 — partial unique index (concurrent pending)
        session.rollback()  # undo the debit too
        return False
```
This catches ALL exceptions, not just `IntegrityError`. A programming error, connection failure, or serialization error would be silently swallowed, and the user would see a generic "failed" with no diagnostics. The debit rollback is correct, but the broad catch masks bugs.

**Fix:**
```python
    except IntegrityError:
        session.rollback()
        return False
```

---

### 17. `reward_referral` Cycle Detection Has Off-by-One / Incomplete Logic
**[SEV: mod — P2]**
**File:** `app/payment/orders.py:254-268`

**Evidence:**
```python
chain: set[str] = {buyer.id}
cur = session.get(_U, ev.referrer_user_id)
hops = 0
while cur and cur.id not in chain and hops < 8:
    chain.add(cur.id)
    prev = session.exec(select(ReferralEvent).where(
        ReferralEvent.new_user_id == cur.id,
        ...
    )).first()
    cur = session.get(_U, prev.referrer_user_id) if (prev and prev.referrer_user_id) else None
    hops += 1
if cur and cur.id in chain:
    ev.status = "voided"
```
The loop starts with `cur = referrer`. If `referrer.id == buyer.id` (direct self-referral), the while condition `cur.id not in chain` is immediately false (since `buyer.id` is in `chain`), so the loop body never executes, and the post-loop check `cur and cur.id in chain` correctly catches it. This is actually correct for the self-referral case. For longer cycles (A→B→A), the logic also works. **This is correct.**

---

### 18. `answer_callback` Called Twice in Some Paths
**[SEV: mod — P2]**
**File:** `app/bots/handler.py:296, 338`

**Evidence:**
```python
async def _handle_callback(cb: dict, platform: str) -> None:
    ...
    elif data.startswith("zodiac_"):
        ...
        await answer_callback(cb_id, platform=platform)  # line ~296
        await _compute_and_send_chart(...)
    ...
    if cb_id:  # line ~338
        await answer_callback(cb_id, platform=platform)  # SECOND call
```
For `zodiac_*` callbacks, `answer_callback` is called twice — once inside the branch and once at the end of the function. Telegram's API returns an error for the second call ("query is too old" or "query already answered"), which is logged as a warning. Not a security issue but generates noise.

**Fix:** Add `return` after each branch, or restructure so the final `answer_callback` is in an `else` block.

---

## VERDICT

| Dimension | Rating | Notes |
|---|---|---|
| **Authentication (OTP)** | ✅ Good | Hashed codes in Redis, TTL, attempt limits, HMAC cookies with constant-time compare. P0 fix needed for dev-mode guard in prod. |
| **Session Security** | ✅ Good | HMAC-SHA256 signed cookies, `httponly`, `secure`, `samesite=lax`. Fail-closed `AUTH_SECRET` in prod. |
| **CSRF** | ⚠️ Incomplete | Origin check is bypassable when header absent. Double-submit token exists but isn't enforced in middleware. |
| **Rate Limiting** | ✅ Good | Redis-backed in prod (fail-closed), per-IP and per-phone limits, mandatory Redis enforcement. |
| **Secret Management** | ✅ Good | Fernet encryption at rest, masked admin UI, fail-closed master key in prod. Minor: no KDF stretching, no cache TTL. |
| **Payment (Zarinpal)** | ✅ Good | Idempotent verify (101 handling), structured error codes, sandbox/prod separation. |
| **Payment (Orders)** | ⚠️ Has Gaps | Atomic coupon reservation, atomic balance debit, CAS withdrawal resolution — all solid. **But**: credit-pack and yearly subscription not granted in wallet-pay path (P1). |
| **Referral System** | ✅ Good | Self-referral blocked, cycle detection, atomic rewards, voiding logic. |
| **Storage (R2)** | ✅ Good | Fail-closed in prod, 30-min presigned URLs, namespaced keys. Minor: client not cached. |
| **Bot Security** | ⚠️ Incomplete | Webhook signature not verified. Bot user identity conflated with Telegram chat_id (not a real DB user). |
| **Launch Readiness** | ⚠️ Not Ready | Fix P0 (OTP dev-mode in prod guard) and P1s (phone validation, CSRF, credit-pack grant, webhook auth) before launch. |