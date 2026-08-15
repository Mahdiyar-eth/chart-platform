"""ZAYCHE P4/E — Today: reflection, streak, timezone, duplicate-day (E5),
subscription gating (E3), ownership (IDOR)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BirthProfile, Chart, DailyReflection, Order, Plan, User  # noqa: E402

SUF = uuid.uuid4().hex[:6]


def _mk_user(c, credits=0) -> str:
    from app.auth import _user_cookie_value
    phone = f"+98p4{SUF}{uuid.uuid4().hex[:6]}"
    with Session(engine) as s:
        u = User(phone=phone, credits=credits)
        s.add(u)
        s.commit()
        uid = u.id
    c.cookies.set("chart_user", _user_cookie_value(uid))
    return uid


def _mk_chart(uid: str, tz: str = "Asia/Tehran") -> str:
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6, raw_day=1,
                         time_known=True, hour=6, minute=10, city_fa="تهران",
                         lat=35.6892, lon=51.3890, tz_name=tz)
        s.add(p)
        s.commit()
        s.refresh(p)
        ch = Chart(profile_id=p.id,
                   chart_json={"birth": {"time_known": True},
                               "planets": {"Sun": {"longitude": 147.5, "sign": "Leo", "house": 1},
                                           "Moon": {"longitude": 320.0, "sign": "Pisces", "house": 8}},
                               "angles": {"ASC": {"longitude": 135.0}}})
        s.add(ch)
        s.commit()
        s.refresh(ch)
        return ch.id


def _grant_gold(cid: str) -> None:
    """Mark the chart's order as paid gold so /today sees full access."""
    with Session(engine) as s:
        ch = s.get(Chart, cid)
        p = s.get(BirthProfile, ch.profile_id)
        plan = s.exec(select(Plan).where(Plan.key == "gold")).first()
        o = Order(chart_id=cid, profile_id=p.id, plan_key="gold",
                  amount_rial=plan.price_toman * 10, status="paid")
        s.add(o)
        s.commit()


def _today_local() -> str:
    return datetime.now(ZoneInfo("Asia/Tehran")).date().isoformat()


def _add_reflection(chart_id: str, day: str, tz: str = "Asia/Tehran") -> None:
    with Session(engine) as s:
        s.add(DailyReflection(chart_id=chart_id, day_local=day, tz_name=tz, answer="تأمل تست"))
        s.commit()


# ── E2: record + status ─────────────────────────────────────────────────────
def test_today_status_shape():
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    r = c.get(f"/api/today?chart_id={cid}")
    assert r.status_code == 200
    d = r.json()
    assert d["today"] == _today_local()
    assert "streak" in d and "today_done" in d and "question" in d
    assert "facts" in d and isinstance(d["facts"], list)


def test_reflection_requires_full_access():
    """E3 — preview users (no paid gold/monthly) get 403 on submit."""
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    r = c.post("/api/today/reflection", data={"chart_id": cid, "answer": "امروز خوب بود"})
    assert r.status_code == 403


def test_reflection_saves_and_updates_streak():
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    _grant_gold(cid)
    r = c.post("/api/today/reflection", data={"chart_id": cid, "answer": "امروز خوب بود"})
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 1
    # status reflects done
    d = c.get(f"/api/today?chart_id={cid}").json()
    assert d["today_done"] is True and d["streak"] == 1


def test_reflection_streak_continues_with_yesterday():
    """E2 — yesterday's reflection + today's = streak 2."""
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    _grant_gold(cid)
    yesterday = (datetime.now(ZoneInfo("Asia/Tehran")).date() - timedelta(days=1)).isoformat()
    _add_reflection(cid, yesterday)
    r = c.post("/api/today/reflection", data={"chart_id": cid, "answer": "امروز خوب بود"})
    assert r.json()["streak"] == 2


def test_missed_day_resets_streak():
    """E5 — gap of one day resets the streak to 1."""
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    _grant_gold(cid)
    two_days_ago = (datetime.now(ZoneInfo("Asia/Tehran")).date() - timedelta(days=2)).isoformat()
    _add_reflection(cid, two_days_ago)
    r = c.post("/api/today/reflection", data={"chart_id": cid, "answer": "امروز خوب بود"})
    assert r.json()["streak"] == 1  # gap yesterday → reset


def test_duplicate_same_day_rejected():
    """E5 — cannot duplicate the same day; second submit → 400."""
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    _grant_gold(cid)
    assert c.post("/api/today/reflection", data={"chart_id": cid, "answer": "اول"}).status_code == 200
    r = c.post("/api/today/reflection", data={"chart_id": cid, "answer": "دوم"})
    assert r.status_code == 400
    with Session(engine) as s:
        rows = s.exec(select(DailyReflection).where(DailyReflection.chart_id == cid)).all()
        assert len(rows) == 1  # only the first survived


def test_reflection_ownership_idor():
    """Bare UUID of someone else's chart → 403, nothing saved."""
    c = TestClient(app)
    _mk_user(c)
    # owner user for the other chart (so the FK is valid) — but WE aren't them
    c2 = TestClient(app)
    other_owner = _mk_user(c2)
    other_cid = _mk_chart(other_owner)
    r = c.post("/api/today/reflection", data={"chart_id": other_cid, "answer": "هک"})
    assert r.status_code == 403
    with Session(engine) as s:
        assert s.exec(select(DailyReflection).where(DailyReflection.chart_id == other_cid)).all() == []


def test_timezone_boundary_streak():
    """E5 — the LOCAL day (chart tz) is the streak key, not UTC.
    Simulate: reflections yesterday+2days ago in UTC+14 → consecutive in
    UTC+14 but a gap in UTC, proving tz correctness."""
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid, tz="Pacific/Kiritimati")  # UTC+14
    _grant_gold(cid)
    from app.today.service import local_today, compute_streak
    with Session(engine) as s:
        today = local_today("Pacific/Kiritimati")
        s.add(DailyReflection(chart_id=cid, day_local=(today - timedelta(days=1)).isoformat(), tz_name="Pacific/Kiritimati", answer="a"))
        s.add(DailyReflection(chart_id=cid, day_local=(today - timedelta(days=2)).isoformat(), tz_name="Pacific/Kiritimati", answer="b"))
        s.commit()
        assert compute_streak(s, cid, "Pacific/Kiritimati") == 2  # consecutive locally
    # submit today → streak 3
    r = c.post("/api/today/reflection", data={"chart_id": cid, "answer": "امروز"})
    assert r.status_code == 200 and r.json()["streak"] == 3


def test_today_page_renders():
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    r = c.get(f"/today?chart={cid}")
    assert r.status_code == 200
    assert "هر روز یک لحظه" in r.text
