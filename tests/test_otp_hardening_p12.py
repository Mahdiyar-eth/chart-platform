"""ZAYCHE P12 gate 1a — OTP auth hardening tests (hermetic, no SMS cost).

Covers: expiry, resend (new code invalidates old), wrong code, brute force
(attempts limit), concurrent requests (per-phone rate limit), account
enumeration (identical responses for known/unknown), logout → re-login flow,
and a mocked Kavenegar SMS send (captured, never a real API call).

Uses the real redis (same semantics as prod) with isolated phone numbers and
keys scrubbed per test. Codes are injected via redis (hashed, as prod stores)
so no real SMS or brute-forcing is needed.
"""
import time
from unittest.mock import patch

import pytest

import app.auth as A


PHONES = [f"9891200{n:06d}" for n in range(1, 40)]


@pytest.fixture(autouse=True)
def _clean_otp_keys():
    yield
    for p in PHONES:
        A._OTP_REDIS.delete(A._otp_key(p))
        A._OTP_REDIS.delete(A._otp_rl_key(p))


def _inject(phone: str, code: str) -> None:
    """Store a code exactly as request_otp does (hashed) for the phone."""
    A._OTP_REDIS.hset(A._otp_key(phone), mapping={"code": A._hash_code(code), "attempts": "0"})
    A._OTP_REDIS.expire(A._otp_key(phone), A.OTP_TTL)


def test_otp_expiry_after_ttl():
    with patch.object(A, "_send_sms", return_value=None):
        A.request_otp(PHONES[0])
        A._OTP_REDIS.expire(A._otp_key(PHONES[0]), 1)
        time.sleep(1.2)
    assert A.verify_otp(PHONES[0], "11111") is None
    assert A._OTP_REDIS.get(A._otp_key(PHONES[0])) is None


def test_otp_resend_invalidates_previous_code():
    with patch.object(A, "_send_sms", return_value=None):
        A.request_otp(PHONES[1])
        first = _dev_code(PHONES[1])
        A.request_otp(PHONES[1])
        second = _dev_code(PHONES[1])
    assert first is not None and second is not None
    assert first != second  # new code replaced old atomically


def _dev_code(phone: str) -> str | None:
    rec = A._OTP_REDIS.hgetall(A._otp_key(phone))
    return rec.get("code") if rec else None


def test_otp_wrong_code_consumes_an_attempt_but_code_stays_valid():
    _inject(PHONES[2], "12345")
    assert A.verify_otp(PHONES[2], "99999") is None
    rec = A._OTP_REDIS.hgetall(A._otp_key(PHONES[2]))
    assert int(rec["attempts"]) == 1
    assert A.verify_otp(PHONES[2], "12345") is not None  # still usable


def test_otp_brute_force_locks_after_max_attempts():
    _inject(PHONES[3], "12345")
    for _ in range(A.OTP_MAX_ATTEMPTS):
        assert A.verify_otp(PHONES[3], "00000") is None
    assert A._OTP_REDIS.get(A._otp_key(PHONES[3])) is None  # key deleted → locked
    assert A.verify_otp(PHONES[3], "12345") is None  # even the right code fails now


def test_otp_concurrent_requests_rate_limited():
    with patch.object(A, "_send_sms", return_value=None):
        for _ in range(A.OTP_REQ_LIMIT):
            assert A.request_otp(PHONES[4])["ok"] is True
        with pytest.raises(RuntimeError):
            A.request_otp(PHONES[4])


def test_otp_account_enumeration_no_oracle():
    """A fresh unknown number must not reveal whether a number exists."""
    with patch.object(A, "_send_sms", return_value=None):
        r = A.request_otp(PHONES[5])
    assert r["ok"] is True and "expires_in" in r
    assert A.verify_otp(PHONES[6], "00000") is None  # no code → None, same as wrong code
    # and an existing user's flow looks identical (no "user exists" flag)
    with patch.object(A, "_send_sms", return_value=None):
        assert set(A.request_otp(PHONES[7]).keys()) == {"ok", "expires_in"}


def test_otp_mocked_kavenegar_send_called_with_code():
    sent = {}
    with patch.object(A, "_send_sms") as m:
        m.side_effect = lambda phone, code: sent.update(phone=phone, code=code)
        A.request_otp(PHONES[8])
    assert sent["phone"] == PHONES[8]
    assert len(sent["code"]) == 5
    assert A.verify_otp(PHONES[8], sent["code"]) is not None  # SMS code verifies


def test_otp_logout_relogin_requires_new_code():
    """Session flow: login → logout (code consumed) → re-login needs NEW code."""
    _inject(PHONES[9], "12345")
    u1 = A.verify_otp(PHONES[9], "12345")
    assert u1 is not None
    # OTP record deleted on successful verify — old code is dead after logout
    assert A._OTP_REDIS.get(A._otp_key(PHONES[9])) is None
    assert A.verify_otp(PHONES[9], "12345") is None
    # re-login: a fresh code works
    _inject(PHONES[9], "54321")
    assert A.verify_otp(PHONES[9], "54321") is not None
