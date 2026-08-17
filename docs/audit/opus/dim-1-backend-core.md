# AUDIT REPORT — CHUNK 1: Backend Core

## FINDINGS

---

### 1. [SEV: critical — P0] `readiness()` calls `asyncio.run()` inside a sync endpoint that may already have a running event loop

**File:** `app/main.py`, readiness endpoint (~line 120)

**Evidence:**
```python
_asyncio.run(_arq_pool())
```

**Problem:** In production under uvicorn (which runs its own asyncio loop), `asyncio.run()` inside a sync endpoint raises `RuntimeError: This event loop is already running`. This means the `/readiness` probe will 503 on the worker check even when the worker is healthy, or crash entirely. The same pattern appears in `_enqueue_report()` (~line 310):
```python
asyncio.run(_enqueue_async(report_id))
```
and `_enqueue_audio()` (~line 620).

**Fix:** Use `asyncio.get_event_loop().run_until_complete()` or, better, make these endpoints `async` and `await` the coroutine directly. For the sync `_enqueue_report`, use a dedicated sync Redis check or `anyio.from_thread.run()`.

---

### 2. [SEV: critical — P0] `readiness()` creates a NEW synchronous `redis.Redis` connection per call and never closes it

**File:** `app/main.py`, readiness endpoint (~line 115)

**Evidence:**
```python
import redis as _r
if not _r.Redis.from_url(_REDIS_URL, decode_responses=True).ping():
```

**Problem:** Connection is never `.close()`d — under load (k8s probes every 10s) this leaks file descriptors until the process hits ulimit. Also, this is a synchronous blocking call inside what could be an async worker thread.

**Fix:** Wrap in a context manager or explicitly close:
```python
r = _r.Redis.from_url(_REDIS_URL, decode_responses=True)
try:
    if not r.ping(): raise RuntimeError("no pong")
finally:
    r.close()
```

---

### 3. [SEV: critical — P0] `_arq_pool()` global pool is created but also used in `readiness()` via `asyncio.run()`, binding it to a throwaway loop — subsequent async calls on the real loop fail

**File:** `app/main.py`, `_arq_pool()` (~line 300)

**Evidence:**
```python
async def _arq_pool():
    global _ARQ_POOL
    if _ARQ_POOL is None:
        from arq import create_pool
        _ARQ_POOL = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
    return _ARQ_POOL
```

The `readiness()` endpoint calls `_asyncio.run(_arq_pool())` which creates a new event loop, binds the global `_ARQ_POOL` to it, then destroys the loop. Any subsequent use of `_ARQ_POOL` from the real uvicorn loop will raise "attached to a different loop". The code comments in `_enqueue_async` acknowledge this exact bug but `readiness()` still triggers it.

**Fix:** `readiness()` should NOT call `_arq_pool()`. Instead, do a simple Redis PING on the ARQ queue key, or create a throwaway pool inside `readiness()` and close it.

---

### 4. [SEV: critical — P0] `api_chart_preview` creates a new `redis_async` connection per call and may leak it on exception paths

**File:** `app/main.py`, `_cache_get()` / `_cache_set()` (~line 380-400)

**Evidence:**
```python
async def _cache_get() -> dict | None:
    try:
        r = redis_async.from_url(_REDIS_URL, decode_responses=True)
        raw = await r.get(cache_key)
        await r.aclose()
        ...
    except Exception:
        return None  # r.aclose() never called on exception between from_url and aclose
```

**Problem:** If `r.get()` raises, `r.aclose()` is skipped. Connection leak. This pattern repeats in `_cache_set()`.

**Fix:** Use `async with` or `try/finally`:
```python
r = redis_async.from_url(...)
try:
    raw = await r.get(cache_key)
finally:
    await r.aclose()
```

---

### 5. [SEV: major — P1] `seed_plans()` in `db.py` uses session `s` AFTER the `with Session(engine) as s:` block has exited

**File:** `app/db.py`, `seed_plans()` (~line 80-95)

**Evidence:**
```python
with Session(engine) as s:
    for item in catalog:
        ...
    s.commit()
# §13 — launch coupon LANCH20
c = s.exec(select(Coupon).where(Coupon.code == "LANCH20")).first()  # ← s is CLOSED here
if not c:
    ...
    s.exec(_text(...))
    s.commit()
```

