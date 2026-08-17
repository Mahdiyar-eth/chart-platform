"""
LLM Provider layer — deterministic chart data NEVER goes through LLM.

Architecture (plan v3.1 section 6.1):
    LLMProvider (abstract: health/quota/latency/error_rate/cost)
      ├── GoProvider       (OpenCode Go subscription — DeepSeek V4 Flash/Pro)
      └── DeepSeekProvider (official DeepSeek API — optional direct fallback)
    LLMRouter picks the best provider by health + quota + cost.

Owner decision (2026-08-13): Gemini + AvalAI removed. Production runs on
OpenCode Go (DeepSeek V4) only, with per-part model selection
(report=pro, chat/preview=flash) overridable from the admin panel.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

import app.config  # noqa: F401 — load .env FIRST
from app.secret_store import get_secret

logger = logging.getLogger("chart.llm")


# ─────────────────────────── dataclasses ───────────────────────────

@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    usage: LLMUsage = field(default_factory=LLMUsage)
    cost: float = 0.0
    error: str | None = None
    key_slot: str | None = None  # M5: which pool key served (go-1/go-2/zen-free)

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def error_code(self) -> str | None:
        """M5: coarse classification for telemetry — 429 / empty / timeout / 5xx / other."""
        if self.ok and self.text.strip():
            return None
        if self.ok:
            return "empty"
        e = self.error or ""
        if "429" in e or "UsageLimit" in e or "Rate limit" in e:
            return "429"
        if "timeout" in e.lower() or "deadline" in e.lower():
            return "timeout"
        if "5" in e[:8] and e.startswith("HTTP 5"):
            return "5xx"
        return "other"


@dataclass
class ProviderHealth:
    provider: str
    healthy: bool = True
    last_error: str | None = None
    error_streak: int = 0
    last_latency_ms: int = 0
    cost_usd: float = 0.0
    tripped_until: float = 0.0  # audit r4 B9 — circuit breaker (monotonic)


# audit r4 B9: circuit breaker + deadlines
_CIRCUIT_THRESHOLD = int(os.getenv("LLM_CIRCUIT_THRESHOLD", "3"))
_CIRCUIT_COOLDOWN = float(os.getenv("LLM_CIRCUIT_COOLDOWN", "60"))
_PER_CALL_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))   # httpx per-request
_DEADLINE = float(os.getenv("LLM_DEADLINE", "150"))          # whole-call backstop

# M1 (multi-provider plan): per-key health inside the GO pool.
_GO_SLOT_COOLDOWN = float(os.getenv("GO_SLOT_COOLDOWN", "60"))      # per-key breaker
_GO_QUOTA_COOLDOWN = float(os.getenv("GO_QUOTA_COOLDOWN", "300"))   # GoUsageLimitError → back off 5 min
_GO_MAX_IN_FLIGHT = int(os.getenv("GO_MAX_IN_FLIGHT_PER_KEY", "2"))  # A4: cap concurrent calls per key
_GO_EMPTY_COOLDOWN = float(os.getenv("GO_EMPTY_COOLDOWN", "300"))   # M4: empty-200 == quota too — 5 min per key
_ZEN_FREE_COOLDOWN = float(os.getenv("ZEN_FREE_COOLDOWN", "300"))   # free-tier rate limit
# M9 (multi-provider plan): hard daily cost ceiling — if the LLM spend for
# today already exceeds this, reports degrade with an honest message instead
# of silently spending more (MaHDi: cost-conscious; no surprise bills).
LLM_DAILY_BUDGET_USD = float(os.getenv("LLM_DAILY_BUDGET_USD", "3.0"))
LLM_MONTHLY_BUDGET_USD = float(os.getenv("LLM_MONTHLY_BUDGET_USD", "30.0"))
LLM_USER_DAILY_MAX_USD = float(os.getenv("LLM_USER_DAILY_MAX_USD", "1.0"))
LLM_REPORT_MAX_USD = float(os.getenv("LLM_REPORT_MAX_USD", "0.5"))


@dataclass
class KeySlot:
    """One API key inside a provider pool — independent circuit breaker.

    M0 (2026-08-16, real API): keys from two separate accounts have
    INDEPENDENT quotas — key A answered while key B was 429 (weekly limit).
    So a per-key breaker is correct: one exhausted key must not stall the pool.
    """
    key: str
    name: str
    model: str | None = None   # R.3: per-slot model override ("key@model" in the pool CSV)
    error_streak: int = 0
    tripped_until: float = 0.0
    in_flight: int = 0
    last_latency_ms: int = 0
    last_error: str | None = None

    def tripped(self) -> bool:
        return self.tripped_until > time.monotonic()

    def trip(self, seconds: float) -> None:
        self.tripped_until = time.monotonic() + seconds
        self.error_streak = 0


# ─────────────────────────── abstract provider ───────────────────────────

class LLMProvider(ABC):
    """All providers expose the same interface so nothing is locked to one vendor."""

    name: str = "base"

    def __init__(self) -> None:
        self.health = ProviderHealth(provider=self.name)

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7) -> LLMResult:
        """Single completion. Returns structured result — never raises for API errors."""

    async def stream(self, prompt: str, system: str | None = None,
                     max_tokens: int = 2048,
                     temperature: float = 0.7) -> AsyncIterator[LLMResult]:
        """D4: streaming completion. Default = fall back to complete() in one
        shot so every provider (even non-streaming) supports the interface."""
        res = await self.complete(prompt, system=system, max_tokens=max_tokens,
                                  temperature=temperature)
        if res.error:
            yield res
        else:
            yield res  # single-shot is a valid "stream" of one chunk
            yield LLMResult(text=res.text, provider=self.name, model=self.MODEL,
                            latency_ms=res.latency_ms, usage=res.usage,
                            cost=res.cost)

    def report_success(self, latency_ms: int, usage: LLMUsage) -> None:
        self.health.last_latency_ms = latency_ms
        self.health.error_streak = 0
        self.health.tripped_until = 0.0  # audit r4 B9 — success resets the breaker
        self.health.last_error = None
        self.health.cost_usd += self.estimate_cost(usage)

    def report_error(self, err: str) -> None:
        self.health.error_streak += 1
        self.health.last_error = err
        self.health.healthy = self.health.error_streak < 5
        # audit r4 B9 — circuit breaker: N consecutive failures open the circuit
        if self.health.error_streak >= _CIRCUIT_THRESHOLD:
            self.health.tripped_until = time.monotonic() + _CIRCUIT_COOLDOWN

    def tripped(self) -> bool:
        """True while the circuit is OPEN (cooldown not elapsed)."""
        return self.health.tripped_until > time.monotonic()

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        """Override per provider pricing. DeepSeek official: in $0.14/1M (miss), out $0.28/1M."""
        return (usage.prompt_tokens * 0.14 + usage.completion_tokens * 0.28) / 1_000_000


# ─────────────────────────── DeepSeek (OpenAI-compatible) ───────────────────────────

class DeepSeekProvider(LLMProvider):
    """DeepSeek V4 Flash via official OpenAI-compatible API. Needs DEEPSEEK_API_KEY env."""

    name = "deepseek"
    MODEL = "deepseek-v4-flash"

    def __init__(self, api_key: str | None = None, api_base: str = "https://api.deepseek.com",
                 model: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key or get_secret("deepseek_api_key", "DEEPSEEK_API_KEY", "")
        self.api_base = api_base
        if model:
            self.MODEL = model
        self.user_agent = "chart-platform/1.0"
        self.extra_payload: dict | None = None

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        if not self.api_key:
            return LLMResult(text="", provider=self.name, model=self.MODEL, error="DEEPSEEK_API_KEY not set")
        t0 = time.monotonic()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict = {"model": self.MODEL, "messages": messages,
                         "max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "User-Agent": self.user_agent}
        if self.extra_payload:
            payload.update(self.extra_payload)
        try:
            async with httpx.AsyncClient(timeout=_PER_CALL_TIMEOUT) as cl:
                r = await cl.post(f"{self.api_base}/chat/completions",
                                  headers=headers,
                                  json=payload)
            if r.status_code != 200:
                err = r.text[:200]
                self.report_error(err)
                return LLMResult(text="", provider=self.name, model=self.MODEL, error=f"HTTP {r.status_code}: {err}")
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            u = LLMUsage(prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                         completion_tokens=data.get("usage", {}).get("completion_tokens", 0))
            lat = int((time.monotonic() - t0) * 1000)
            self.report_success(lat, u)
            return LLMResult(text=text, provider=self.name, model=self.MODEL,
                             latency_ms=lat, usage=u, cost=self.estimate_cost(u))
        except Exception as e:
            self.report_error(str(e))
            return LLMResult(text="", provider=self.name, model=self.MODEL, error=str(e))

    async def stream(self, prompt: str, system: str | None = None,
                     max_tokens: int = 2048, temperature: float = 0.7) -> AsyncIterator[LLMResult]:
        """SSE streaming completion — yields partial results with .text being
        the ACCUMULATED text so far; final yield carries usage + provider.
        D4: real token streaming over the OpenAI-compatible /chat/completions
        stream. Never raises: errors are yielded as LLMResult(error=...)."""
        if not self.api_key:
            yield LLMResult(text="", provider=self.name, model=self.MODEL,
                            error="DEEPSEEK_API_KEY not set")
            return
        t0 = time.monotonic()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict = {"model": self.MODEL, "messages": messages,
                         "max_tokens": max_tokens, "temperature": temperature,
                         "stream": True}
        if self.extra_payload:
            payload.update(self.extra_payload)
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "User-Agent": self.user_agent}
        acc = ""
        try:
            async with httpx.AsyncClient(timeout=_PER_CALL_TIMEOUT) as cl:
                async with cl.stream("POST", f"{self.api_base}/chat/completions",
                                     headers=headers, json=payload) as r:
                    if r.status_code != 200:
                        err = (await r.aread())[:200].decode(errors="replace")
                        self.report_error(err)
                        yield LLMResult(text="", provider=self.name, model=self.MODEL,
                                        error=f"HTTP {r.status_code}: {err}")
                        return
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        delta = obj["choices"][0].get("delta", {})
                        piece = delta.get("content") or ""
                        if piece:
                            acc += piece
                            yield LLMResult(text=acc, provider=self.name, model=self.MODEL)
            u = LLMUsage(prompt_tokens=0, completion_tokens=len(acc))
            lat = int((time.monotonic() - t0) * 1000)
            self.report_success(lat, u)
            yield LLMResult(text=acc, provider=self.name, model=self.MODEL,
                            latency_ms=lat, usage=u, cost=self.estimate_cost(u))
        except Exception as e:  # noqa: BLE001
            self.report_error(str(e))
            yield LLMResult(text=acc, provider=self.name, model=self.MODEL, error=str(e))


# ─────────────────────────── Go (opencode.ai subscription, OpenAI-compatible) ───────────────────────────

class GoProvider(DeepSeekProvider):
    """OpenCode Go subscription (opencode.ai/zen/go/v1) — DeepSeek V4 via OpenAI-compatible API.
    Flat $10/mo with per-model request quotas — cost per call recorded as 0 (billed via subscription).
    KEY: reasoning models burn max_tokens on thinking → MUST send thinking: disabled (verified 2026-08-12).
    NOTE: gateway sits behind Cloudflare — sends browser UA to avoid 403 (error code 1010)."""

    name = "go"
    MODEL = get_secret("go_model", "GO_MODEL", "deepseek-v4-pro")

    def __init__(self, api_key: str | None = None, api_base: str | None = None,
                 model: str | None = None) -> None:
        super().__init__(api_key=api_key or get_secret("go_api_key", "GO_API_KEY", ""),
                         api_base=api_base or get_secret("go_api_base", "GO_API_BASE", "https://opencode.ai/zen/go/v1"))
        if model:
            self.MODEL = model
        self.extra_payload = {"thinking": {"type": "disabled"}}
        self.user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "Chrome/126.0 Safari/537.36")

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        return 0.0  # flat subscription — not per-token


# ─────────────────────────── Go KeyPool (M1 — multi-account) ───────────────────────────

class GoPoolProvider(LLMProvider):
    """OpenCode Go subscription pool — N API keys from N separate accounts.

    M0 evidence (2026-08-16): quotas are PER-ACCOUNT and independent, so N keys
    give N independent rolling quotas. The pool picks the healthiest least-busy
    key per call; a key that 429s / returns an EMPTY 200 is cooled down on its
    own (per-key circuit) while the other keys keep serving. One bad key can
    never stall the pool.
    """

    name = "go"

    def __init__(self, api_keys: list[str], api_base: str | None = None,
                 model: str | None = None) -> None:
        super().__init__()
        self.api_base = api_base or get_secret("go_api_base", "GO_API_BASE",
                                               "https://opencode.ai/zen/go/v1")
        self.MODEL = model or get_secret("go_model", "GO_MODEL", "deepseek-v4-pro")
        # Per-slot model override: an entry may be "key@model" (R.3 paid-key
        # fix 2026-08-17) — paid GO keys run the reasoning variant of
        # deepseek-v4-flash which burns max_tokens on thinking and returns
        # EMPTY content; deepseek-v4-pro (with thinking:disabled below) always
        # returns content. So a paid key is pinned to pro while free keys keep
        # the part's default (flash) — verified with real API calls.
        self.slots = []
        for i, k in enumerate(api_keys):
            raw = k.strip()
            key_part, _, model_part = raw.partition("@")
            slot_model = model_part.strip() if model_part else None
            self.slots.append(KeySlot(key=key_part, name=f"go-{i + 1}", model=slot_model))
        self.user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "Chrome/126.0 Safari/537.36")
        self.extra_payload = {"thinking": {"type": "disabled"}}

    def _mk(self, slot: KeySlot) -> DeepSeekProvider:
        """Build the actual caller for one key (overridable in tests)."""
        p = DeepSeekProvider(api_key=slot.key, api_base=self.api_base,
                             model=slot.model or self.MODEL)
        p.user_agent = self.user_agent
        p.extra_payload = self.extra_payload
        return p

    def _pick(self) -> KeySlot:
        healthy = [s for s in self.slots if not s.tripped()] or self.slots
        return min(healthy, key=lambda s: (s.in_flight, s.error_streak, s.last_latency_ms))

    def tripped(self) -> bool:
        """The pool is only DOWN when EVERY key is tripped (stale breaker safe)."""
        return bool(self.slots) and all(s.tripped() for s in self.slots)

    def _track(self, slot: KeySlot, res: LLMResult) -> None:
        if res.ok and res.text.strip():
            slot.error_streak = 0
            slot.last_latency_ms = res.latency_ms
            slot.last_error = None
            self.report_success(res.latency_ms, res.usage)
            return
        err = res.error or "empty response (GO quota/rate)"
        slot.error_streak += 1
        slot.last_error = err
        if res.ok and not res.text.strip():
            # empty HTTP 200 — GO returning blank while rate-limited: back off
            slot.trip(_GO_EMPTY_COOLDOWN)
            self.report_error(err)
            return
        if "GoUsageLimitError" in err or "429" in err:
            slot.trip(_GO_QUOTA_COOLDOWN)  # quota hit — don't hammer for 5 min
        elif slot.error_streak >= _CIRCUIT_THRESHOLD:
            slot.trip(_GO_SLOT_COOLDOWN)
        self.report_error(err)

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        if not self.slots:
            return LLMResult(text="", provider=self.name, model=self.MODEL,
                             error="GO_API_KEYS not set")
        # in-pool failover: try the healthiest key; on failure (quota/empty/5xx)
        # move to the next healthy key for THIS request — one bad key must not
        # cost the user a degraded report.
        tried: list[KeySlot] = []
        last: LLMResult | None = None
        while len(tried) < len(self.slots):
            candidates = [s for s in self.slots if s not in tried and not s.tripped()] or \
                         [s for s in self.slots if s not in tried]
            if not candidates:
                break
            # A4 (amendments): per-key in-flight cap — GO rate-limits bursts of
            # concurrent calls, so spread load and never hammer a single key.
            low = [s for s in self.slots if s not in tried and not s.tripped()
               and s.in_flight < _GO_MAX_IN_FLIGHT]
            candidates = low or candidates
            slot = min(candidates, key=lambda s: (s.in_flight, s.error_streak, s.last_latency_ms))
            tried.append(slot)
            slot.in_flight += 1
            try:
                res = await self._mk(slot).complete(prompt, system=system,
                                                    max_tokens=max_tokens,
                                                    temperature=temperature,
                                                    json_mode=json_mode)
            finally:
                slot.in_flight -= 1
            self._track(slot, res)
            last = res
            if res.ok and res.text.strip():
                res.provider = self.name   # M1: pool identity, not inner caller
                res.model = self.MODEL
                res.key_slot = slot.name   # M5: telemetry — which key served
                return res
        assert last is not None
        last.provider = self.name
        last.model = self.MODEL
        last.key_slot = ",".join(s.name for s in tried)  # M4: honest telemetry on failure
        return last

    async def stream(self, prompt: str, system: str | None = None,
                     max_tokens: int = 2048,
                     temperature: float = 0.7) -> AsyncIterator[LLMResult]:
        if not self.slots:
            yield LLMResult(text="", provider=self.name, model=self.MODEL,
                            error="GO_API_KEYS not set")
            return
        slot = self._pick()
        slot.in_flight += 1
        last: LLMResult | None = None
        try:
            async for chunk in self._mk(slot).stream(prompt, system=system,
                                                     max_tokens=max_tokens,
                                                     temperature=temperature):
                last = chunk
                yield chunk
        finally:
            slot.in_flight -= 1
        if last is not None:
            self._track(slot, last)


# ─────────────────────────── Zen free-tier (M1 — last-resort fallback) ───────────────────────────

class ZenFreeProvider(DeepSeekProvider):
    """OpenCode Zen FREE model (e.g. deepseek-v4-flash-free) — zero cost,
    zero reliability (M0: 429 FreeUsageLimitError most of the time).

    Positioned as the LAST fallback layer: try-once per request, and on ANY
    free-tier rate limit back off the whole slot for ZEN_FREE_COOLDOWN so we
    never hammer a free quota in a loop. When it works it costs nothing.
    """

    name = "zen-free"
    MODEL = "deepseek-v4-flash-free"

    def __init__(self, api_key: str | None = None,
                 api_base: str = "https://opencode.ai/zen/v1") -> None:
        super().__init__(api_key=api_key, api_base=api_base, model=self.MODEL)
        self.user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "Chrome/126.0 Safari/537.36")

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        return 0.0  # free tier

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        res = await super().complete(prompt, system=system, max_tokens=max_tokens,
                                     temperature=temperature, json_mode=json_mode)
        if res.error and ("FreeUsageLimitError" in res.error or "429" in res.error):
            self.health.tripped_until = time.monotonic() + _ZEN_FREE_COOLDOWN
            self.health.error_streak = 0  # free quota — not a persistent fault
        return res


# ─────────────────────────── OmniRoute provider (Phase 3, 2026-08-17) ─────
OMNI_BASE = get_secret("omni_base", "OMNI_BASE", "http://127.0.0.1:20128/v1")
OMNI_KEY = get_secret("omni_api_key", "OMNI_API_KEY", "")
# verified per-model pricing ($/1M tokens, in/out) — phase-1 research 2026-08-17
_OMNI_PRICES = {
    "antigravity/gemini-3.6-flash-high": (1.50, 7.50),
    "antigravity/gemini-3.6-flash-medium": (1.50, 7.50),
    "antigravity/gemini-3.6-flash-low": (1.50, 7.50),
    "antigravity/gemini-3.1-pro-low": (2.00, 12.00),
    "antigravity/claude-sonnet-4-6": (3.00, 15.00),
    "antigravity/claude-opus-4-6-thinking": (5.00, 25.00),
    "opencode-go/deepseek-v4-pro": (0.435, 0.87),
    "opencode-go/deepseek-v4-flash": (0.14, 0.28),
}
_OMNI_PRICE_DEFAULT = (1.50, 7.50)


class OmniProvider(LLMProvider):
    """OpenAI-compatible provider for the local OmniRoute gateway (Antigravity
    / GO / Zen models). Used when a section model is named with a gateway
    prefix (antigravity/..., opencode-go/..., agy/...). Phase 3 speed test."""

    name = "omni"

    def __init__(self, model: str, api_base: str | None = None,
                 api_key: str | None = None) -> None:
        super().__init__()
        self.api_base = api_base or OMNI_BASE
        self.api_key = api_key or OMNI_KEY
        self.MODEL = model

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        res = await super().complete(prompt, system=system, max_tokens=max_tokens,
                                     temperature=temperature)
        if not self.api_key:
            return LLMResult(text="", provider="omni", model=self.MODEL,
                             error="OMNI_API_KEY not set")
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        payload: dict = {"model": self.MODEL, "messages": messages,
                         "max_tokens": max_tokens, "temperature": temperature,
                         "stream": False}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                r = await client.post(f"{self.api_base}/chat/completions",
                                      json=payload,
                                      headers={"Authorization": f"Bearer {self.api_key}"})
        except Exception as exc:  # noqa: BLE001
            return LLMResult(text="", provider="omni", model=self.MODEL,
                             error=f"omni transport error: {exc}")
        dt = int((time.monotonic() - t0) * 1000)
        if r.status_code != 200:
            # some gateways reject response_format — retry once without it
            if json_mode and r.status_code == 400:
                payload.pop("response_format", None)
                try:
                    async with httpx.AsyncClient(timeout=180) as client:
                        r = await client.post(f"{self.api_base}/chat/completions",
                                              json=payload,
                                              headers={"Authorization": f"Bearer {self.api_key}"})
                except Exception as exc:  # noqa: BLE001
                    return LLMResult(text="", provider="omni", model=self.MODEL,
                                     error=f"omni transport error: {exc}")
                dt = int((time.monotonic() - t0) * 1000)
            if r.status_code != 200:
                return LLMResult(text="", provider="omni", model=self.MODEL,
                                 error=f"omni {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
            msg = data["choices"][0]["message"]
            usage = data.get("usage") or {}
            return LLMResult(text=msg.get("content") or "",
                             provider="omni", model=self.MODEL, latency_ms=dt,
                             usage=LLMUsage(prompt_tokens=usage.get("prompt_tokens", 0),
                                            completion_tokens=usage.get("completion_tokens", 0)),
                             cost=((usage.get("prompt_tokens", 0) * _OMNI_PRICES.get(self.MODEL, _OMNI_PRICE_DEFAULT)[0]
                                    + usage.get("completion_tokens", 0) * _OMNI_PRICES.get(self.MODEL, _OMNI_PRICE_DEFAULT)[1]) / 1e6))
        except Exception as exc:  # noqa: BLE001
            return LLMResult(text="", provider="omni", model=self.MODEL,
                             error=f"omni parse error: {exc}")


# ─────────────────────────── Router ───────────────────────────

class LLMRouter:
    """Picks the best provider: healthy + cheapest + lowest error streak.
    Priority order can be overridden via LLM_ORDER env (comma-separated provider names)."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        self.providers = {p.name: p for p in providers}
        env_order = get_secret("llm_order", "LLM_ORDER", "")
        self.order = [n.strip() for n in env_order.split(",") if n.strip()] or list(self.providers)

    def _rank(self) -> list[LLMProvider]:
        def key(p: LLMProvider) -> tuple:
            return (not p.health.healthy, p.health.error_streak, p.health.cost_usd)
        ranked = sorted((self.providers[n] for n in self.order if n in self.providers), key=key)
        # audit r4 B9: skip OPEN circuits; if that empties the pool, fall back
        # to everything (a stale breaker must not deadlock the request)
        candidates = [p for p in ranked if not p.tripped()]
        return candidates or ranked

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        # audit r4 B9: whole-call deadline — a stuck provider chain must fail
        # fast, not hold a worker slot for minutes
        try:
            return await asyncio.wait_for(
                self._complete(prompt, system=system, max_tokens=max_tokens,
                               temperature=temperature, json_mode=json_mode),
                timeout=_DEADLINE)
        except asyncio.TimeoutError:
            logger.warning("LLM call hit the %ss deadline", _DEADLINE)
            return LLMResult(text="", provider="none", model="",
                             error=f"deadline exceeded ({_DEADLINE}s)")

    async def _complete(self, prompt: str, system: str | None = None,
                        max_tokens: int = 2048, temperature: float = 0.7,
                        json_mode: bool = False) -> LLMResult:
        last: LLMResult | None = None
        for p in self._rank():
            last = await p.complete(prompt, system=system, max_tokens=max_tokens,
                                    temperature=temperature, json_mode=json_mode)
            if last.ok:
                return last
            logger.warning("LLM provider %s failed: %s — trying next", p.name, last.error)
        return last or LLMResult(text="", provider="none", model="", error="all providers failed")

    async def stream_complete(self, prompt: str, system: str | None = None,
                              max_tokens: int = 2048,
                              temperature: float = 0.7) -> AsyncIterator[LLMResult]:
        """D4: streaming completion with the same fallback chain as complete().
        Yields accumulated text chunks; the LAST yield carries usage/provider
        (or .error when every provider failed)."""
        last: LLMResult | None = None
        for p in self._rank():
            try:
                emitted = False
                async for chunk in p.stream(prompt, system=system,
                                            max_tokens=max_tokens,
                                            temperature=temperature):
                    emitted = True
                    last = chunk
                    if chunk.error:
                        logger.warning("LLM provider %s stream error: %s — trying next",
                                       p.name, chunk.error)
                        break
                    yield chunk
                if emitted and last and not last.error:
                    return
            except Exception as e:  # noqa: BLE001 — a broken provider must not kill the stream
                logger.warning("LLM provider %s stream raised: %s — trying next", p.name, e)
                last = LLMResult(text="", provider=p.name, model="", error=str(e))
        yield last or LLMResult(text="", provider="none", model="", error="all providers failed")

    def health_report(self) -> list[dict]:
        return [
            {"provider": p.name, "healthy": p.health.healthy, "error_streak": p.health.error_streak,
             "last_latency_ms": p.health.last_latency_ms, "last_error": p.health.last_error,
             "cost_usd": round(p.health.cost_usd, 6)}
            for p in self.providers.values()
        ]


