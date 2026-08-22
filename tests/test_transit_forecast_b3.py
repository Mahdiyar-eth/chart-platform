"""B3 — transit forecast API + page acceptance tests (LLM mocked → $0, no live spend)."""
import os, json, types, uuid
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
os.environ["SWISSEPH_EPHE_PATH"] = "/root/chart-platform/ephe"
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.db import engine
from app.main import app as main_app
from app.models import BirthProfile, Chart, User
from app.astrology.engine import compute_from_fields, ensure_ephe
from app.astrology.golden_data import GOLDEN_CHARTS
from app.credits import grant as credit_grant
from app.auth import _user_cookie_value


def _cookie(uid):
    from app.auth import USER_COOKIE, _user_cookie_value
    return {USER_COOKIE: _user_cookie_value(uid)}


def _mk_user(credits=0):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        u = User(id=uid, phone=uid + "@t", credits=credits)
        s.add(u); s.commit()
        if credits:
            s.refresh(u)
        return uid


def _owner_chart(uid, free=True):
    ensure_ephe()
    cj = compute_from_fields(**GOLDEN_CHARTS[0]["birth"]).chart_json
    cid = "c" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, raw_year=1373, raw_month=1, raw_day=1)
        s.add(p); s.flush()
        c = Chart(id=cid, profile_id=p.id, chart_json=cj, access_token=("cap_" + uuid.uuid4().hex) if free else None)
        s.add(c); s.commit()
        return cid


def _mock_payload():
    return json.dumps({"headline": "زحل در همنشینی با ماهِ تولد تو", "what_it_means": "گذرِ زحل با ماه از ۱۰ مهر تا ۲۵ آذر تو را به مرورِ بنیادهای عاطفی دعوت می‌کند.", "reflection_question": "کدام پیوند عاطفی را امسال ساده‌تر می‌کنی؟", "window_text": "بازه ۲۰۲۶-۱۰-۰۱ تا ۲۰۲۶-۱۲-۱۵."}, ensure_ascii=False)


_TGT = ["خورشید", "ماه", "عطارد", "ناهید", "مریخ", "مشتری", "زحل", "طالع", "میانه آسمان"]


def _mock_router():
    class _R:
        async def complete(self, prompt, system=None, max_tokens=None, temperature=None, json_mode=None, **_k):
            t = "ماه و خورشید و عطارد و زهره و مریخ و مشتری و زحل و طالع و وسط‌آسمان"
            text = json.dumps({
                "headline": f"گذر زحل در تربیع با {t}",
                "what_it_means": f"این گذر زمینه‌ای برای مرور بنیان‌های مرتبط با {t} است؛ بلوغ در مرز آن می‌آید.",
                "reflection_question": "کدام حلقه را می‌خواهی آگاهانه رها کنی؟",
                "window_text": "بازهٔ حساس از ۲۰۲۶-۱۰-۰۱ تا ۲۰۲۶-۱۲-۱۵.",
            }, ensure_ascii=False)
            return types.SimpleNamespace(ok=True, text=text, usage=types.SimpleNamespace(total=50), cost=0.0001, provider="mock")
    return _R()


def _stub_build_router(monkeypatch):
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _mock_router())


def test_forecast_free_returns_events(monkeypatch):
    uid = _mk_user(credits=0)
    cid = _owner_chart(uid)
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _mock_router())
    c = TestClient(main_app)
    r = c.get(f"/api/charts/{cid}/forecast?months=3", cookies=_cookie(uid))
    assert r.status_code == 200
    assert isinstance(r.json().get("events"), list)


def test_forecast_foreign_403(monkeypatch):
    owner = _mk_user(); uid2 = _mk_user()
    cid = _owner_chart(owner)
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _mock_router())
    c = TestClient(main_app)
    r = c.get(f"/api/charts/{cid}/forecast?months=3", cookies=_cookie(uid2))
    assert r.status_code == 403


def test_analyze_not_logged_in_401():
    cid = _owner_chart(_mk_user(credits=5))
    c = TestClient(main_app)
    r = c.post(f"/api/charts/{cid}/forecast/analyze", data={"months": "12"})
    assert r.status_code == 401


def test_analyze_insufficient_402(monkeypatch):
    uid = _mk_user(credits=0)
    cid = _owner_chart(uid, free=True)
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _mock_router())
    c = TestClient(main_app)
    r = c.post(f"/api/charts/{cid}/forecast/analyze", data={"months": "12"}, cookies=_cookie(uid))
    assert r.status_code == 402
    assert r.json().get("credit_packs") is True


def test_analyze_success_spends_credit(monkeypatch):
    uid = _mk_user(credits=5)
    cid = _owner_chart(uid, free=True)
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _mock_router())
    c = TestClient(main_app)
    r = c.post(f"/api/charts/{cid}/forecast/analyze", data={"months": "12"}, cookies=_cookie(uid))
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("narratives"), list) and j["narratives"]
    with Session(engine) as s:
        assert s.get(User, uid).credits == 0  # transit_12m = 5 credits spent


def test_transits_page_renders(monkeypatch):
    uid = _mk_user(credits=0)
    cid = _owner_chart(uid)
    monkeypatch.setattr("app.core.llm.build_router", lambda part=None: _mock_router())
    c = TestClient(main_app)
    r = c.get(f"/transits/{cid}", cookies=_cookie(uid))
    assert r.status_code == 200
    assert "گذرهای پیشِ رو" in r.text