The coupon seeding code runs OUTSIDE the `with Session(engine) as s:` context manager. `s` is closed/detached. This will raise `SessionError` or silently fail depending on SQLAlchemy version.

**Fix:** Move the coupon seeding inside the `with` block, or open a new session.

---

### 6. [SEV: major — P1] `_compute_and_save_chart` year validation allows Jalali years 1300-2100 and Gregorian years 1300-2100 — Gregorian year 1300 is nonsensical; Jalali year 2100 is nonsensical

**File:** `app/main.py`, `_compute_and_save_chart()` (~line 195)

**Evidence:**
```python
if year < 1300 or year > 2100:
    raise HTTPException(400, "year out of range")
```

This check doesn't distinguish between Jalali and Gregorian calendars. `validate_birth_fields` in `engine.py` correctly uses 1300-1405 for Jalali and 1900-2026 for Gregorian, but `_compute_and_save_chart` bypasses it entirely.

**Fix:** Call `validate_birth_fields(year, month, day, jalali=(calendar == "jalali"))` and raise on failure, or at minimum branch the range check by calendar.

---

### 7. [SEV: major — P1] `_dedupe_update` local fallback uses `set.pop()` which removes an ARBITRARY element (not the oldest)

**File:** `app/main.py`, `_dedupe_update()` (~line 730)

**Evidence:**
```python
if len(_seen_update_ids) >= _MAX_SEEN:
    _seen_update_ids.pop()  # set.pop() removes arbitrary element
_seen_update_ids.add(uid)
```

**Problem:** `set.pop()` removes an arbitrary element, not the oldest. A recently-processed update_id could be evicted, re-opening the dedup window and allowing duplicate processing. The comment says "drop oldest, never clear all" but the code doesn't do that.

**Fix:** Use `collections.OrderedDict` or a `deque` to maintain insertion order and evict the oldest.

---

### 8. [SEV: major — P1] `api_share_card` docstring is placed AFTER the rate-limit check — the function signature's docstring is the rate-limit block

**File:** `app/main.py`, `api_share_card()` (~line 460)

**Evidence:**
```python
@app.get("/api/share/{chart_id}.png")
def api_share_card(chart_id: str, request: Request, ...):
    if not _rate_limit(...):
        raise HTTPException(429, ...)
    """OG share card (1200×630)..."""  # ← this is a string literal, NOT a docstring
```

**Problem:** The docstring is after executable code, so it's just a dead string expression, not the function's `__doc__`. Minor but indicates copy-paste error. No functional impact.

**Fix:** Move the docstring to immediately after `def api_share_card(...):`

---

### 9. [SEV: major — P1] IDOR risk: `api_create_order` allows creating orders for charts the user doesn't own when `plan_key` is in `CREDIT_PACKS` and `chart_id` is None

**File:** `app/main.py`, `api_create_order()` (~line 430)

**Evidence:**
```python
if not chart and plan_key not in CREDIT_PACKS:
    raise HTTPException(400, ...)
```

When `plan_key` is a credit pack AND `chart_id` is provided but not owned, the ownership check passes because `chart` is None (chart_id not found returns 404 above). However, if `chart_id` is omitted for a credit pack, `chart` is None and the ownership check `if chart and not _owns_chart(...)` is skipped entirely. This is correct behavior for credit packs (no chart needed), but the `user_id` passed to `create_order` comes from `get_current_user(request)` which could be None for anonymous users — credits would be granted to no one.

**Fix:** For credit packs, require authentication:
```python
if plan_key in CREDIT_PACKS and not user:
    raise HTTPException(401, "برای خرید اعتبار ابتدا وارد شوید")
```

---

### 10. [SEV: major — P1] `api_payment_verify` exposes internal exception message to the user in the `order.error` field

**File:** `app/main.py`, payment verify (~line 530)

**Evidence:**
```python
order.error = f"تأیید پرداخت موقتاً ناموفق بود؛ صفحه را رفرش کنید: {str(e)[:150]}"
```

**Problem:** `str(e)` from a network/timeout exception can contain internal hostnames, IP addresses, connection strings, or stack details. This is stored in `order.error` and potentially displayed to the user via `payment_result.html` or `api_order_status`.

**Fix:** Log the full exception server-side; store only a sanitized message:
```python
order.error = "تأیید پرداخت موقتاً ناموفق بود؛ صفحه را رفرش کنید"
```

---

