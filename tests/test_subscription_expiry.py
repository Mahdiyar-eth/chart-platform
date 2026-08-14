"""A9/B8 (audit r4): monthly subscriptions EXPIRE — chat requires an unexpired
Subscription row; renewal EXTENDS from the later of (expiry, now); one
subscription per (chart, account)."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

import app.main as main_mod
from app.db import engine
from app.models import Order, Subscription
from app.payment.orders import activate_subscription


def _mk_chart(c: TestClient) -> tuple[str, str]:
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    }).json()
    return d["chart_id"], d["access_token"]


def _order(s: Session, cid: str, chat_id: str | None = None) -> Order:
    o = Order(chart_id=cid, plan_key="monthly", status="paid",
              amount_rial=3_990_000, chat_id=chat_id, platform="telegram" if chat_id else None)
    s.add(o)
    s.flush()
    return o


@pytest.fixture()
def chat_mock(monkeypatch):
    monkeypatch.setattr(main_mod, "chat_answer",
                        lambda *a, **k: {"answer": "پاسخ تستی", "ok": True,
                                         "intent": "i", "domains": [], "tokens": 1})
    monkeypatch.setattr(main_mod, "_rate_limit", lambda *a, **k: True)


def _sub(s: Session, cid: str, chat: str):
    return s.exec(select(Subscription).where(
        Subscription.chat_id == chat, Subscription.chart_id == cid)).first()


def test_renewal_extends_from_current_expiry():
    c = TestClient(main_mod.app)
    cid, _ = _mk_chart(c)
    with Session(engine) as s:
        o1 = _order(s, cid, chat_id="tg-9")
        activate_subscription(s, o1)
        s.commit()
        sub = _sub(s, cid, "tg-9")
        # simulate 20 days already used
        sub.expires_at = datetime.now(timezone.utc) + timedelta(days=20)
        s.add(sub)
        s.commit()
        o2 = _order(s, cid, chat_id="tg-9")
        activate_subscription(s, o2)
        s.commit()
        s.refresh(sub)
        # renewed from expiry (20 days) + 30 → ~50 days, NOT 30
        from app.timeutil import ensure_utc
        days_left = (ensure_utc(sub.expires_at) - datetime.now(timezone.utc)).total_seconds() / 86400
        assert 48 <= days_left <= 52, f"expected ~50 days, got {days_left:.1f}"


def test_expired_subscription_blocks_chat(chat_mock):
    c = TestClient(main_mod.app)
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        o = _order(s, cid, chat_id="tg-1")
        activate_subscription(s, o)
        s.commit()
        sub = _sub(s, cid, "tg-1")
        sub.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        s.add(sub)
        s.commit()
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    r = c.post("/api/chat", data={"chart_id": cid, "question": "س"},
               )
    assert r.status_code == 403
    assert "منقضی" in r.json()["detail"]


def test_active_subscription_allows_chat(chat_mock):
    c = TestClient(main_mod.app)
    cid, tok = _mk_chart(c)
    import uuid as _uuid
    chat = f"tg-2-{_uuid.uuid4().hex[:6]}"  # unique — Redis quota counter persists
    with Session(engine) as s:
        o = _order(s, cid, chat_id=chat)
        activate_subscription(s, o)
        s.commit()
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    r = c.post("/api/chat", data={"chart_id": cid, "question": "س"},
               )
    assert r.status_code == 200, r.text


def test_access_endpoint_reports_expired_reason(chat_mock):
    c = TestClient(main_mod.app)
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        o = _order(s, cid, chat_id="tg-3")
        activate_subscription(s, o)
        s.commit()
        sub = _sub(s, cid, "tg-3")
        sub.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        s.add(sub)
        s.commit()
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    d = c.get(f"/api/chat/access/{cid}").json()
    assert d["allowed"] is False
    assert d.get("reason") == "subscription_expired"


def test_web_monthly_activation_creates_null_chat_sub():
    """Web purchase (no chat_id) still activates an unexpired subscription."""
    c = TestClient(main_mod.app)
    cid, _ = _mk_chart(c)
    with Session(engine) as s:
        o = _order(s, cid)  # chat_id=None
        activate_subscription(s, o)
        s.commit()
        sub = s.exec(
            select(Subscription).where(Subscription.chart_id == cid,
                                       Subscription.chat_id == None)  # noqa: E711
        ).first()
        assert sub is not None
        from app.timeutil import ensure_utc
        assert ensure_utc(sub.expires_at) > datetime.now(timezone.utc)
        # F-28 cleanup: leave no active web sub behind — run_weekly_delivery in
        # later tests iterates ALL active subs (push-only now, not a crash)
        s.delete(sub)
        s.exec(text("DELETE FROM charts WHERE id = :cid").bindparams(cid=cid))
        s.commit()
