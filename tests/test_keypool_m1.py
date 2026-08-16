"""M1 — Go KeyPool: per-key breaker, empty-200 detection, quota backoff,
least-busy pick, pool identity, and the Zen free-tier last-resort fallback.

M0 evidence: quotas are per-account and independent → per-key breaker is right.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.core.llm as llm
from app.core.llm import GoPoolProvider, LLMResult, LLMUsage, KeySlot, ZenFreeProvider


class FakeCaller:
    """Stands in for DeepSeekProvider — decides behaviour from the key value."""

    def __init__(self, key: str, mode: str):
        self.key = key
        self.mode = mode
        self.calls = 0

    async def complete(self, prompt, system=None, max_tokens=2048,
                       temperature=0.7, json_mode=False):
        self.calls += 1
        if self.mode == "ok":
            return LLMResult(text="پاسخ خوب", provider="go", model="m",
                             latency_ms=10, usage=LLMUsage(5, 5))
        if self.mode == "empty":
            return LLMResult(text="", provider="go", model="m", latency_ms=10)
        if self.mode == "quota":
            return LLMResult(text="", provider="go", model="m",
                             error="HTTP 429: GoUsageLimitError: Weekly usage limit reached")
        if self.mode == "boom":
            return LLMResult(text="", provider="go", model="m", error="HTTP 500: oops")
        raise AssertionError(self.mode)

    async def stream(self, prompt, system=None, max_tokens=2048, temperature=0.7):
        r = await self.complete(prompt, system=system, max_tokens=max_tokens,
                                temperature=temperature)
        yield r


def make_pool(key_modes: dict[str, str]) -> tuple[GoPoolProvider, dict[str, FakeCaller]]:
    pool = GoPoolProvider(api_keys=list(key_modes), model="deepseek-v4-flash")
    callers: dict[str, FakeCaller] = {}

    def _mk(slot: KeySlot) -> FakeCaller:
        c = callers.get(slot.key)
        if c is None:
            c = FakeCaller(slot.key, key_modes[slot.key])
            callers[slot.key] = c
        return c

    pool._mk = _mk  # type: ignore[method-assign]
    return pool, callers


def test_pick_prefers_least_busy_and_healthy():
    pool, _ = make_pool({"k1": "ok", "k2": "ok"})
    s1, s2 = pool.slots
    s1.in_flight = 1
    assert pool._pick() is s2  # least busy
    s2.error_streak = 3  # but not tripped yet
    assert pool._pick() is s2  # error_streak only orders after in_flight
    s2.tripped_until = time.monotonic() + 100
    assert pool._pick() is s1  # tripped keys are excluded


def test_quota_key_fails_over_in_same_request_and_trips():
    pool, callers = make_pool({"k1": "quota", "k2": "ok"})

    async def run(n: int):
        return [await pool.complete(f"q{i}") for i in range(n)]

    res = asyncio.run(run(3))
    assert all(r.ok and r.text for r in res)           # every call succeeded
    assert all(r.provider == "go" for r in res)        # pool identity, not inner
    k1, k2 = pool.slots
    assert k1.tripped()                                 # quota → 5-min backoff
    assert callers["k2"].calls == 3                     # failover landed on k2
    assert callers["k1"].calls == 1                     # tripped after first 429


def test_empty_200_is_treated_as_failure_and_fails_over():
    pool, callers = make_pool({"k1": "empty", "k2": "ok"})

    async def run():
        return await pool.complete("q")

    res = asyncio.run(run())
    assert res.ok and "پاسخ" in res.text                # k2 answered
    assert pool.slots[0].tripped()                      # empty → per-key breaker


def test_all_keys_dead_pool_reports_error():
    pool, callers = make_pool({"k1": "quota", "k2": "quota"})

    async def run():
        return await pool.complete("q")

    res = asyncio.run(run())
    assert not res.ok and "429" in (res.error or "")
    assert all(s.tripped() for s in pool.slots)


def test_pool_tripped_only_when_every_slot_tripped():
    pool, _ = make_pool({"k1": "ok", "k2": "ok"})
    assert not pool.tripped()
    for s in pool.slots:
        s.tripped_until = time.monotonic() + 100
    assert pool.tripped()


def test_zen_free_429_sets_long_cooldown(monkeypatch):
    zf = ZenFreeProvider(api_key="fake")

    async def fake_complete(self, prompt, system=None, max_tokens=2048,
                            temperature=0.7, json_mode=False):
        return LLMResult(text="", provider="zen-free", model="m",
                         error="HTTP 429: FreeUsageLimitError: Rate limit exceeded")

    monkeypatch.setattr(llm.DeepSeekProvider, "complete", fake_complete)
    res = asyncio.run(zf.complete("q"))
    assert not res.ok
    assert zf.tripped()
    assert zf.health.tripped_until > time.monotonic() + 200  # ~300s cooldown


def test_slot_breaker_recovers_after_cooldown():
    pool, callers = make_pool({"k1": "ok", "k2": "ok"})
    k2 = pool.slots[1]
    k2.trip(0.05)  # short cooldown
    assert k2.tripped()
    time.sleep(0.08)
    assert not k2.tripped()
    assert not pool.tripped()