### 11. [SEV: major — P1] `account_delete` cascade doesn't delete `LLMRun` rows where `user_id` matches (only deletes by `report_id`)

**File:** `app/main.py`, `account_delete()` (~line 870)

**Evidence:**
```python
for run in session.exec(select(LLMRun).where(LLMRun.report_id == rep.id)).all():
    session.delete(run)
```

Chat-originated `LLMRun` rows have `report_id=None` and `user_id=profile.user_id`. These are never deleted. If `LLMRun.user_id` has a FK to `users.id`, deletion will fail with an IntegrityError.

**Fix:** Add after the chart loop:
```python
for run in session.exec(select(LLMRun).where(LLMRun.user_id == u.id)).all():
    session.delete(run)
```

---

### 12. [SEV: major — P1] `account_delete` doesn't delete `Exploration` rows — FK to `users.id` will block deletion

**File:** `app/main.py`, `account_delete()` (~line 860-920)

**Evidence:** The `Exploration` model has `user_id: str | None = Field(default=None, foreign_key="users.id")` but `account_delete` never queries/deletes Exploration rows.

**Fix:** Add before deleting the user:
```python
for exp in session.exec(select(Exploration).where(Exploration.user_id == u.id)).all():
    session.delete(exp)
```

---

### 13. [SEV: major — P1] `account_delete` doesn't delete `ConsentLog` rows — FK to `users.id`

**File:** `app/main.py` + `app/models.py`

**Evidence:** `ConsentLog` has `user_id: str = Field(foreign_key="users.id")`. Not deleted in `account_delete`.

**Fix:** Delete ConsentLog rows before deleting the user.

---

### 14. [SEV: major — P1] `account_delete` doesn't delete `NotificationPrefs` — PK is `user_id` with FK to `users.id`

**File:** `app/main.py` + `app/models.py`

**Evidence:** `NotificationPrefs` has `user_id: str = Field(primary_key=True, foreign_key="users.id")`.

**Fix:** Delete the NotificationPrefs row before deleting the user.

---

### 15. [SEV: major — P1] `account_delete` doesn't delete `PushSubscription` rows — FK to `users.id`

**File:** `app/main.py` + `app/models.py`

**Evidence:** `PushSubscription` has `user_id: str | None = Field(default=None, foreign_key="users.id")`.

**Fix:** Delete PushSubscription rows before deleting the user.

---

### 16. [SEV: major — P1] `account_delete` doesn't delete `CreditTransaction` rows — FK to `users.id`

**File:** `app/main.py` + `app/models.py`

**Evidence:** `CreditTransaction` has `user_id: str = Field(default=None, foreign_key="users.id")`.

**Fix:** Delete CreditTransaction rows before deleting the user.

---

### 17. [SEV: major — P1] `account_delete` doesn't delete `AuditLog` rows referencing the user

**File:** `app/main.py` — No FK constraint on AuditLog, so this won't block deletion, but audit logs containing user PII (phone, id) will persist after account deletion, violating GDPR/data-deletion expectations.

**Fix:** Either anonymize or delete AuditLog rows for the user.

---

### 18. [SEV: major — P1] `account_delete` doesn't delete `BotState` rows — no FK but orphaned data

**File:** `app/models.py` — `BotState` has no FK to users, but if the user had bot interactions, their `chat_id` data persists. Lower severity since no FK constraint blocks deletion.

---

### 19. [SEV: major — P1] Astrology math: element counting uses `sign_index % 4` which is WRONG

**File:** `app/astrology/engine.py`, ~line 230

**Evidence:**
```python
counts[["Fire", "Earth", "Air", "Water"][s % 4]] += 1
modalities[["Cardinal", "Fixed", "Mutable"][s % 3]] += 1
```

The standard astrological element mapping is:
- Aries(0)=Fire, Taurus(1)=Earth, Gemini(2)=Air, Cancer(3)=Water, Leo(4)=Fire...

`s % 4` gives: 0→Fire, 1→Earth, 2→Air, 3→Water, 4→Fire✓, 5→Earth✓, 6→Air✓, 7→Water✓, 8→Fire✓, 9→Earth✓, 10→Air✓, 11→Water✓

This is actually **correct** for the traditional element cycle. ✅

Modality: Cardinal(0,3,6,9), Fixed(1,4,7,10), Mutable(2,5,8,11). `s % 3` gives: 0→Cardinal✓, 1→Fixed✓, 2→Mutable✓, 3→Cardinal✓... This is also **correct**. ✅

