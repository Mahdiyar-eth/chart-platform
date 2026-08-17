"""A11 (ChatGPT directive) — LLM degraded: never fake done, never silent."""
import asyncio

from sqlmodel import Session, select

from app.db import engine
from app.models import BirthProfile, Chart, Report, User
from tests.conftest import fake_authority


class _NoLLM:
    """Router that behaves like a totally down provider."""
    class _Res:
        ok = False
        text = ""
        error = "provider down (simulated)"
        provider = "fake-down"
        model = "fake"
        cost = 0.0
        usage = type("U", (), {"total": 0, "prompt_tokens": 0, "completion_tokens": 0})()
        latency_ms = 0

    async def complete(self, *a, **k):
        return self._Res()


def _seed_report():
    from app.astrology.engine import compute_from_fields
    chart_json = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json
    with Session(engine) as s:
        u = User(phone='+98a11' + fake_authority(8), credits=10)
        s.add(u); s.commit(); s.refresh(u)
        p = BirthProfile(user_id=u.id, name='ن', raw_year=1373, raw_month=6, raw_day=1,
                         hour=6, minute=10, city_fa='تهران', time_known=True)
        s.add(p); s.commit(); s.refresh(p)
        c = Chart(profile_id=p.id, chart_json=chart_json)
        s.add(c); s.commit(); s.refresh(c)
        r = Report(chart_id=c.id, plan_key='basic', status='failed')
        s.add(r); s.commit(); s.refresh(r)
        return r.id, c.id, u.id, p.id


def test_llm_down_report_becomes_degraded_not_done():
    """Provider down → degraded (не done-fake), fallback reasons surfaced."""
    rid, cid, uid, pid = _seed_report()
    from app.report.worker import generate_report
    from app.report import worker as w
    # audit P4: no worker-level router — mock the per-section layer instead
    o1, o2 = w.section_model, w.build_section_router
    w.section_model = lambda d: "deepseek-v4-pro"
    w.build_section_router = lambda d, mm: _NoLLM()
    try:
        asyncio.run(generate_report({
            "chart_id": cid,
            "user_id": uid,
        }, rid))
    finally:
        w.section_model, w.build_section_router = o1, o2
    with Session(engine) as s:
        rep = s.get(Report, rid)
        assert rep.status == "degraded", rep.status
        assert (("fallback" in (rep.error or "").lower()) or ("budget" in (rep.error or "").lower())
        or ("بخش" in (rep.error or "")))
        assert rep.pdf_path  # artifact was still generated (intro-only sections)
        assert rep.sections  # never a half-written JSON
        # every section must be the honest fallback intro, not fake analysis
        for dom in rep.sections.values():
            assert dom["intro"].startswith("بر اساس عوامل"), dom["intro"][:40]


def test_llm_down_requeue_still_degrades_after_retry():
    """Re-queue while provider is down must NOT flip to done."""
    rid, cid, uid, pid = _seed_report()
    from app.report.worker import generate_report
    from app.report import worker as w
    o1, o2 = w.section_model, w.build_section_router
    w.section_model = lambda d: "deepseek-v4-pro"
    w.build_section_router = lambda d, mm: _NoLLM()
    try:
        for _ in range(2):  # two independent runs, both degraded
            with Session(engine) as s:
                rep = s.get(Report, rid)
                rep.status = "queued"
                s.add(rep); s.commit()
            asyncio.run(generate_report({
                "chart_id": cid, "user_id": uid,
            }, rid))
            with Session(engine) as s:
                assert s.get(Report, rid).status == "degraded"
    finally:
        w.section_model, w.build_section_router = o1, o2


def test_degraded_requeue_endpoint_allowed():
    """Admin regenerate on degraded → re-queued (same report, no dup)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models import Order
    rid, cid, uid, pid = _seed_report()
    with Session(engine) as s:
        o = Order(user_id=uid, chart_id=cid, profile_id=pid, amount_rial=1490000,
                  plan_key='basic', status='paid', authority='authtest')
        s.add(o); s.commit(); s.refresh(o)
        oid = o.id
    c = TestClient(app)
    # force admin: reuse the session's internal admin flag via cookie impersonation
    from app.main import _admin_cookie_value
    c.cookies.update({"chart_admin": _admin_cookie_value()})
    r = c.post(f"/api/admin/orders/{oid}/regenerate")
    assert r.status_code == 200, (r.status_code, r.text)
    with Session(engine) as s:
        n = s.exec(select(Report).where(Report.chart_id == cid)).all()
        assert len(n) == 1  # degraded → requeue same row, no version dup
        assert n[0].status == "queued"

