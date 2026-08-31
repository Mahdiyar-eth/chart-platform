"""Report progress must describe the report actually being generated.

Two independent lies in the one progress bar the app had:

1. The worker wrote rep.sections exactly once, after asyncio.gather over every
   section had finished (worker.py). So sections_count was 0 for the entire
   multi-minute run, Math.max(repSections, 1) pinned the label at "بخش ۱ از ۱۳"
   and the fill at ~8%, and then it jumped straight to done. The single piece
   of genuine progress feedback in the product was a placebo.

2. The denominator was hardcoded to 13 in the template. A basic plan generates
   5 sections, so a basic buyer watched a bar that could only ever reach 38%.

Both are fixed by having the worker publish live progress and the API return
the real numerator and denominator.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from sqlmodel import Session

from app.db import engine
from app.models import Chart, Report

ROOT = Path(__file__).resolve().parent.parent


def test_worker_publishes_progress_incrementally():
    """A single write after gather() is what made the bar a placebo."""
    src = (ROOT / "app" / "report" / "worker.py").read_text(encoding="utf-8")
    assert "_publish_progress" in src, (
        "worker never publishes progress while sections are being generated"
    )
    # the publish must happen inside the per-section coroutine, not after gather
    gen_one = src.split("async def _gen_one", 1)[1].split("await asyncio.gather", 1)[0]
    assert "_publish_progress" in gen_one, (
        "progress is published outside the per-section loop, so it still only "
        "updates once everything has finished"
    )


def test_api_returns_a_real_denominator():
    src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    status_fn = src.split("def api_report_status", 1)[1].split("\n@app.", 1)[0]
    assert "sections_total" in status_fn, (
        "the status endpoint returns no section total, so the client has to "
        "hardcode one — and 13 is wrong for every basic plan"
    )
    assert "sections_done" in status_fn


def test_template_does_not_hardcode_thirteen():
    src = (ROOT / "app" / "templates" / "chart.html").read_text(encoding="utf-8")
    # The denominator sits after an inline <b>, so a [^<] window never reaches
    # it — look at the whole progress block instead.
    block = re.search(r"در حال نوشتن گزارش.{0,600}?</div>", src, re.S)
    assert block, "report progress block not found"
    assert "۱۳" not in block.group(0), (
        "chart.html hardcodes a 13-section denominator — a basic plan has 5 "
        "sections and its bar could never pass 38%"
    )
    assert "/ 13" not in block.group(0), "width still divides by a hardcoded 13"
    assert "repTotal" in block.group(0), "denominator does not come from the server"


def test_progress_publish_is_atomic():
    """Four sections finish concurrently (SECTION_CONC=4); a read-modify-write
    in Python would lose increments."""
    src = (ROOT / "app" / "report" / "worker.py").read_text(encoding="utf-8")
    fn = src.split("def _publish_progress", 1)[1].split("\ndef ", 1)[0]
    assert "jsonb_set" in fn or "UPDATE" in fn.upper(), (
        "progress must be incremented by the database, not read-modify-written "
        "in Python, or concurrent sections lose counts"
    )


def test_progress_counter_climbs_under_concurrency():
    """Prove it with real concurrent writers against the real database."""
    from app.report.worker import _publish_progress

    with Session(engine) as s:
        ch = Chart(chart_json={}, access_token="t-prog")
        s.add(ch)
        s.commit()
        rep = Report(chart_id=ch.id, status="running", plan_key="full")
        s.add(rep)
        s.commit()
        rid = rep.id

    async def drive():
        await asyncio.gather(*(asyncio.to_thread(_publish_progress, rid, 13)
                               for _ in range(13)))

    asyncio.run(drive())

    with Session(engine) as s:
        m = s.get(Report, rid).metrics or {}
    assert m.get("sections_done") == 13, (
        f"13 concurrent completions produced sections_done={m.get('sections_done')} "
        "— increments were lost"
    )
    assert m.get("sections_total") == 13


def test_progress_climbs_during_a_real_generation(monkeypatch):
    """End-to-end, no paid calls: run generate_sections_async against a stub
    router and watch the database counter move while it runs.

    This is the assertion that would have caught the placebo bar: the old code
    passed every unit test about sections and metrics, because the only thing
    wrong was *when* the number appeared.
    """
    import app.config  # noqa: F401
    from app.core.llm import LLMResult, LLMUsage
    from app.report import worker
    from app.report.worker import generate_sections_async

    long_insight = "جملهٔ نمونه برای تست تطویل متن " * 20
    body = ('{"section": "test", "title_fa": "تست", "intro": "مقدمه", '
            '"insights": [{"insight": "' + long_insight + '", "evidence": [], '
            '"strengths": [], "challenges": [], "practical_advice": "راهکار"},'
            '{"insight": "' + long_insight + '", "evidence": [], '
            '"strengths": [], "challenges": [], "practical_advice": "راهکار"}]}')

    observed: list[int] = []

    class Stub:
        async def complete(self, prompt, max_tokens=8192, temperature=0.6, json_mode=True):
            await asyncio.sleep(0.02)
            with Session(engine) as s:
                m = (s.get(Report, rid).metrics or {})
                observed.append(int(m.get("sections_done") or 0))
            return LLMResult(text=body, provider="stub", model="stub",
                             latency_ms=1, usage=LLMUsage(10, 20), error=None)

    with Session(engine) as s:
        ch = Chart(chart_json={}, access_token="t-prog-e2e")
        s.add(ch)
        s.commit()
        rep = Report(chart_id=ch.id, status="running", plan_key="full")
        s.add(rep)
        s.commit()
        rid = rep.id

    stub = Stub()
    monkeypatch.setattr(worker, "build_section_router", lambda d, m: stub)

    sections, _metrics = asyncio.run(generate_sections_async(
        {}, max_tokens=512, report_id=rid, plan_key="full", router=stub))

    with Session(engine) as s:
        final = (s.get(Report, rid).metrics or {})

    assert final.get("sections_done") == len(sections), (
        f"counter ended at {final.get('sections_done')} for {len(sections)} sections"
    )
    assert final.get("sections_total") == len(sections)
    # the whole point: it moved *during* the run, not only at the end
    assert max(observed) > 0, (
        "sections_done was 0 for every call — progress is still only published "
        "after generation finishes, which is exactly the placebo bar"
    )
    assert len(set(observed)) > 1, f"counter never changed mid-run: {observed}"
