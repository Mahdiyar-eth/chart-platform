"""Ownership gate tests — audit P0-1.

An anonymous (or registered) chart must NEVER be reachable by a bare UUID;
access requires user_id OR the cryptographically-strong capability token.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session
import uuid

from app.db import engine
from app.models import Chart, BirthProfile, Order, Report, User
from app.main import _owns_chart, _report_gate


def _uniq_phone() -> str:
    return "09" + str(uuid.uuid4().int)[:9]


class FakeRequest:
    def __init__(self, t=None, cookies=None):
        self._t = t
        self.cookies = cookies or {}

    @property
    def query_params(self):
        class _QP:
            def __init__(self, t):
                self._t = t
            def get(self, k, default=None):
                return self._t if k == "t" else default
        return _QP(self._t)


def _make_anon_chart(session: Session, token="tok123") -> Chart:
    p = BirthProfile(raw_year=1994, raw_month=8, raw_day=23, time_known=True,
                     hour=6, minute=10, city_fa="تهران", tz_name="Asia/Tehran",
                     calendar_system="jalali")
    session.add(p)
    session.flush()
    c = Chart(profile_id=p.id, chart_json={}, engine_config={}, access_token=token)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _make_user(session: Session, phone: str) -> User:
    u = User(phone=phone)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _make_owned_chart(session: Session, user: User, token="tok_owned") -> Chart:
    p = BirthProfile(user_id=user.id, raw_year=1994, raw_month=8, raw_day=23,
                     time_known=True, hour=6, minute=10, city_fa="تهران",
                     tz_name="Asia/Tehran", calendar_system="jalali")
    session.add(p)
    session.flush()
    c = Chart(profile_id=p.id, chart_json={}, engine_config={}, access_token=token)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


# ── anonymous capability token ─────────────────────────────

def test_bare_uuid_denied():
    with Session(engine) as s:
        c = _make_anon_chart(s)
        assert _owns_chart(c, s, FakeRequest()) is False


def test_correct_token_granted():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-abc")
        assert _owns_chart(c, s, FakeRequest(t="tok-abc")) is True


def test_wrong_token_denied():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-abc")
        assert _owns_chart(c, s, FakeRequest(t="tok-WRONG")) is False


def test_cookie_token_granted():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-cookie")
        req = FakeRequest(cookies={"chart_access": f'{{"{c.id}": "tok-cookie"}}'})
        assert _owns_chart(c, s, req) is True


# ── registered-user ownership ──────────────────────────────

def test_registered_owner_granted(monkeypatch):
    with Session(engine) as s:
        u = _make_user(s, _uniq_phone())
        c = _make_owned_chart(s, u)
        monkeypatch.setattr("app.main.get_current_user", lambda req: u)
        assert _owns_chart(c, s, FakeRequest()) is True


def test_registered_other_user_denied(monkeypatch):
    with Session(engine) as s:
        owner = _make_user(s, _uniq_phone())
        other = _make_user(s, _uniq_phone())
        c = _make_owned_chart(s, owner)
        monkeypatch.setattr("app.main.get_current_user", lambda req: other)
        assert _owns_chart(c, s, FakeRequest()) is False


# ── report gate: paid order required ────────────────────────

def _make_report(session: Session, chart: Chart) -> Report:
    r = Report(chart_id=chart.id, status="done")
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def test_report_gate_denies_without_paid_order():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-rg1")
        rep = _make_report(s, c)
        assert _report_gate(rep, s, FakeRequest(t="tok-rg1")) is False


def test_report_gate_grants_paid_owner():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-rg2")
        rep = _make_report(s, c)
        o = Order(chart_id=c.id, plan_key="full", amount_rial=399000, status="paid",
                  report_id=rep.id)
        s.add(o)
        s.commit()
        assert _report_gate(rep, s, FakeRequest(t="tok-rg2")) is True


def test_report_gate_denies_paid_but_wrong_token():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-rg3")
        rep = _make_report(s, c)
        o = Order(chart_id=c.id, plan_key="full", amount_rial=399000, status="paid",
                  report_id=rep.id)
        s.add(o)
        s.commit()
        assert _report_gate(rep, s, FakeRequest(t="WRONG")) is False


# ── P1-4: order must inherit profile_id from the chart ─────

def test_create_order_inherits_profile_id(monkeypatch):
    from app.payment.orders import create_order

    class _FakeZP:
        def request(self, *a, **k):
            return ("AUTH123", "https://pay.test/start")

    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", _FakeZP)
    with Session(engine) as s:
        u = _make_user(s, _uniq_phone())
        p = BirthProfile(user_id=u.id, raw_year=1994, raw_month=8, raw_day=23,
                         time_known=True, hour=6, minute=10, city_fa="تهران",
                         tz_name="Asia/Tehran", calendar_system="jalali")
        s.add(p)
        s.flush()
        c = Chart(profile_id=p.id, chart_json={}, engine_config={}, access_token="tok-ord")
        s.add(c)
        s.commit()
        s.refresh(c)

        # R13/N3: legacy toman plans are retired (active=False) — this test now
        # uses the credit3 pack plan which is still orderable via /api/orders.
        order, _url = create_order(s, "credit6", c.id)
        assert order.profile_id == p.id  # ← was None before the fix


# ── BUGFIX 2026-08-27: chart_access cookie round-trip ─────
# Real Chromium DROPS a cookie whose value contains quotes/braces (set_cookie
# sent raw JSON → «"{...}"» → guest who just created a chart got 303 to
# /birth-form and NEVER saw their chart). The setter now URL-quotes the JSON;
# the reader unquotes and also tolerates legacy double-quoted values.

def test_chart_tokens_roundtrip_urlquoted():
    from urllib.parse import quote
    from app.main import _chart_tokens
    import json as _j

    class _R:
        def __init__(self, raw):
            self.cookies = {"chart_access": raw}

    tokens = {"abcd-1234": "tok_x-y_z", "efgh-5678": "tok2"}
    quoted = quote(_j.dumps(tokens), safe="")
    assert '"' not in quoted and "{" not in quoted  # browser-safe alphabet
    # new %-quoted form (what the setter now emits, what Chromium keeps)
    assert _chart_tokens(_R(quoted)) == tokens
    # plain JSON (cookie jars that already URL-normalize) still works
    assert _chart_tokens(_R(_j.dumps(tokens))) == tokens
    # legacy double-quoted form («"{...}"» from the old set_cookie quoting)
    legacy = '"' + _j.dumps(tokens).replace('"', '\\"') + '"'
    assert _chart_tokens(_R(legacy)) == tokens


def test_guest_chart_page_visible_after_creation():
    """E2E regression: guest creates a chart via /api/charts, then the EXACT
    Set-Cookie value must let /chart/{id} render (200), not 303 to birth-form.
    TestClient runs over http — Secure cookies are dropped by the jar there,
    so re-add the cookie with secure=False to mirror an https browser."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/api/charts", data={
            "calendar": "jalali", "year": 1373, "month": 6, "day": 15,
            "time_known": "true", "hour": 6, "minute": 10,
            "city_fa": "تهران", "province_fa": "تهران", "lat": 35.6892,
            "lon": 51.3890, "zodiac": "tropical"})
        assert r.status_code == 200
        cid = r.json()["chart_id"]
        set_cookie = r.headers.get("set-cookie", "")
        assert "chart_access=" in set_cookie
        raw = set_cookie.split("chart_access=")[1].split(";")[0]
        # raw value must be URL-quoted (no quotes/braces) so browsers keep it
        assert '"' not in raw and "{" not in raw, f"unsafe cookie value: {raw[:60]}"
        # https-browser simulation: inject the cookie header directly
        # (httpx drops Secure cookies on its http test transport)
        c.cookies.delete("chart_access")
        r2 = c.get(f"/chart/{cid}", follow_redirects=False,
                   headers={"Cookie": f"chart_access={raw}"})
        assert r2.status_code == 200, f"guest chart page redirected: {r2.status_code} {r2.headers.get('location','')}"
