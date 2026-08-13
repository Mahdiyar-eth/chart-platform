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
from hmac import compare_digest as _compare_digest

from fastapi import Request
from sqlmodel import Session, select

import app.config  # noqa: F401

_RATE_LIMITS: dict[str, deque] = defaultdict(deque)
_RATE_LIMITS_WINDOW = 60  # seconds
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_COOKIE = "csrf_token"


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
    now = time.monotonic()
    q = _RATE_LIMITS[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_calls:
        raise RateLimitExceeded(key)
    q.append(now)


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


def audit(engine, admin: str, action: str, entity: str = "", details: str = "") -> None:
    """Write an audit_logs row (best-effort — never crashes the request)."""
    try:
        from app.models import AuditLog
        with Session(engine) as s:
            s.add(AuditLog(admin=admin, action=action, entity=entity, details=details[:500]))
            s.commit()
    except Exception:
        pass