**Retracted — no issue.**

---

### 20. [SEV: major — P1] `swe.set_sid_mode` called TWICE at module level — once in `engine.py` and once in `sky.py`

**File:** `app/astrology/engine.py` (~line 40) and `app/astrology/sky.py` (~line 16)

**Evidence:**
```python
# engine.py
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

# sky.py
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
```

**Problem:** Both set the same mode (SIDM_LAHIRI), so no functional issue currently. But this is fragile — if one module changes, the other silently overrides it. The engine.py comment explicitly says "Set it ONCE at import and never mutate it again."

**Fix:** Centralize the `swe.set_sid_mode` call in a single initialization function.

---

### 21. [SEV: major — P1] `swe.set_ephe_path` called in `engine.py:ensure_ephe()` per chart computation but also at module level in `sky.py` — no issue but wasteful

**File:** `app/astrology/sky.py` line 16, `app/astrology/engine.py` `ensure_ephe()`

**Problem:** Minor redundancy. Not a bug.

---

### 22. [SEV: major — P1] `_compute_and_save_chart` calls `get_current_user(request)` twice — once for the None check and once for `.id`

**File:** `app/main.py`, `_compute_and_save_chart()` (~line 215)

**Evidence:**
```python
user_id or (get_current_user(request).id if get_current_user(request) else None)
```

**Problem:** `get_current_user` is called twice. If it involves DB lookups or cookie parsing, this is wasteful. More critically, there's a TOCTOU race: the first call could return a user, the second could return None (or vice versa), causing an `AttributeError` on `.id`.

**Fix:**
```python
_u = get_current_user(request)
user_id or (_u.id if _u else None)
```

---

### 23. [SEV: major — P1] `lifespan` seeds plans with `PLANS_SEED` which includes `credits_grant` field, but `seed_plans()` in `db.py` also seeds plans — double seeding with potentially different data

**File:** `app/main.py` lifespan (~line 75) vs `app/db.py` `seed_plans()` (~line 35)

**Evidence:** `lifespan` inserts from `PLANS_SEED` (which includes credit3/credit6/credit12/monthly/yearly plans with `credits_grant`), then `init_db()` calls `seed_plans()` which has its own catalog (without credit packs). The lifespan runs first, inserts plans, then `seed_plans()` runs and overwrites `name_fa`, `subtitle_fa`, `features`, `sort` for overlapping keys but NOT `credits_grant` or `price_toman`.

**Problem:** Two sources of truth for plan data. The `PLANS_SEED` in main.py has credit packs (credit3/credit6/credit12) that `seed_plans()` in db.py doesn't know about. If `seed_plans()` runs after lifespan, it will update display fields of basic/full/gold/synastry/monthly/yearly but leave credit packs untouched (they exist from lifespan). This works but is confusing and fragile.

**Fix:** Consolidate into a single seed function.

---

### 24. [SEV: moderate — P2] `api_synastry` overwrites the `city_a`/`city_b` form parameters with search results

**File:** `app/main.py`, `api_synastry()` (~line 490)

**Evidence:**
```python
city_a = search_cities(city_a or "", 1)
city_b = search_cities(city_b or "", 1)
```

The form parameter `city_a: str` is overwritten with a `list[dict]`. This works because it's only used as `city_a[0]["lat"]` afterward, but it's confusing and would break if the variable were used as a string later.

**Fix:** Use different variable names: `cities_a = search_cities(city_a or "", 1)`.

---

### 25. [SEV: moderate — P2] `api_synastry` uses `resolve_tz_safe` which returns `None` for non-Iranian cities without timezonefinder — falls back to `"Asia/Tehran"` via `or "Asia/Tehran"`

**File:** `app/main.py`, `api_synastry()` (~line 500)

**Evidence:**
```python
resolve_tz_safe(float(city_a[0]["lat"]), float(city_a[0]["lon"])) or "Asia/Tehran"
```

**Problem:** `resolve_tz_safe` returns `None` for non-Iranian coords when timezonefinder fails. The `or "Asia/Tehran"` fallback silently computes a wrong chart for any non-Iranian city. This contradicts the careful F-06 handling in `_compute_and_save_chart`.

**Fix:** Raise HTTPException(400) when `resolve_tz_safe` returns None, consistent with the main chart creation flow.