# ─────────────────────────── factory ───────────────────────────

# Per-part default model — overridable from the admin panel (secret store).
_PART_DEFAULT_MODEL = {
    "report": "deepseek-v4-pro",     # full report generation (worker; report sections use SECTION_MODEL_DEFAULT)
    "chat": "antigravity/gemini-3.6-flash-high",   # AI chat (phase-1 test winner: 4s, 10/10 grounded)
    "preview": "antigravity/gemini-3.6-flash-high",  # free 3-5 insights enrichment
}


def _llm_cost_window(db_engine, hours: int | None = None, user_id: str | None = None) -> float:
    """Sum of LLMRun.cost_usd in a window. hours=None → current UTC month."""
    from datetime import datetime, timedelta, timezone

    from sqlmodel import Session, func, select

    from app.models import LLMRun
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if hours is None:
        start = start.replace(day=1)  # month boundary
    else:
        start = start - timedelta(hours=hours) if hours > 24 else start
    try:
        with Session(db_engine) as s:
            q = select(func.coalesce(func.sum(LLMRun.cost_usd), 0.0)).where(LLMRun.created_at >= start)
            if user_id:
                q = q.where(LLMRun.user_id == user_id)
            return float(s.exec(q).one() or 0.0)
    except Exception:
        return 0.0


