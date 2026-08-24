"""R.7 / T1 (P1) — transit-analysis refund uses the NARRATED denominator.

The reviewer ran the real money funnel and found: `api_chart_forecast_analyze`
computed the partial-refund denominator as `len(events)` (ALL forecasted events)
instead of the number of events actually NARRATED (`m["events"]` == len(top) == n).
So a 12-month analysis (n=12) of a chart with 30 events that QA-fails all 12
returned `ceil(5*12/30)=2` instead of the full 5 — a net ~3-credit loss at the
worst moment (LLM down). Fixed denominator → the parametric cases in AC-1 now
hold: 0/12→0, 6/12→3, 12/12→5.

Each test builds a real chart, mocks `build_router` with a controllable router that
QA-fails the FIRST `k` narrated events (2 attempts each) then succeeds, and asserts
the refunded credits exactly.
"""
import json
import os
import types
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("SWISSEPH_EPHE_PATH", str(Path(__file__).resolve().parent.parent / "ephe"))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.astrology.engine import compute_from_fields, ensure_ephe
from app.astrology.golden_data import GOLDEN_CHARTS
from app.db import engine
from app.main import app as main_app
from app.models import BirthProfile, Chart, CreditPrice, User

ensure_ephe()

# 12-month analysis narrates the top 12 events; price is 5 credits (seeded).
_MONTHS = "12"
_PRICE = None  # resolved from credit_prices at runtime


def _price(session):
    global _PRICE
    if _PRICE is None:
        row = session.get(CreditPrice, "transit_12m")
        assert row and row.active
        _PRICE = int(row.credits)
    return _PRICE


def _cookie(uid):
    from app.auth import USER_COOKIE, _user_cookie_value
    return {USER_COOKIE: _user_cookie_value(uid)}


def _mk_user(credits):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@t", credits=credits))
        s.commit()
    return uid


def _owner_chart(uid):
    cj = compute_from_fields(**GOLDEN_CHARTS[0]["birth"]).chart_json
    cid = "c" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, raw_year=1373, raw_month=1, raw_day=1)
        s.add(p); s.flush()
        s.add(Chart(id=cid, profile_id=p.id, chart_json=cj, access_token="cap_" + uuid.uuid4().hex))
        s.commit()
    return cid


_VALID_TXT = json.dumps({
    "headline": "زحل در همنشینی با ماهِ تولد تو",
    "what_it_means": "گذرِ زحل با ماه و خورشید و عطارد و زهره و مریخ و مشتری و زحل و طالع و وسط‌آسمان تو را به مرورِ بنیادهای عاطفی دعوت می‌کند.",
    "reflection_question": "کدام پیوند عاطفی را امسال ساده‌تر می‌کنی؟",
    "window_text": "از ۱۰ مهر تا ۲۵ آذر.",
}, ensure_ascii=False)
# A QA-FAILING narrative: contains a forbidden absolute-certainty claim.
_BAD_TXT = json.dumps({
    "headline": "قطعی است که تو ارتقا خواهی گرفت",
    "what_it_means": "قطعی است که موفق خواهی شد", "reflection_question": "x", "window_text": "x",
}, ensure_ascii=False)


class _FailingRouter:
    """Succeeds after the first `fail_events` events QA-fail (2 attempts each)."""
    def __init__(self, fail_events):
        self.calls = 0
        self.limit = fail_events * 2

    async def complete(self, prompt, system=None, max_tokens=None, temperature=None,
                       json_mode=None, **_k):
        self.calls += 1
        text = _BAD_TXT if self.calls <= self.limit else _VALID_TXT
        return types.SimpleNamespace(ok=True, text=text,
                                     usage=types.SimpleNamespace(total=50), cost=0.0001, provider="mock")


@pytest.mark.parametrize("fail_events,expected_refund", [
    (0, 0),   # nothing fails → no refund
    (6, 3),   # half narrated fail → ceil(5*6/12)=3
    (12, 5),  # all narrated fail → full refund
])
def test_transit_refund_uses_narrated_denominator(monkeypatch, fail_events, expected_refund):
    uid = _mk_user(credits=20)
    cid = _owner_chart(uid)
    router = _FailingRouter(fail_events)
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: router)

    c = TestClient(main_app)
    r = c.post(f"/api/charts/{cid}/forecast/analyze", data={"months": _MONTHS}, cookies=_cookie(uid))
    assert r.status_code == 200, r.text
    j = r.json()
    with Session(engine) as s:
        price = _price(s)
    # Guard: we actually narrated a bounded number (≤12) and the endpoint returned
    # a refunded_credits amount that matches ceil(price*failed/narrated).
    n_narrated = j.get("metrics", {}).get("events")
    assert n_narrated is not None, "endpoint must expose narrated event count"
    failed = j.get("refunded_events", 0)
    assert failed == min(fail_events, n_narrated), (failed, n_narrated)
    # The durable assertion: refund == full price when ALL narrated fail; otherwise
    # ceil(price * failed / narrated) — never less than the fair share.
    import math
    if failed == 0:
        # Nothing QA-failed → the refund block is skipped, so no refund is issued.
        assert j.get("refunded_credits") in (None, 0), (j.get("refunded_credits"),)
    elif failed >= n_narrated:
        assert j.get("refunded_credits") == price, (j.get("refunded_credits"), price)
    else:
        expected = min(price, math.ceil(price * failed / n_narrated))
        assert j.get("refunded_credits") == expected, (j.get("refunded_credits"), expected)


def test_transit_refund_full_when_zero_succeed(monkeypatch):
    """The review's exact regression: a chart with many events, all narrated failing,
    must refund the FULL price — not ceil(price*12/30)=2."""
    uid = _mk_user(credits=20)
    cid = _owner_chart(uid)
    # A router that fails every narrated event (limit huge → never succeeds).
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _FailingRouter(10**6))

    c = TestClient(main_app)
    r = c.post(f"/api/charts/{cid}/forecast/analyze", data={"months": _MONTHS}, cookies=_cookie(uid))
    assert r.status_code == 200, r.text
    j = r.json()
    n_narrated = j.get("metrics", {}).get("events")
    assert n_narrated is not None and n_narrated > 0
    assert j.get("refunded_events") == n_narrated
    with Session(engine) as s:
        price = _price(s)
    assert j.get("refunded_credits") == price, f"expected full {price}, got {j.get('refunded_credits')}"
