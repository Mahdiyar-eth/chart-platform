"""Security middleware: CSRF origin check + rate limiting + audit log helper.

- CSRF: for state-changing requests, require Origin header to match Host
  (defends against cross-site POSTs; all our forms are same-site).
- Rate limit: simple in-memory sliding window per (ip, scope).
- audit(): record admin actions to audit_logs table.
"""
import os
import secrets as _secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from hmac import compare_digest as _compare_digest

from fastapi import Request
from sqlmodel import Session

import app.config  # noqa: F401
from app.env import IS_PROD

_RATE_LIMITS: dict[str, deque] = defaultdict(deque)
_RATE_LIMITS_WINDOW = 60  # seconds
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_COOKIE = "csrf_token"

# audit P1 (round 3): distributed rate limiting. RATE_LIMIT_BACKEND=redis uses a
# Redis fixed-window counter shared across workers/instances. audit r4 B5:
# Redis is MANDATORY in production (per-process memory counters are useless
# with >1 worker) — a prod deploy configured for memory must refuse to boot.
_RATE_LIMIT_BACKEND = os.getenv("RATE_LIMIT_BACKEND", "memory").lower()
if IS_PROD and _RATE_LIMIT_BACKEND != "redis":
    raise RuntimeError(
        "RATE_LIMIT_BACKEND=redis is REQUIRED in production (audit r4 B5). "
        "In-memory counters do not work across workers."
    )
_rl_redis_conn = None


def _rl_redis():
    global _rl_redis_conn
    if _rl_redis_conn is None:
        import redis
        _rl_redis_conn = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            socket_connect_timeout=0.4, socket_timeout=0.4, decode_responses=True)
    return _rl_redis_conn


def _rl_memory(key: str, max_calls: int, window: int) -> bool:
    """Sliding-window in-memory check; True = allowed."""
    now = time.monotonic()
    q = _RATE_LIMITS[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_calls:
        return False
    q.append(now)
    return True


def _rl_redis_check(key: str, max_calls: int, window: int) -> bool:
    """Fixed-window Redis counter; True = allowed. Raises on Redis failure."""
    import time as _t
    bucket = int(_t.time() // max(1, window))
    nk = f"rl:{key}:{bucket}"
    r = _rl_redis()
    n = r.incr(nk)
    if n == 1:
        r.expire(nk, window + 5)
    return n <= max_calls


def chat_quota_claim(account_key: str, limit: int) -> int | None:
    """Atomic per-ACCOUNT daily quota claim (audit r4 A8): Redis INCR+TTL.

    Returns the new used count, or None when Redis is unavailable (caller
    falls back to a DB count). Multiple charts of one account share the pool."""
    import datetime as _dt
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    nk = f"chatq:{day}:{account_key}"
    try:
        r = _rl_redis()
        n = r.incr(nk)
        if n == 1:
            r.expire(nk, 26 * 3600)
        return n
    except Exception:  # noqa: BLE001
        return None


def chat_quota_release(account_key: str) -> None:
    """Undo a claim when the request failed before producing an answer."""
    import datetime as _dt
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    try:
        _rl_redis().decr(f"chatq:{day}:{account_key}")
    except Exception:  # noqa: BLE001
        pass


def chat_quota_used(account_key: str) -> int | None:
    """Current atomic counter for display; None when Redis is unavailable."""
    import datetime as _dt
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    try:
        n = _rl_redis().get(f"chatq:{day}:{account_key}")
        return int(n) if n is not None else 0
    except Exception:  # noqa: BLE001
        return None


def new_csrf_token() -> str:
    return _secrets.token_urlsafe(16)


def verify_csrf(request: Request, submitted: str) -> bool:
    """Double-submit CSRF check: form token must equal the cookie token."""
    expect = request.cookies.get(CSRF_COOKIE, "")
    return bool(expect and submitted and _compare_digest(expect, submitted))


class RateLimitExceeded(Exception):
    pass


def check_rate_limit(key: str, max_calls: int, window: int = _RATE_LIMITS_WINDOW) -> None:
    """Allow `max_calls` per `window` seconds for `key`. Raises RateLimitExceeded."""
    if _RATE_LIMIT_BACKEND == "redis":
        try:
            if not _rl_redis_check(key, max_calls, window):
                raise RateLimitExceeded(key)
            return
        except RateLimitExceeded:
            raise
        except Exception:  # noqa: BLE001 — Redis down
            if IS_PROD:
                # audit r4 B5: fail-CLOSED in prod — never silently open the
                # floodgates because Redis hiccuped
                raise RateLimitExceeded(key)
            # dev/tests: in-memory fallback keeps things usable
            pass
    if not _rl_memory(key, max_calls, window):
        raise RateLimitExceeded(key)


def csrf_protect(request: Request) -> bool:
    """Origin must match Host for non-safe methods. Returns True when OK."""
    if request.method in SAFE_METHODS:
        return True
    origin = request.headers.get("origin")
    if not origin:
        # Non-browser clients (curl, bots, server-to-server) — allow
        return True
    host = request.headers.get("host", "")
    try:
        from urllib.parse import urlparse
        return urlparse(origin).netloc == host
    except Exception:
        return False


async def security_guard(request: Request, call_next):
    """FastAPI middleware: CSRF + rate limit for sensitive scopes."""
    if not csrf_protect(request):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "CSRF: origin mismatch"}, status_code=403)

    # rate limit: OTP request (5/min per ip), webhooks (30/min), payments (20/min)
    path = request.url.path
    ip = request.client.host if request.client else "?"
    scope_key = None
    max_calls = 30
    if path.startswith("/api/auth/otp/request"):
        scope_key, max_calls = f"otp:{ip}", 5
    elif path.startswith("/api/v1/"):
        scope_key, max_calls = f"webhook:{ip}", 30
    elif path.startswith("/api/payments"):
        scope_key, max_calls = f"pay:{ip}", 20
    elif path.startswith("/api/chat"):
        scope_key, max_calls = f"chat:{ip}", 40
    if scope_key:
        try:
            check_rate_limit(scope_key, max_calls)
        except RateLimitExceeded:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "درخواست بیش از حد — کمی بعد تلاش کنید"}, status_code=429)
    return await call_next(request)


_AUDIT_FALLBACK = os.environ.get("AUDIT_FALLBACK_LOG", "/tmp/zayche-audit-fallback.log")


def audit(engine, admin: str, action: str, entity: str = "", details: str = "") -> None:
    """Write an audit_logs row (best-effort — never crashes the request).

    F-16 (audit v6 P2): a DB failure no longer swallows the forensic record
    silently — the event is appended to an append-only fallback file so a
    refund / withdrawal resolution / secret change is never left with NO
    durable trace. The fallback is read by scripts/audit_fallback_ingest.py
    and re-inserted once the DB is healthy.
    """
    try:
        from app.models import AuditLog
        with Session(engine) as s:
            s.add(AuditLog(admin=admin, action=action, entity=entity, details=details[:500]))
            s.commit()
    except Exception:  # noqa: BLE001 — never crash the main operation
        try:
            import json as _json
            with open(_AUDIT_FALLBACK, "a") as f:
                f.write(_json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "admin": admin, "action": action, "entity": entity,
                    "details": details[:500],
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass  # last resort: even the fallback failed — stay silent
