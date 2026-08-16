"""G8 (§57) — notification prefs: defaults, persist, validation, auth."""
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import NotificationPrefs, User
from tests.conftest import fake_authority


def _mk_user() -> User:
    from app.auth import _user_cookie_value
    u = User(phone=f"+98g8{fake_authority(8)}", credits=0)
    with Session(engine) as s:
        s.add(u)
        s.commit()
        s.refresh(u)
        u._cookie = _user_cookie_value(u.id)  # type: ignore[attr-defined]
    return u


def test_prefs_require_auth():
    c = TestClient(app)
    assert c.get("/api/notifications/prefs").status_code == 401
    assert c.post("/api/notifications/prefs").status_code == 401


def test_prefs_defaults_and_persist():
    c = TestClient(app)
    u = _mk_user()
    c.cookies.set("chart_user", u._cookie)  # type: ignore[attr-defined]

    d = c.get("/api/notifications/prefs").json()
    assert d["daily_insight"] is True and d["quiet_start"] == 23

    r = c.post("/api/notifications/prefs", data={
        "daily_insight": "false", "weekly_reflection": "true", "report_ready": "false",
        "quiet_start": "22", "quiet_end": "8"})
    assert r.status_code == 200 and r.json()["ok"]

    d2 = c.get("/api/notifications/prefs").json()
    assert d2["daily_insight"] is False and d2["report_ready"] is False
    assert d2["quiet_start"] == 22 and d2["quiet_end"] == 8

    with Session(engine) as s:
        row = s.get(NotificationPrefs, u.id)
        assert row is not None and row.daily_insight is False


def test_prefs_validate_quiet_hours():
    c = TestClient(app)
    u = _mk_user()
    c.cookies.set("chart_user", u._cookie)  # type: ignore[attr-defined]
    r = c.post("/api/notifications/prefs", data={"quiet_start": "25", "quiet_end": "7"})
    assert r.status_code == 400