---

### 26. [SEV: moderate — P2] Insight/synastry share tokens use only 24 hex chars of HMAC-SHA256 — 96 bits of security

**File:** `app/main.py`, `api_insight_share()`, `api_synastry_share()` (~lines 510, 540)

**Evidence:**
```python
tok = _hmac.new(_AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
```

**Problem:** 24 hex chars = 96 bits. For a signed share link this is adequate (the payload is not secret), but the truncation means collisions are more likely. Since the payload is included in the URL (`?p=...`), the HMAC just prevents tampering — 96 bits is sufficient for this purpose.

**Assessment:** Acceptable for the use case. No fix needed.

---

### 27. [SEV: moderate — P2] `_rate_limit` wraps `check_rate_limit` but swallows ALL exceptions, not just `RateLimitExceeded`

**File:** `app/main.py`, `_rate_limit()` (~line 740)

**Evidence:**
```python
def _rate_limit(key: str, limit: int, window: float = 60.0) -> bool:
    from app.security import RateLimitExceeded, check_rate_limit
    try:
        check_rate_limit(key, limit, int(window))
        return True
    except RateLimitExceeded:
        return False
```

Actually, this only catches `RateLimitExceeded` and lets other exceptions propagate. This is correct. ✅

---

### 28. [SEV: moderate — P2] `account_export` exposes `chart_json` (full planetary positions) in the export — this is the user's own data, so it's correct for GDPR export, but the endpoint has no rate limiting

**File:** `app/main.py`, `account_export()` (~line 930)

**Problem:** No rate limit on `/account/export`. An attacker with a stolen session cookie could repeatedly download the full data export. The endpoint does require authentication, but adding a rate limit (e.g., 3/hour) would be prudent.

**Fix:** Add `_rate_limit(f"export:{user.id}", 3, 3600)`.

---

### 29. [SEV: moderate — P2] `db.py` hardcodes dev database password in source code

**File:** `app/db.py`, line 10

**Evidence:**
```python
_DEV_DEFAULT = "postgresql://chart_app:***@127.0.0.1:5432/chart_platform"
```

The `***` is a placeholder, but if this were a real password, it would be in source control. The code correctly requires `DATABASE_URL` in production and only uses this default in dev. Acceptable if `***` is truly a placeholder.

---

### 30. [SEV: moderate — P2] `_house_of` fallback returns house 12 when no house matches — this can happen with extreme latitudes

**File:** `app/astrology/engine.py`, `_house_of()` (~line 310)

**Evidence:**
```python
def _house_of(lon: float, cusps) -> int:
    ...
    for i in range(12):
        ...
        if _between(lon, c1, c2):
            return i + 1
    return 12
```

**Problem:** If the loop doesn't find a match (possible with floating-point edge cases at exact cusp boundaries), it silently returns house 12. This could misplace a planet. The `_between` function handles wrap-around, so this should be rare, but a logging warning would help diagnose issues.

**Fix:** Add a warning log when the fallback is hit.

---

### 31. [SEV: moderate — P2] `search_cities` province normalization doesn't normalize Arabic kaf (ك → ک) in province names

**File:** `app/astrology/cities_ir.py`, `search_cities()` (~line 60)

**Evidence:**
```python
nq = q.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
out = [c for c in cities
       if nq in c["city_fa"].replace("\u064a", "\u06cc") or nq in c["province_fa"]]
```

The province_fa field is NOT normalized (no `.replace()` calls), so searching by province with Arabic kaf won't match.

**Fix:**
```python
if nq in c["city_fa"].replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
   or nq in c["province_fa"].replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
```

---

### 32. [SEV: moderate — P2] `api_explore_start` reuses variable name `chart` for both the Card object and the Chart DB object

**File:** `app/main.py`, `api_explore_start()` (~line 1100)

**Evidence:**
```python
card = CARD_MAP.get(card_key)
if not card:
    raise HTTPException(404, ...)
...
chart = session.get(Chart, chart_id)  # ← now `chart` is the DB Chart, `card` is the Card
if not chart or not _owns_chart(chart, session, request):
```

Wait — the function parameter is also `card_key`, and the path parameter is also `card_key`. The variable `chart` is reassigned from the path parameter `card_key`'s Card lookup to the DB Chart. Actually, looking more carefully, the function signature has `card_key: str` as a path param, and `chart_id: str = Form(...)`. The variable `card` holds the catalog card, `chart` holds the DB chart. This is fine — no collision.