def today_llm_cost(db_engine) -> float:
    """M9: sum of today's LLM spend from llm_runs (UTC day boundary)."""
    return _llm_cost_window(db_engine, hours=24)


def month_llm_cost(db_engine) -> float:
    """P0-2: current UTC month spend."""
    return _llm_cost_window(db_engine)


def user_today_llm_cost(db_engine, user_id: str | None) -> float:
    """P0-2: current user's spend in the last 24h."""
    if not user_id:
        return 0.0
    return _llm_cost_window(db_engine, hours=24, user_id=user_id)


def report_llm_cost(db_engine, report_id: str) -> float:
    """P0-2: spend so far for a single report."""
    from sqlmodel import Session, func, select

    from app.models import LLMRun
    try:
        with Session(db_engine) as s:
            return float(s.exec(select(func.coalesce(func.sum(LLMRun.cost_usd), 0.0))
                                  .where(LLMRun.report_id == report_id)).one() or 0.0)
    except Exception:
        return 0.0


def build_router(part: str = "report") -> LLMRouter:
    """Build the router for a specific part.

    M1 chain (2026-08-16): GO KeyPool (N account keys, per-key breaker)
    → optional Zen free-tier model (zero cost, last resort)
    → optional direct DeepSeek API key (paid fallback).
    Model + provider per part are overridable via secrets `{part}_llm_model`
    and `{part}_llm_provider` (go / zen-free / deepseek / auto) from the admin panel.
    """
    default_model = _PART_DEFAULT_MODEL.get(part, "deepseek-v4-pro")
    model = get_secret(f"{part}_llm_model", f"{part.upper()}_LLM_MODEL", default_model)
    provider_pref = get_secret(f"{part}_llm_provider", f"{part.upper()}_LLM_PROVIDER", "auto").strip().lower()
    providers: list[LLMProvider] = []
    if model.startswith(("antigravity/", "opencode-go/", "opencode-zen/", "agy/")):
        # Phase 3/4 (2026-08-17): gateway-routed model (OmniRoute) with GO + Zen fallback.
        providers.append(OmniProvider(model=model))
        pool = build_go_pool(model="deepseek-v4-pro")
        if pool is not None:
            providers.append(pool)
        zen = ZenFreeProvider(api_key=get_secret("go_api_key_2", "GO_API_KEY_2", "")
                              or get_secret("go_api_key", "GO_API_KEY", ""))
        if zen.api_key:
            providers.append(zen)
        return LLMRouter(providers)
    if provider_pref in ("", "auto", "go"):
        pool = build_go_pool(model=model)
        if pool is not None:
            providers.append(pool)
    if provider_pref in ("", "auto", "zen-free"):
        zen = ZenFreeProvider(api_key=get_secret("go_api_key_2", "GO_API_KEY_2", "")
                              or get_secret("go_api_key", "GO_API_KEY", ""))
        if zen.api_key:
            providers.append(zen)
    if provider_pref in ("", "auto", "deepseek"):
        ds = DeepSeekProvider(model=model)
        if ds.api_key:
            providers.append(ds)
    return LLMRouter(providers)


