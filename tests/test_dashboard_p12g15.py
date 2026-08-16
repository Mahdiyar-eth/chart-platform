"""G15 (§22) — dashboard as primary product: login gate, hero, 8 cards, CTA."""
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import BirthProfile, Chart, User
from tests.conftest import fake_authority


def test_dashboard_requires_login():
    c = TestClient(app, follow_redirects=False)
    r = c.get("/dashboard")
    assert r.status_code == 303
    assert "/account/login" in r.headers["location"]


def test_dashboard_empty_state():
    from app.auth import _user_cookie_value
    with Session(engine) as s:
        u = User(phone=f"+98g15{fake_authority(8)}", credits=0)
        s.add(u); s.commit(); s.refresh(u)
        uid = u.id
    c = TestClient(app)
    c.cookies.set("chart_user", _user_cookie_value(uid))
    r = c.get("/dashboard")
    assert r.status_code == 200
    assert "ساخت چارت رایگان" in r.text  # empty-state CTA
    assert "امروز در چارت تو چه خبر است؟" in r.text


def test_dashboard_with_chart_shows_8_cards():
    from app.auth import _user_cookie_value
    with Session(engine) as s:
        u = User(phone=f"+98g15b{fake_authority(8)}", credits=3)
        s.add(u); s.commit(); s.refresh(u)
        p = BirthProfile(user_id=u.id, name="تست", raw_year=1373, raw_month=6, raw_day=1,
                         hour=6, minute=10, city_fa="تهران", time_known=True)
        s.add(p); s.commit(); s.refresh(p)
        s.add(Chart(profile_id=p.id, chart_json={"planets": {"Sun": {"longitude": 120.0}}}))
        s.commit()
        uid = u.id
    c = TestClient(app)
    c.cookies.set("chart_user", _user_cookie_value(uid))
    r = c.get("/dashboard")
    assert r.status_code == 200
    for label in ("گفت‌وگو با چارت", "خودت را کشف کن", "سازگاری دو چارت", "کیف پول", "گزارش‌ها"):
        assert label in r.text