**Retracted.**

---

### 33. [SEV: moderate — P2] `api_explore_start` exception handler reuses variable name `e` for both the outer exception and the inner `Exploration` object

**File:** `app/main.py`, `api_explore_start()` event_stream (~line 1130)

**Evidence:**
```python
except Exception as e:  # noqa: BLE001
    try:
        refund_credit(session, user.id, exp.id, charged)
        with Session(engine) as s2:
            e2 = s2.get(Exploration, exp.id)
            e2.status = "failed"
            e2.refunded = True
            e2.error = str(e)[:300]  # ← uses outer `e` (the exception)
```

This is actually fine — `e` is the exception, `e2` is the exploration. No collision. ✅

---

### 34. [SEV: moderate — P2] `_owns_chart` returns `False` for charts with no `access_token` AND no `profile_id` — orphaned charts are permanently inaccessible

**File:** `app/main.py`, `_owns_chart()` (~line 260)

**Problem:** If a chart somehow ends up with `profile_id=None` and `access_token=None`, it can never be accessed. This is a data integrity edge case, not a security issue.

---

### 35. [SEV: moderate — P2] `api_chat_stream` persists history in a NEW session (`s2`) but the outer session may have stale data

**File:** `app/main.py`, `api_chat_stream()` event_stream (~line 780)

**Evidence:**
```python
with Session(engine) as s2:
    s2.add(ChatMessage(...))
    ...
    s2.commit()
```

This is actually correct — the streaming response outlives the request's DI session, so using a new session is the right approach. ✅

---

### 36. [SEV: moderate — P2] `_ADMIN_SECRET` generated at startup in dev is ephemeral — admin cookies invalidated on every restart

**File:** `app/main.py`, (~line 960)

**Evidence:**
```python
if not _ADMIN_SECRET:
    if IS_PROD:
        raise RuntimeError(...)
    _ADMIN_SECRET = _secrets.token_hex(16)
```

**Problem:** In dev, every restart generates a new secret, invalidating all admin sessions. This is acceptable for dev but worth documenting.

---

### 37. [SEV: moderate — P2] `admin_page` loads ALL orders (up to 100), ALL reports (20), ALL users (50) in a single synchronous request — potential slow query

**File:** `app/main.py`, `admin_page()` (~line 1000)

**Evidence:** Multiple unbounded queries including `select(ChatMessage.id)` for total count:
```python
chat_total = len(session.exec(select(ChatMessage.id)).all())
```

**Problem:** `select(ChatMessage.id)` without a limit loads ALL chat message IDs into memory. For a production system with millions of messages, this will OOM or timeout.

**Fix:** Use `SELECT COUNT(*)`:
```python
from sqlalchemy import func
chat_total = session.exec(select(func.count(ChatMessage.id))).one()
```

---

### 38. [SEV: moderate — P2] `_compute_and_save_chart` doesn't set `profile.tz_name` — the BirthProfile model defaults to `"Asia/Tehran"` even for non-Iranian cities

**File:** `app/main.py`, `_compute_and_save_chart()` (~line 210)

**Evidence:** The `tz_name` is computed and passed to `compute_from_fields`, but never stored on the `BirthProfile` object:
```python
profile = BirthProfile(
    ...
    # tz_name is NOT set here — defaults to "Asia/Tehran"
)
```

**Problem:** The profile's `tz_name` field will always be "Asia/Tehran" regardless of the actual timezone used for computation. This affects data export, Today features, and any code that reads `profile.tz_name`.

**Fix:** Add `tz_name=tz_name` to the BirthProfile constructor.

---

### 39. [SEV: moderate — P2] Moon phase calculation doesn't account for sidereal adjustment

**File:** `app/astrology/engine.py`, ~line 240

**Evidence:**
```python
moon_phase = swe.degnorm(moon_lon - sun_lon)
```

Here `moon_lon` and `sun_lon` have already been adjusted for ayanamsa (sidereal). But moon phase is a TROPICAL phenomenon (the actual angular separation between Sun and Moon). Subtracting the same ayanamsa from both cancels out, so the result is the same as tropical. ✅ This is actually correct.

---

