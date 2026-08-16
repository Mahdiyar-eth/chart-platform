"""G1 (§138) — account data export: owner-only JSON with profiles/charts/
reports/orders/chat/ledger + signed artifact URLs. No secrets in payload.
"""
import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import BirthProfile, Chart, Report, User

from tests.conftest import fake_authority  # noqa: F401


def _mk_user() -> User:
    from app.auth import _user_cookie_value
    u = User(phone=f"+98g1{fake_authority(8)}", credits=5)
    with Session(engine) as s:
        s.add(u)
        s.commit()
        s.refresh(u)
        u._cookie = _user_cookie_value(u.id)  # type: ignore[attr-defined]
    return u


def _login(client: TestClient, u: User):
    client.cookies.set("chart_user", u._cookie)  # type: ignore[attr-defined]


def test_export_requires_login():
    c = TestClient(app, follow_redirects=False)
    r = c.get("/account/export")
    assert r.status_code == 303
    assert "/account/login" in r.headers["location"]


def test_export_owner_full_payload():
    from app.models import WeeklyReflection
    c = TestClient(app)
    u = _mk_user()
    with Session(engine) as s:
        p = BirthProfile(user_id=u.id, name="خودم", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890)
        s.add(p)
        s.flush()
        ch = Chart(profile_id=p.id, chart_json={"schema_version": 3, "planets": {}})
        s.add(ch)
        s.flush()
        s.add(Report(chart_id=ch.id, plan_key="full", status="done",
                     sections={"identity": {"text": "x"}}))
        s.add(WeeklyReflection(chart_id=ch.id, week_start="2026-08-10", text="بازتاب"))
        s.commit()

    _login(c, u)
    r = c.get("/account/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers.get("content-disposition", "")
    data = json.loads(r.text)

    assert data["schema_version"] == 1
    assert data["user"]["id"] == u.id
    assert data["user"]["phone"] == u.phone
    assert "password_hash" not in json.dumps(data)
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["city_fa"] == "تهران"
    assert len(data["charts"]) == 1
    assert data["charts"][0]["chart_json"]["schema_version"] == 3
    assert len(data["reports"]) == 1
    assert data["reports"][0]["plan_key"] == "full"
    assert data["reports"][0]["pdf_download_url"] is None
    assert len(data["weekly_reflections"]) == 1


def test_export_isolated_between_users():
    c = TestClient(app)
    u = _mk_user()
    other = _mk_user()
    with Session(engine) as s:
        s.add(BirthProfile(user_id=u.id, name="A-secret", raw_year=1370,
                           raw_month=1, raw_day=1, time_known=False))
        s.commit()

    _login(c, other)
    data = json.loads(c.get("/account/export").text)
    assert data["profiles"] == []
    assert "A-secret" not in json.dumps(data)
