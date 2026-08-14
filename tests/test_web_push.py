"""D1 (audit r4): Web Push — subscribe/unsubscribe endpoints, VAPID key
endpoint, and weekly delivery triggers a push to the owning user's browsers.

pywebpush calls are mocked (no real push service in tests); VAPID keys come
from env (tests inject fake PEMs via monkeypatch).
"""
import asyncio
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

import app.push as push_mod
from app.main import app as main_app
from app.auth import USER_COOKIE, _user_cookie_value
from app.db import engine
from app.models import BirthProfile, Chart, PushSubscription, User

ENDPOINT = "https://fcm.googleapis.com/fcm/send/" + uuid.uuid4().hex


@pytest.fixture(autouse=True)
def _vapid(monkeypatch):
    monkeypatch.setattr(push_mod, "VAPID_PUBLIC_KEY", "fake-pub-key")
    monkeypatch.setattr(push_mod, "VAPID_PRIVATE_KEY", "fake-priv-key")
    yield


def test_vapid_key_endpoint():
    c = TestClient(main_app)
    r = c.get("/api/push/vapid-public-key")
    assert r.status_code == 200
    assert r.json()["key"] == "fake-pub-key"


def test_subscribe_unsubscribe_roundtrip():
    c = TestClient(main_app)
    payload = {"endpoint": ENDPOINT, "p256dh": "cGF0aA==", "auth": "YXV0aA=="}
    r = c.post("/api/push/subscribe", json=payload)
    assert r.status_code == 200
    with Session(engine) as s:
        sub = s.exec(select(PushSubscription).where(
            PushSubscription.endpoint == ENDPOINT)).first()
        assert sub is not None and sub.user_id is None
    r = c.post("/api/push/unsubscribe", json={"endpoint": ENDPOINT})
    assert r.status_code == 200
    with Session(engine) as s:
        assert s.exec(select(PushSubscription).where(
            PushSubscription.endpoint == ENDPOINT)).first() is None


def test_subscribe_rejects_bad_payload():
    c = TestClient(main_app)
    assert c.post("/api/push/subscribe", json={"endpoint": "http://not-https"}).status_code == 400
    assert c.post("/api/push/subscribe", json={}).status_code == 400


def test_subscribe_links_user_and_weekly_sends(monkeypatch):
    """Subscription with a logged-in user gets user_id; weekly delivery
    pushes to that user's browsers (send_message mocked)."""
    with Session(engine) as s:
        u = User(phone="0912" + uuid.uuid4().hex[:8])
        s.add(u)
        s.commit()
        s.refresh(u)
        uid = u.id
    c = TestClient(main_app)
    c.cookies.update({USER_COOKIE: _user_cookie_value(uid)})
    payload = {"endpoint": ENDPOINT, "p256dh": "cGF0aA==", "auth": "YXV0aA=="}
    assert c.post("/api/push/subscribe", json=payload).status_code == 200
    with Session(engine) as s:
        sub = s.exec(select(PushSubscription).where(
            PushSubscription.endpoint == ENDPOINT)).first()
        assert sub.user_id == uid

    # weekly delivery → push sent to that user
    import app.report.weekly as weekly
    sent = []
    monkeypatch.setattr("app.bots.handler.send_message", lambda *a, **k: None)
    monkeypatch.setattr(push_mod, "send_to_user",
                        lambda user_id, title, body, url, session: sent.append(
                            (user_id, title, url)))
    # fabricate a subscription + chart + profile for the user
    from app.models import Subscription as Sub, WeeklyReflection
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, name="پوش", raw_year=1994, raw_month=8,
                         raw_day=23, time_known=True, hour=6, minute=10)
        s.add(p)
        s.commit()
        s.refresh(p)
        ch = Chart(profile_id=p.id, chart_json={"planets": {}}, name="x")
        s.add(ch)
        s.commit()
        s.refresh(ch)
        cid, pid = ch.id, p.id  # read BEFORE any later commit expires them
    # F-28 hygiene: other tests may leave active subs behind; delivery
    # iterates ALL of them, so clear the slate BEFORE creating ours
    with Session(engine) as s:
        s.exec(text("DELETE FROM weekly_reflections"))
        s.exec(text("DELETE FROM subscriptions"))
        s.commit()
    with Session(engine) as s:
        s.add(Sub(chart_id=ch.id, chat_id="12345", platform="telegram", active=True))
        s.commit()
    # drop any leftover WeeklyReflection for this chart (per-run cleanup —
    # the DB persists between runs, and `already` skips delivery)
    with Session(engine) as s:
        for w in s.exec(select(WeeklyReflection).where(
                WeeklyReflection.chart_id == cid)).all():
            s.delete(w)
        s.commit()
    import app.bots.handler as _handler
    monkeypatch.setattr(_handler, "send_message",
                        lambda chat_id, text, platform: asyncio.sleep(0))
    out = asyncio.run(weekly.run_weekly_delivery())
    assert out["sent"] == 1
    assert len(sent) == 1 and sent[0][0] == uid and sent[0][2] == "/account"
    # cleanup (push_subscriptions BEFORE user — FK)
    with Session(engine) as s:
        for w in s.exec(select(WeeklyReflection)).all():
            s.delete(w)
        for sub in s.exec(select(Sub)).all():
            s.delete(sub)
        for ps in s.exec(select(PushSubscription)).all():
            s.delete(ps)
        s.flush()
        s.delete(s.get(Chart, cid))
        s.delete(s.get(BirthProfile, pid))
        s.delete(s.get(User, uid))
        s.commit()