### 40. [SEV: moderate — P2] `Report.updated_at` uses `sa_column_kwargs` with `onupdate` as a Python lambda — this only works with SQLAlchemy's ORM `session.commit()`, not with raw SQL updates

**File:** `app/models.py`, Report model (~line 200)

**Evidence:**
```python
updated_at: datetime = Field(
    default_factory=lambda: datetime.now(timezone.utc),
    sa_column_kwargs={
        "server_default": text("now()"),
        "onupdate": lambda: datetime.now(timezone.utc),
    },
)
```

**Problem:** `onupdate` with a Python callable only fires during ORM-level updates. The raw SQL `UPDATE orders SET status = 'verifying'` in the payment flow won't trigger it. If stale-job recovery relies on `updated_at` being current, raw SQL updates will leave it stale.

**Fix:** Use `server_onupdate=text("now()")` or ensure all updates go through the ORM.

---

## CORRECT SECTIONS (no issues found)

- **Astrology math (engine.py):** Swiss Ephemeris usage is correct. Sidereal handling via manual ayanamsa subtraction (avoiding global state mutation per-request) is the right approach. Element/modality counting is correct. House placement logic is sound. DST handling via `zoneinfo` is correct and covers Iran's full history.

- **Golden data (golden_data.py):** Comprehensive test vectors covering DST eras, foreign cities, sidereal mode, unknown birth time, and Jalali calendar. Well-structured.

- **Big three (big_three.py):** Correct sign determination, proper handling of unknown birth time (ASC omitted). Sign metadata is accurate.

- **Cities (cities_ir.py, cities_world.py):** Timezone resolution is well-designed with the Iran-only fallback pattern. The `is_iran_coords` bounding box is reasonable.

- **Rectify (rectify.py):** Sound approach with 20-minute steps, event-category filtering, and transit scoring. CPU-bounded by the 3-event cap.

- **IDOR protections:** Consistently applied via `_owns_chart()` with capability tokens. The `compare_digest` usage prevents timing attacks.

- **Payment flow:** The `pending→verifying→paid` state machine with advisory locks is well-designed. The "never mark failed on network error" pattern is correct for payment safety.

- **CSRF protection:** Present on account deletion and notification prefs.

- **Webhook security:** Both Telegram and Bale webhooks validate secrets with `compare_digest`. Fail-closed when secrets are unconfigured.

---

## VERDICT

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Correctness** | ⚠️ Major issues | `seed_plans` uses closed session (F5); `readiness` `asyncio.run` crashes under uvicorn (F1-3); year validation doesn't distinguish calendars (F6); `tz_name` not stored on profile (F38) |
| **Security (OWASP)** | ✅ Good with caveats | IDOR gates are thorough; CSRF present; webhook auth solid. Internal exception leak in payment error (F10); no rate limit on data export (F28); account deletion incomplete (F11-16) |
| **Data Races** | ⚠️ Moderate risk | `_ARQ_POOL` global bound to wrong loop (F3); `_seen_update_ids` set eviction is random not FIFO (F7); `get_current_user` TOCTOU (F22) |
| **Cost Leaks** | ✅ Good | Chat quota is atomic (Redis INCR); exploration refunds on failure; preview caching prevents repeat LLM calls |
| **Astrology Math** | ✅ Correct | Swiss Ephemeris usage is sound; sidereal handling avoids global state race; DST via zoneinfo is correct; golden data coverage is excellent |
| **RAG/LLM Pipeline** | ✅ Acceptable | (Not deeply covered in this chunk — chat/report generation delegated to service modules) |
| **UX (Mobile RTL)** | N/A | No frontend code in this chunk |
| **Business Logic** | ⚠️ Minor gaps | Double plan seeding (F23); synastry timezone fallback to Tehran for non-Iranian cities (F25); credit pack orders possible without auth (F9) |
| **Launch Readiness** | 🔴 Not ready | The `readiness` endpoint itself crashes under uvicorn (F1-3); `seed_plans` fails on coupon seeding (F5); account deletion will 500 for any user with explorations/consent/notifications/push/credits (F11-16) — these are **blocking** for launch |

**Summary:** The codebase shows strong security awareness (IDOR, CSRF, payment state machine, webhook auth) and correct astrology computation. However, **three critical runtime bugs** (asyncio.run in sync endpoints, closed session in seed, ARQ pool bound to wrong loop) and **six missing FK cascades in account deletion** must be fixed before launch.