def build_go_pool(model: str | None = None, api_keys: str | None = None) -> GoPoolProvider | None:
    """GO KeyPool from GO_API_KEYS (comma-separated) with GO_API_KEY fallback.

    api_keys: optional explicit CSV override (benchmark BENCH_GO_KEYS hook).
    """
    keys_csv = api_keys if api_keys is not None else get_secret("go_api_keys", "GO_API_KEYS", "")
    if not keys_csv:
        keys_csv = get_secret("go_api_key", "GO_API_KEY", "")
    keys = [k.strip() for k in keys_csv.split(",") if k.strip()]
    if not keys:
        return None
    return GoPoolProvider(api_keys=keys, model=model)


# ─────────────── M2: per-section model routing (multi-provider plan) ────────
# Quality-critical sections default to the pro model; lighter sections default
# to flash. Every section can be overridden via SECTION_MODEL_<DOMAIN> (env or
# admin panel secret) — the A/B benchmark (M2/M4) feeds the final mapping.
_SECTION_DEFAULT_MODEL: dict[str, str] = {
    "wellbeing": "deepseek-v4-flash",   # energy: shorter, lighter analysis
}
_SECTION_PRO_MODEL = "deepseek-v4-pro"


def section_model(domain: str) -> str:
    default = _SECTION_DEFAULT_MODEL.get(domain, get_secret("section_model_default", "SECTION_MODEL_DEFAULT", ""))
    if not default:
        default = _SECTION_PRO_MODEL
    return get_secret(f"section_model_{domain}",
                      f"SECTION_MODEL_{domain.upper()}", default)


@lru_cache(maxsize=None)
def build_section_router(domain: str, model: str) -> LLMRouter:
    """Cached per-section router: GO KeyPool (section model) + Zen free last resort.
    The cache key includes the model so an admin override rebuilds the pool.
    Phase 3 (2026-08-17): gateway-prefixed models (antigravity/..., opencode-go/...,
    agy/...) route through the local OmniRoute gateway instead of GO direct."""
    providers: list[LLMProvider] = []
    if model.startswith(("antigravity/", "opencode-go/", "opencode-zen/", "agy/")):
        providers.append(OmniProvider(model=model))
        # Phase 3: gateway model first, then GO pro as automatic fallback
        pool = build_go_pool(model="deepseek-v4-pro")
        if pool is not None:
            providers.append(pool)
    else:
        pool = build_go_pool(model=model)
        if pool is not None:
            providers.append(pool)
    zen = ZenFreeProvider(api_key=get_secret("go_api_key_2", "GO_API_KEY_2", "")
                          or get_secret("go_api_key", "GO_API_KEY", ""))
    if zen.api_key:
        providers.append(zen)
    return LLMRouter(providers)


def build_chat_router() -> LLMRouter:
    """Backward-compatible alias — chat uses the flash model by default."""
    return build_router("chat")
