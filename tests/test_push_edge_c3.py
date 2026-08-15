"""ZAYCHE C3 — Web Push edge cases: duplicate upsert, stale/revoked
subscription handling, send-to-user fan-out, per-sub failure isolation."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import PushSubscription, User  # noqa: E402
from app.push import send_to_user, subscribe, unsubscribe  # noqa: E402

SUF = uuid.uuid4().hex[:8]
EP = "https://fcm.example.com/send/tok123"


def _user() -> str:
    with Session(engine) as s:
        u = User(phone=f"+98c3{SUF}{uuid.uuid4().hex[:6]}")
        s.add(u)
        s.commit()
        return u.id


def _cleanup(uid: str):
    with Session(engine) as s:
        for sub in s.exec(select(PushSubscription).where(
                PushSubscription.user_id == uid)).all():
            s.delete(sub)
        u = s.get(User, uid)
        if u:
            s.delete(u)
        s.commit()


def test_duplicate_subscription_upserts_not_duplicates():
    """Same endpoint subscribed twice → single row, keys refreshed."""
    uid = _user()
    try:
        with Session(engine) as s:
            assert subscribe(EP, "p1", "a1", uid, s)
        with Session(engine) as s:
            assert subscribe(EP, "p2", "a2", uid, s)
        with Session(engine) as s:
            rows = s.exec(select(PushSubscription).where(
                PushSubscription.endpoint == EP)).all()
            assert len(rows) == 1, "duplicate endpoint must upsert"
            assert rows[0].p256dh == "p2" and rows[0].auth == "a2"
    finally:
        _cleanup(uid)


def test_unsubscribe_removes_only_that_endpoint():
    uid = _user()
    try:
        with Session(engine) as s:
            subscribe(EP, "p", "a", uid, s)
            subscribe("https://fcm.example.com/send/other", "p", "a", uid, s)
        with Session(engine) as s:
            unsubscribe(EP, s)
        with Session(engine) as s:
            rows = s.exec(select(PushSubscription).where(
                PushSubscription.user_id == uid)).all()
            assert len(rows) == 1 and rows[0].endpoint != EP
    finally:
        _cleanup(uid)


def test_send_to_user_skips_failed_subscriptions_but_counts_others(monkeypatch):
    """One dead subscription must not kill the fan-out (per-sub isolation)."""
    uid = _user()
    try:
        from app import push as push_mod

        calls = []

        def fake_send_one(sub, title, body, url):
            calls.append(sub.endpoint)
            if "dead" in sub.endpoint:
                raise RuntimeError("410 Gone")
        monkeypatch.setattr(push_mod, "_send_one", fake_send_one)
        monkeypatch.setattr(push_mod, "vapid_configured", lambda: True)
        with Session(engine) as s:
            subscribe("https://fcm.example.com/send/dead1", "p", "a", uid, s)
            subscribe("https://fcm.example.com/send/alive2", "p", "a", uid, s)
            n = send_to_user(uid, "t", "b", "u", s)
        assert n == 1, "only the alive one counts"
        assert len(calls) == 2, "both attempted (dead one failed, not blocking)"
    finally:
        _cleanup(uid)


def test_subscribe_rejects_non_https():
    uid = _user()
    try:
        with Session(engine) as s:
            assert not subscribe("http://insecure.example.com/x", "p", "a", uid, s)
    finally:
        _cleanup(uid)
