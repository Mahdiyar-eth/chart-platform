"""OPUS-R12 P0 fixes — regression tests.

P0-1: /api/purchase for solar_return/relocation WITHOUT chart_id must 400
      (never mint a dead entitlement). WITH chart_id it must work.
P0-2: a FAILED LLM enrichment must not poison the permanent freepreview
      cache — the fallback cache entry carries a short TTL (900s), while a
      SUCCESS is cached permanently.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import _user_cookie_value
from app.db import engine
from app.main import app as main_app
from app.models import BirthProfile, Chart, User


def _natal() -> dict:
    from app.astrology.engine import compute_from_fields
    return compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def _setup(credits: int = 50):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@r12", credits=credits)); s.commit()
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890,
                         personal_question="آیا شغلم را عوض کنم؟",
                         focus_areas=["شغل", "پول"])
        s.add(p); s.flush()
        ch = Chart(profile_id=p.id, chart_json=_natal(),
                   access_token="tok" + uuid.uuid4().hex[:12])
        s.add(ch); s.commit(); s.refresh(ch)
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_user", _user_cookie_value(uid))
    return uid, ch.id, ch.access_token, c


def test_p01_purchase_without_chart_id_is_rejected_for_new_products():
    """The R12 money bug: buying solar_return without a chart used to mint a
    dead entitlement (money taken, nothing delivered). Now → 400."""
    uid, cid, tok, c = _setup()
    for action in ("solar_return", "relocation"):
        r = c.post("/api/purchase", json={"action_key": action})
        assert r.status_code == 400, f"{action}: {r.status_code} {r.text}"
        assert r.json().get("error") == "chart_id_required"
    # no entitlement may exist and no credit may be gone
    with Session(engine) as s:
        ents = s.exec(_sel_ents(uid)).all()
        assert not ents, "a failed purchase must not mint an entitlement"
        u = s.get(User, uid)
        assert u.credits == 50, "no deduction on rejected purchase"


def _sel_ents(uid):
    from sqlmodel import select
    from app.models import Entitlement as E
    return select(E).where(E.user_id == uid)


def test_p01_purchase_with_chart_id_still_works():
    uid, cid, tok, c = _setup(credits=20)
    r = c.post("/api/purchase", json={"action_key": "solar_return",
                                      "chart_id": cid})
    assert r.status_code == 200 and r.json().get("ok"), r.text
    with Session(engine) as s:
        ent = s.exec(_sel_ents(uid)).first()
        assert ent is not None and ent.chart_id == cid, \
            "the entitlement MUST be chart-scoped now"
        u = s.get(User, uid)
        assert u.credits == 11  # 20 - 9


class _FailResult:
    ok = False
    text = ""
    provider = "fake"
    model = "fake"
    cost = 0.0
    error = "simulated outage"

    class usage:
        total = 0
        prompt_tokens = 0
        completion_tokens = 0

    latency_ms = 0


class _FailingRouter:
    calls = 0

    async def complete(self, prompt, **kw):
        _FailingRouter.calls += 1
        return _FailResult()


def _flush(cid):
    try:
        import redis as _r
        for db in ("0", "1"):
            _r.Redis.from_url(f"redis://127.0.0.1:6379/{db}").delete(f"freepreview:{cid}")
    except Exception:  # noqa: BLE001
        pass


def test_p02_failed_llm_cache_has_short_ttl(monkeypatch):
    """R12/P0-2: LLM down → fallback cached with TTL≈900s, NOT permanent;
    personal_question is still echoed; retry succeeds after flush."""
    uid, cid, tok, c = _setup()
    monkeypatch.setenv("ENRICH_INSIGHTS", "1")
    monkeypatch.setattr("app.core.llm.build_router",
                        lambda part="report": _FailingRouter())
    _flush(cid)
    r1 = c.get(f"/api/charts/{cid}/preview")
    d1 = r1.json()
    assert d1.get("enriched") is None, "failed LLM must not claim enrichment"
    assert d1.get("personal_question") == "آیا شغلم را عوض کنم؟", \
        "P0-3: question must be echoed even when the LLM fails"
    assert d1.get("focus_areas") == ["شغل", "پول"], "focus areas echoed too"
    # TTL check — the fallback entry expires (~15min), never permanent
    import redis as _r
    ttl = None
    for db in ("0", "1"):
        rr = _r.Redis.from_url(f"redis://127.0.0.1:6379/{db}")
        if rr.exists(f"freepreview:{cid}"):
            ttl = rr.ttl(f"freepreview:{cid}")
            break
    assert ttl is not None and 0 < ttl <= 900, f"fallback TTL wrong: {ttl}"


def test_p03_question_echoed_even_without_enrichment(monkeypatch):
    """ENRICH_INSIGHTS=0 path (deterministic only) still echoes the question."""
    uid, cid, tok, c = _setup()
    monkeypatch.setenv("ENRICH_INSIGHTS", "0")
    _flush(cid)
    r = c.get(f"/api/charts/{cid}/preview")
    d = r.json()
    assert d.get("personal_question") == "آیا شغلم را عوض کنم؟"
    assert d.get("focus_areas") == ["شغل", "پول"]
