"""C6 (audit r4): data lifecycle — account deletion cascades EVERYTHING
(charts, chats, reports + R2 objects, orders, subscriptions, referrals),
and the privacy page states the real AI providers.

Regression: deleting an account used to orphan rows (reports/R2 kept leaking
birth data). Verified cascade now, and privacy.html names DeepSeek/OpenCode
(not "OpenAI").
"""
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app as main_app
from app.auth import USER_COOKIE, _user_cookie_value
from app.db import engine
from app.models import (BirthProfile, Chart, ChatMessage, Order, Report,
                        Subscription, User)


def _seed_user_with_data(s) -> tuple[User, str, str]:
    u = User(phone="0912" + uuid.uuid4().hex[:8])
    s.add(u)
    s.commit()
    s.refresh(u)
    p = BirthProfile(user_id=u.id, name="تست", raw_year=1994, raw_month=8,
                     raw_day=23, time_known=True, hour=6, minute=10,
                     city_fa="تهران", lat=35.69, lon=51.39)
    s.add(p)
    s.commit()
    s.refresh(p)
    chart = Chart(profile_id=p.id, chart_json={"planets": {}}, name="تست")
    s.add(chart)
    s.commit()
    s.refresh(chart)
    rep = Report(chart_id=chart.id, status="done", plan_key="gold",
                 r2_key="chart-reports/x.pdf", sections={"a": {"title": "t"}})
    s.add(rep)
    s.add(ChatMessage(chart_id=chart.id, role="user", content="سلام"))
    s.add(Subscription(chart_id=chart.id, active=True, expires_at=None))
    s.add(Order(chart_id=chart.id, plan_key="gold", status="paid",
                amount_rial=99000, authority="AU" + uuid.uuid4().hex[:8],
                ref_id="REF1"))
    s.commit()
    return u, chart.id, rep.id


def test_account_delete_cascades_all_data(monkeypatch):
    deleted = []
    monkeypatch.setattr("app.storage.delete_object", lambda key: deleted.append(key))
    c = TestClient(main_app)
    with Session(engine) as s:
        u, cid, rep_id = _seed_user_with_data(s)
        uid = u.id
    c.cookies.update({USER_COOKIE: _user_cookie_value(uid), "csrf_token": "t1"})
    r = c.post("/account/delete", data={"csrf_token": "t1"},
               follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as s:
        assert s.get(User, uid) is None
        assert s.get(Chart, cid) is None
        assert s.get(Report, rep_id) is None
        assert s.exec(select(ChatMessage).where(ChatMessage.chart_id == cid)).all() == []
        assert s.exec(select(Subscription).where(Subscription.chart_id == cid)).all() == []
        assert s.exec(select(Order).where(Order.chart_id == cid)).all() == []
        profiles = s.exec(select(BirthProfile)).all()
        assert profiles == [] or all(p.user_id != uid for p in profiles)
    assert "chart-reports/x.pdf" in deleted, "R2 object must be deleted too"


def test_account_delete_requires_auth_and_csrf():
    c = TestClient(main_app)
    # no session cookie → redirect to login
    r = c.post("/account/delete", data={"csrf_token": "x"}, follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as s:
        u, _, _ = _seed_user_with_data(s)
        uid = u.id
    # authenticated but wrong CSRF → 403
    c.cookies.update({USER_COOKIE: _user_cookie_value(uid), "csrf_token": "right"})
    r = c.post("/account/delete", data={"csrf_token": "wrong"})
    assert r.status_code == 403
    with Session(engine) as s:
        assert s.get(User, uid) is not None, "wrong CSRF must NOT delete"


def test_privacy_page_names_real_ai_providers():
    c = TestClient(main_app)
    r = c.get("/privacy")
    assert r.status_code == 200
    assert "OpenAI" not in r.text
    assert "DeepSeek" in r.text and "OpenCode" in r.text
    assert "۳۰ روز" in r.text  # audio retention
