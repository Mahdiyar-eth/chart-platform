"""Login must land the user where they were going, with their chart in hand.

Two defects, both on the critical path from "free chart" to "paying customer":

1. Every caller passes ``next`` (chart.html, plans.html, solar.html,
   relocation.html) and the login page ignored all of them, hardcoding
   ``/account``. A guest who clicked "buy" on the solar page was sent to log in
   and then dumped on their account page with no route back to the product.

2. ``claim_anonymous_charts`` existed and worked, but the ``cap`` it needs was
   never sent by anything. The chart_access cookie is httpOnly, so the browser
   *cannot* send it from JavaScript — the claim has to happen server-side.
   test_money_paths_r14.py::test_94_guest_chart_then_register_claims_it passes
   ``cap`` by hand and so has always been green; no real login ever did.
   Until this, "your chart will be saved to your account" was simply false.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import _safe_next
from app.main import app as main_app
from app.models import BirthProfile, Chart


def _phone() -> str:
    return "0912" + str(uuid.uuid4().int)[:8]


def _otp(c, phone: str) -> str:
    """Request an OTP and return the dev code.

    The rate limiter keys on the client identity, which is "testclient" for
    every test in the suite, so the 5/300s budget is shared globally. Clear it
    first or a full-suite run fails on ordering alone.
    """
    from app import security as _sec
    _sec._RATE_LIMITS.pop("otp:testclient", None)
    r = c.post("/api/auth/otp/request", data={"phone": phone})
    assert r.status_code == 200, r.text
    return r.json()["dev_code"]


def _mk_chart(c):
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


# ── 1. next= sanitising ──────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("/plans", "/plans"),
    ("/chart/abc-123", "/chart/abc-123"),
    ("/solar/xyz?t=tok", "/solar/xyz?t=tok"),
    # falsy / missing -> default
    ("", "/account"),
    (None, "/account"),
    # open-redirect vectors must all collapse to the default
    ("//evil.example", "/account"),
    ("///evil.example", "/account"),
    ("http://evil.example", "/account"),
    ("https://evil.example", "/account"),
    ("javascript:alert(1)", "/account"),
    ("/\\evil.example", "/account"),
    ("\\\\evil.example", "/account"),
    ("evil.example", "/account"),                # not absolute
    ("/plans\r\nSet-Cookie: x=1", "/account"),   # header/response splitting
])
def test_safe_next_rejects_external_destinations(raw, expected):
    assert _safe_next(raw) == expected


def test_login_page_echoes_sanitised_next():
    """Assert on the redirect target specifically — /plans also appears in the
    nav drawer on every page, so a bare substring check passes either way."""
    c = TestClient(main_app, base_url="https://testserver")
    r = c.get("/account/login?next=/plans")
    assert r.status_code == 200
    assert 'next: "/plans"' in r.text, "login page did not adopt next="


def test_login_page_defaults_to_account_when_next_absent():
    c = TestClient(main_app, base_url="https://testserver")
    r = c.get("/account/login")
    assert 'next: "/account"' in r.text


def test_login_page_does_not_echo_hostile_next():
    c = TestClient(main_app, base_url="https://testserver")
    r = c.get("/account/login?next=//evil.example")
    assert r.status_code == 200
    assert "evil.example" not in r.text
    assert 'next: "/account"' in r.text, "hostile next= must collapse to default"


# ── 2. guest chart is claimed at login ───────────────────────────────────────
def test_guest_chart_claimed_on_login_with_no_cap_field(monkeypatch):
    """The point: the template sends nothing, and it still works.

    This is the real browser's situation — chart_access is httpOnly, so the
    page cannot read it, so no `cap` is ever posted.
    """
    c = TestClient(main_app, base_url="https://testserver")
    cid, _tok = _mk_chart(c)
    assert c.cookies.get("chart_access"), "guest ownership cookie not set"

    with Session(engine) as s:
        prof = s.get(BirthProfile, s.get(Chart, cid).profile_id)
        assert prof.user_id is None

    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    phone = _phone()
    dev = _otp(c, phone)
    # NOTE: no `cap` — exactly what account_login.html posts.
    r = c.post("/api/auth/otp/verify", data={"phone": phone, "code": dev})
    assert r.status_code == 200, r.text

    with Session(engine) as s:
        prof = s.get(BirthProfile, s.get(Chart, cid).profile_id)
        assert prof.user_id is not None, (
            "guest chart was not claimed at login — the user logs in and their "
            "chart is still ownerless, so /account shows 'no charts yet'"
        )


def test_login_claims_every_guest_chart_in_the_cookie(monkeypatch):
    """A guest can make several charts before signing up; all are theirs."""
    c = TestClient(main_app, base_url="https://testserver")
    ids = [_mk_chart(c)[0] for _ in range(3)]

    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    phone = _phone()
    dev = _otp(c, phone)
    c.post("/api/auth/otp/verify", data={"phone": phone, "code": dev})

    with Session(engine) as s:
        owners = [s.get(BirthProfile, s.get(Chart, i).profile_id).user_id for i in ids]
    assert all(o is not None for o in owners), f"unclaimed charts: {owners}"
    assert len(set(owners)) == 1, "all charts must land on the same user"


def test_login_never_steals_an_owned_chart(monkeypatch):
    """Someone else's token in your cookie must not transfer their chart."""
    owner = TestClient(main_app, base_url="https://testserver")
    cid, tok = _mk_chart(owner)
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    p1 = _phone()
    dev = _otp(owner, p1)
    owner.post("/api/auth/otp/verify", data={"phone": p1, "code": dev})
    with Session(engine) as s:
        first = s.get(BirthProfile, s.get(Chart, cid).profile_id).user_id
    assert first is not None

    # A second person shows up carrying the first person's capability token.
    thief = TestClient(main_app, base_url="https://testserver")
    thief.cookies.set("chart_access", __import__("json").dumps({cid: tok}))
    p2 = _phone()
    dev2 = _otp(thief, p2)
    thief.post("/api/auth/otp/verify", data={"phone": p2, "code": dev2})

    with Session(engine) as s:
        still = s.get(BirthProfile, s.get(Chart, cid).profile_id).user_id
    assert still == first, "an already-owned chart was re-assigned"
