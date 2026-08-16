"""G6 (§16) — chat quick chips: static presets + dynamic Big-Three chips."""
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import BirthProfile, Chart, User
from tests.conftest import fake_authority


def test_chat_page_has_presets():
    from app.auth import _user_cookie_value
    with Session(engine) as s:
        u = User(phone=f"+98g6{fake_authority(8)}", credits=0)
        s.add(u); s.commit(); s.refresh(u)
        p = BirthProfile(user_id=u.id, name="علی", raw_year=1373, raw_month=6, raw_day=1,
                         hour=6, minute=10, city_fa="تهران", time_known=True)
        s.add(p); s.commit(); s.refresh(p)
        # Leo Sun (120°), Pisces Moon (350°), ASC Leo-ish — deterministic
        c = Chart(profile_id=p.id, chart_json={
            "planets": {"Sun": {"longitude": 120.0}, "Moon": {"longitude": 350.0}},
            "angles": {"ASC": {"longitude": 130.0}}})
        s.add(c); s.commit(); s.refresh(c)
        cid, uid = c.id, u.id
    c = TestClient(app)
    c.cookies.set("chart_user", _user_cookie_value(uid))
    r = c.get(f"/chat/{cid}")
    assert r.status_code == 200
    # static preset
    assert "الگوی روابط من چیست؟" in r.text
    # dynamic chips from Big Three (Sun=Leo)
    assert "خورشید من در Leo است" in r.text
    assert "ماه من در Pisces است" in r.text
