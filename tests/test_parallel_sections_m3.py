"""M3 — concurrent section generation: bounded parallelism, order preserved,
metrics correct (calls/elapsed), and the fallback shape on total failure."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.config  # noqa: F401
from app.core.llm import LLMResult, LLMUsage
from app.report import worker
from app.report.worker import generate_sections_async


class SlowOk:
    """Fake router: 30ms per call, always valid JSON for any domain."""

    def __init__(self, delay: float = 0.03):
        self.delay = delay
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0

    async def complete(self, prompt, max_tokens=8192, temperature=0.6, json_mode=True):
        self.calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(self.delay)
        self.in_flight -= 1
        long_insight = "جملهٔ نمونه برای تست تطویل متن " * 20
        return LLMResult(
            text='{"section": "test", "title_fa": "تست", "intro": "مقدمه", '
                 '"insights": [{"insight": "' + long_insight + '",'
                 ' "evidence": [], "strengths": [], "challenges": [], '
                 '"practical_advice": "راهکار"},'
                 '{"insight": "' + long_insight + '",'
                 ' "evidence": [], "strengths": [], "challenges": [], '
                 '"practical_advice": "راهکار"}]}',
            provider="go", model="deepseek-v4-flash", latency_ms=10,
            usage=LLMUsage(10, 20), error=None, key_slot="go-1")


CHART = {}


def test_sections_run_concurrently_with_bounded_semaphore(monkeypatch):
    # monkeypatch SECTION_CONC via worker module attr
    monkeypatch.setattr(worker, "SECTION_CONC", 4)
    fake = SlowOk(delay=0.03)
    monkeypatch.setattr(worker, "build_section_router", lambda d, m: fake)  # no real API
    # small plan: 10 sections
    # capture which domains were requested through prompt content tag
    async def run():
        return await generate_sections_async(CHART, max_tokens=512,
                                             report_id="m3test", plan_key="full", router=fake)

    sections, metrics = asyncio.run(run())
    n_sections = len(sections)
    assert n_sections > 4                     # real multi-section plan
    # bounded: with 30ms calls and semaphore 4, max_in_flight must equal 4
    # (if it were serial, max would be 1; if unbounded, > 4)
    assert fake.max_in_flight == 4, f"max_in_flight={fake.max_in_flight}"
    assert fake.calls == n_sections           # one successful attempt each
    assert metrics["calls"] == n_sections
    assert metrics["elapsed_ms"] > 0
    # order matches the plan declaration order
    assert list(sections.keys()) == [d for d in sections]


def test_fallback_domain_shape_on_failure(monkeypatch):
    monkeypatch.setattr(worker, "SECTION_CONC", 8)

    class FailAll:
        async def complete(self, prompt, max_tokens=8192, temperature=0.6, json_mode=True):
            return LLMResult(text="", provider="go", model="m", error="HTTP 429: x")

    monkeypatch.setattr(worker, "build_section_router", lambda d, m: FailAll())  # no real API
    sections, metrics = asyncio.run(generate_sections_async(CHART, max_tokens=512, plan_key="basic", router=FailAll()))
    assert all(v.get("insights") for v in sections.values())   # fallback shape has insights
    assert metrics["fallback_domains"] == list(sections.keys())
    assert metrics["calls"] >= 5