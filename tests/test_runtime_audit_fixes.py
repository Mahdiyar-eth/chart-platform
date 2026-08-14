"""F-24 / F-25 (browser runtime audit) regression tests.

F-24 (P1): report worker crashed with DetachedInstanceError AFTER the report
           was fully generated (status read outside the session) — 8 minutes
           of LLM work wasted, then ARQ retried the whole job.
F-25 (P1): _enqueue_report used a global ARQ pool created inside asyncio.run()
           — the second request ran in a different thread → "attached to a
           different loop" → "queue unavailable at payment time".
"""
import threading

from sqlmodel import Session

import app.main as main_mod
from app.db import engine
from app.models import Chart, Report, User

_TEST_CHART = {
    "birth": {"lat": 35.6889, "lon": 51.4297, "tz_name": "Asia/Tehran",
              "utc_time": "1994-08-23 01:40:00", "local_time": "1994-08-23 06:10",
              "time_known": True, "city_fa": "تهران"},
    "planets": {"Sun": {"longitude": 149.716514, "sign_fa": "اسد", "sign_en": "Leo",
                        "degree": 29.71, "house": 1, "retrograde": False},
                "Moon": {"longitude": 351.0, "sign_fa": "حوت", "sign_en": "Pisces",
                         "degree": 21.0, "house": 8, "retrograde": False}},
    "angles": {"ASC": {"longitude": 144.971753, "house": 1}},
    "houses": {"h1": 144.97, "h10": 50.0},
}


def _mk_report():
    with Session(engine) as s:
        u = User(phone="9991000" + str(__import__("uuid").uuid4().hex[:6]))
        s.add(u)
        s.commit()
        s.refresh(u)
        c = Chart(chart_json=_TEST_CHART, engine_config={}, access_token="t-runtime")
        s.add(c)
        s.commit()
        s.refresh(c)
        rep = Report(chart_id=c.id, status="queued", plan_key="basic")
        s.add(rep)
        s.commit()
        s.refresh(rep)
        return rep.id, c.id


# ── F-24: worker must NOT crash after a successful generation
def test_worker_finishes_after_done_without_detached_error(monkeypatch):
    import app.report.worker as w

    async def fake_generate(router, chart_json, **kw):
        return {"identity": {"section": "identity", "title_fa": "هویت",
                             "intro": "x", "insights": [{"insight": "i", "evidence": [],
                                                         "strengths": [], "challenges": [],
                                                         "recommendations": []}]}}, {"fallback_domains": []}

    monkeypatch.setattr(w, "generate_sections_async", fake_generate)
    monkeypatch.setattr(w, "render_report_pdf", lambda *a, **k: "/tmp/x.pdf")
    monkeypatch.setattr(w, "REPORTS_DIR", __import__("pathlib").Path("/tmp"))
    indexed = []

    def fake_upload(*a, **k):
        return "r2://reports/x.pdf"

    monkeypatch.setattr("app.storage.upload_report", fake_upload)

    def fake_index(report_id):
        indexed.append(report_id)
        return 3

    monkeypatch.setattr("app.rag.index_report", fake_index)

    rep_id, _ = _mk_report()
    # run the ARQ job function directly
    import asyncio
    asyncio.run(w.generate_report({"router": None}, rep_id))

    with Session(engine) as s:
        rep = s.get(Report, rep_id)
        assert rep.status == "done", rep.error
    assert indexed == [rep_id], "RAG index must run for done reports"


# ── F-25: enqueue must succeed from ANY thread (fresh pool per call)
def test_enqueue_succeeds_from_multiple_threads(monkeypatch):
    monkeypatch.setattr(main_mod, "_REDIS_URL", "redis://127.0.0.1:6379/0")
    rep_id, _ = _mk_report()
    results = []

    def worker():
        results.append(main_mod._enqueue_report(rep_id))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [True, True, True, True], results
