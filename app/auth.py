"""Lazy OTP auth (plan v3.1 §4 — Kavenegar first, dev-mode fallback).

Flow: chart form stays anonymous; OTP only when user wants dashboard/purchase.
- POST /api/auth/otp/request  {phone}   → 5-digit code (SMS via Kavenegar if
  OTP_SMS_API_KEY set, else server log — dev mode OTP_DEV_MODE=true returns hint).
- POST /api/auth/otp/verify   {phone, code} → session cookie (hmac of user id).
- GET  /api/auth/me                    → current user (or null)
- POST /api/auth/logout
Cookie: chart_user (httponly, samesite=lax, 30 days).
"""
import hashlib
import hmac as _hmac
import logging
import os
import secrets

import redis as _redis

from app.env import IS_PROD
from fastapi import Request
from sqlmodel import Session, select

import app.config  # noqa: F401
from app.db import engine
from app.models import User

log = logging.getLogger("chart.auth")

_AUTH_SECRET: str = os.getenv("AUTH_SECRET") or ""
if not _AUTH_SECRET:
    # fail-closed in production: a random per-boot secret would silently
    # invalidate every session on restart (audit P0)
    if IS_PROD:
        raise RuntimeError("AUTH_SECRET is required in production (APP_ENV=prod|production)")
    _AUTH_SECRET = secrets.token_hex(16)  # dev-only ephemeral
_OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "false").lower() == "true"
USER_COOKIE = "chart_user"
OTP_TTL = 300           # 5 minutes
OTP_MAX_ATTEMPTS = 5
OTP_REQ_LIMIT = 3       # max OTP requests per phone per window
OTP_REQ_WINDOW = 600    # 10 minutes
# Redis-backed OTP (audit P1-2): survives multi-worker, hashed code, TTL.
_REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_OTP_REDIS = _redis.Redis.from_url(_REDIS_URL, decode_responses=True)


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _otp_rl_key(phone: str) -> str:
    return f"otp:rl:{phone}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


# ── session helpers ──────────────────────────────────────────────────────────

def _user_cookie_value(user_id: str) -> str:
    sig = _hmac.new(_AUTH_SECRET.encode(), user_id.encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{sig}"


def get_current_user(request: Request) -> User | None:
    val = request.cookies.get(USER_COOKIE, "")
    if not val or "." not in val:
        return None
    uid, sig = val.rsplit(".", 1)
    if len(sig) != 64:
        return None
    expect = _hmac.new(_AUTH_SECRET.encode(), uid.encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expect, sig):
        return None
    with Session(engine) as s:
        return s.get(User, uid)


def set_user_cookie(request: Request, user_id: str):
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse("/account", status_code=303)
    resp.set_cookie(USER_COOKIE, _user_cookie_value(user_id), httponly=True,
                    max_age=30 * 24 * 3600, samesite="lax", secure=True)
    return resp


# ── OTP ──────────────────────────────────────────────────────────────────────

def _send_sms(phone: str, code: str) -> None:
    """Kavenegar v2 if configured. Fail-closed in production (audit P0):
    never log the OTP itself outside explicit dev mode."""
    from app.secret_store import get_secret
    api_key = get_secret("otp_sms_api_key", "OTP_SMS_API_KEY", "")
    if api_key:
        try:
            import httpx
            url = f"https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"
            r = httpx.post(url, data={
                "receptor": phone, "token": code, "template": get_secret("otp_sms_template", "OTP_SMS_TEMPLATE", "chartotp"),
            }, timeout=10)
            r.raise_for_status()
            return
        except Exception as e:
            if IS_PROD:
                raise RuntimeError(f"SMS delivery failed: {e}") from e
            log.warning("SMS send failed: %s — falling back to dev log", e)
    if _OTP_DEV_MODE:
        log.info("OTP DEV MODE: code for %s = %s", phone, code)
    else:
        raise RuntimeError("SMS provider not configured (OTP_SMS_API_KEY)")


def request_otp(phone: str) -> dict:
    phone = phone.strip()
    # per-phone rate limit (combined with the endpoint's IP limit)
    rl = _OTP_REDIS.incr(_otp_rl_key(phone))
    if rl == 1:
        _OTP_REDIS.expire(_otp_rl_key(phone), OTP_REQ_WINDOW)
    if rl > OTP_REQ_LIMIT:
        raise RuntimeError("تعداد درخواست کد زیاد است؛ کمی بعد دوباره تلاش کن")
    code = f"{secrets.randbelow(100000):05d}"  # cryptographic RNG (audit P1-2)
    key = _otp_key(phone)
    _OTP_REDIS.hset(key, mapping={"code": _hash_code(code), "attempts": "0"})
    _OTP_REDIS.expire(key, OTP_TTL)
    _send_sms(phone, code)
    out = {"ok": True, "expires_in": OTP_TTL}
    if _OTP_DEV_MODE:
        out["dev_code"] = code
    return out


def verify_otp(phone: str, code: str) -> User | None:
    phone = phone.strip()
    key = _otp_key(phone)
    rec = _OTP_REDIS.hgetall(key)
    if not rec:
        return None
    attempts = int(rec.get("attempts", "0")) + 1
    if attempts > OTP_MAX_ATTEMPTS:
        _OTP_REDIS.delete(key)
        return None
    _OTP_REDIS.hset(key, "attempts", str(attempts))
    if not _hmac.compare_digest(rec.get("code", ""), _hash_code(code.strip())):
        return None
    _OTP_REDIS.delete(key)

    with Session(engine) as s:
        u = s.exec(select(User).where(User.phone == phone)).first()
        if not u:
            u = User(phone=phone)
            s.add(u)
            s.commit()
            s.refresh(u)
        return u
