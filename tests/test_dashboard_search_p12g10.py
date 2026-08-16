"""G10 (§90) — dashboard search index renders and stays owner-scoped."""
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import BirthProfile, Chart, User
from tests.conftest import fake_authority


def test_dashboard_search_index_present():
    from app.auth import _user_cookie_value
    with Session(engine) as s:
        u = User(phone=f"+98g10{fake_authority(8)}", credits=10)
        s.add(u); s.commit(); s.refresh(u)
        p = BirthProfile(user_id=u.id, name="علی", raw_year=1373, raw_month=6, raw_day=1,
                         hour=6, minute=10, city_fa="تهران", time_known=True)
        s.add(p); s.commit(); s.refresh(p)
        c = Chart(profile_id=p.id, chart_json={"planets": {"Sun": {"longitude": 120.0}}})
        s.add(c); s.commit(); s.refresh(c)
        uid = u.id
    c = TestClient(app)
    c.cookies.set("chart_user", _user_cookie_value(uid))
    r = c.get("/account")
    assert r.status_code == 200
    assert "داشبورد" not in r.text  # no leakage of the word dashboard
    assert "علی" in r.text
    assert "جستجو در چارت" in r.text
