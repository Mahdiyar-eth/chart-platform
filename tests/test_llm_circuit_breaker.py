"""B9 (audit r4): LLM circuit breaker + deadlines.

Regression: a failing provider was always retried first on every request
(no circuit), and a hung provider held a worker slot for up to 300s.
Now: N consecutive failures OPEN the circuit (cooldown), success closes it,
and the whole router call has a hard deadline.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.core.llm as llm
from app.core.llm import LLMResult, LLMUsage, LLMRouter


class OkProvider(llm.LLMProvider):
    name = "ok"

    async def complete(self, prompt, system=None, max_tokens=2048,
                       temperature=0.7, json_mode=False):
        self.report_success(10, LLMUsage(1, 1))
        return LLMResult(text="ok", provider=self.name, model="m")

    @staticmethod
    def estimate_cost(usage):
        return 0.0


class FailProvider(llm.LLMProvider):
    name = "fail"

    async def complete(self, prompt, system=None, max_tokens=2048,
                       temperature=0.7, json_mode=False):
        self.report_error("boom")
        return LLMResult(text="", provider=self.name, model="m", error="boom")

    @staticmethod
    def estimate_cost(usage):
        return 0.0


class SlowProvider(llm.LLMProvider):
    name = "slow"

    async def complete(self, prompt, system=None, max_tokens=2048,
                       temperature=0.7, json_mode=False):
        await asyncio.sleep(30)
        return LLMResult(text="never", provider=self.name, model="m")

    @staticmethod
    def estimate_cost(usage):
        return 0.0


def test_circuit_opens_after_threshold_and_skips_failing_provider(monkeypatch):
    """After 3 consecutive failures the provider's circuit OPENs and it is
    skipped from ranking; a later success closes the breaker."""
    failer, ok = FailProvider(), OkProvider()
    r = LLMRouter([failer])
    monkeypatch.setattr(llm, "_CIRCUIT_THRESHOLD", 3)
    monkeypatch.setattr(llm, "_CIRCUIT_COOLDOWN", 60)

    # 3 consecutive failures (no healthy peer to rescue) → circuit opens
    for _ in range(3):
        asyncio.run(r.complete("x"))
    assert failer.tripped(), "circuit must OPEN after 3 consecutive failures"

    # with a healthy provider present, the tripped one is skipped entirely
    r2 = LLMRouter([failer, ok])
    assert [p.name for p in r2._rank()] == ["ok"], "open circuit must not be ranked"

    # success closes the circuit
    failer.health.tripped_until = 0.0
    failer.report_success(5, LLMUsage(1, 1))
    assert not failer.tripped()


def test_deadline_aborts_slow_provider(monkeypatch):
    """A hung provider must not hold the call past the deadline."""
    slow = SlowProvider()
    r = LLMRouter([slow])
    monkeypatch.setattr(llm, "_DEADLINE", 0.15)
    res = asyncio.run(r.complete("x"))
    assert res.error and "deadline" in res.error.lower()


def test_all_tripped_falls_back_so_request_never_deadlocks():
    """If EVERY provider's circuit is open, still try them (no deadlock)."""
    failer = FailProvider()
    failer.health.error_streak = 99
    failer.health.tripped_until = 10 ** 12  # open until year ~33658
    r = LLMRouter([failer])
    res = asyncio.run(r.complete("x"))
    assert res.error == "boom"  # it WAS tried despite the open circuit
