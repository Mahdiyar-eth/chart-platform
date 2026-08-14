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
        o = Order(chart_id=c.id, plan_key="full", amount_rial=399000, status="paid")
        s.add(o)
        s.commit()
        assert _report_gate(rep, s, FakeRequest(t="tok-rg2")) is True


def test_report_gate_denies_paid_but_wrong_token():
    with Session(engine) as s:
        c = _make_anon_chart(s, "tok-rg3")
        rep = _make_report(s, c)
        o = Order(chart_id=c.id, plan_key="full", amount_rial=399000, status="paid")
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

        order, _url = create_order(s, "full", c.id)
        assert order.profile_id == p.id  # ← was None before the fix
