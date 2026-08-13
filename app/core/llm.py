"""
LLM Provider layer — deterministic chart data NEVER goes through LLM.

Architecture (plan v3.1 section 6.1):
    LLMProvider (abstract: health/quota/latency/error_rate/cost)
      ├── GeminiProvider   (direct REST, AQ free-tier keys, rotation)  ✅ tested
      ├── DeepSeekProvider (OpenAI-compatible API)                     ⏳ needs key
      └── AvalAIProvider   (OpenAI-compatible Iranian gateway)          ⏳ needs key
    LLMRouter picks the best provider by health + quota + cost.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

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

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class ProviderHealth:
    provider: str
    healthy: bool = True
    last_error: str | None = None
    error_streak: int = 0
    last_latency_ms: int = 0
    cost_usd: float = 0.0


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

    def report_success(self, latency_ms: int, usage: LLMUsage) -> None:
        self.health.last_latency_ms = latency_ms
        self.health.error_streak = 0
        self.health.cost_usd += self.estimate_cost(usage)

    def report_error(self, err: str) -> None:
        self.health.error_streak += 1
        self.health.last_error = err
        self.health.healthy = self.health.error_streak < 5

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        """Override per provider pricing. DeepSeek official: in $0.14/1M (miss), out $0.28/1M."""
        return (usage.prompt_tokens * 0.14 + usage.completion_tokens * 0.28) / 1_000_000


# ─────────────────────────── Gemini (direct REST, free-tier AQ keys) ───────────────────────────

class GeminiProvider(LLMProvider):
    """Gemini 3.6 Flash via native generateContent?key= — PROVEN working from this server (2026-08-12)."""

    name = "gemini"
    MODEL = "gemini-3.6-flash"

    def __init__(self, keys: list[str], api_base: str = "https://generativelanguage.googleapis.com/v1beta") -> None:
        super().__init__()
        self.keys = keys
        self.api_base = api_base
        self._idx = 0
        self._exhausted: dict[str, float] = {}  # key -> cooldown-until (monotonic)
        self._daily_quota = 20  # free tier: 20 req/day/project/model
        self._daily: dict[str, int] = {}
        self._daily_reset = int(time.time()) // 86400

    def _next_key(self) -> str:
        """Round-robin over keys, skipping cooldown + daily-quota-exhausted keys."""
        today = int(time.time()) // 86400
        if today != self._daily_reset:
            self._daily.clear()
            self._daily_reset = today
        for _ in range(len(self.keys)):
            key = self.keys[self._idx % len(self.keys)]
            self._idx += 1
            if self._exhausted.get(key, 0) <= time.monotonic() and self._daily.get(key, 0) < self._daily_quota:
                self._daily[key] = self._daily.get(key, 0) + 1
                return key
        # everything cooling down / quota-exhausted — try the next key anyway (retry > nothing)
        key = self.keys[self._idx % len(self.keys)]
        self._idx += 1
        return key

    def _mark_exhausted(self, key: str, cooldown_s: float) -> None:
        self._exhausted[key] = time.monotonic() + cooldown_s
        logger.warning("Gemini key %s… cooldown %.0fs (remaining healthy keys: %d)",
                       key[-6:], cooldown_s, sum(1 for k in self.keys if self._exhausted.get(k, 0) <= time.monotonic()))

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        t0 = time.monotonic()
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        # try up to len(keys) times — skip exhausted keys automatically
        for attempt in range(max(len(self.keys), 1)):
            key = self._next_key()
            url = f"{self.api_base}/models/{self.MODEL}:generateContent?key={key}"
            try:
                async with httpx.AsyncClient(timeout=120) as cl:
                    r = await cl.post(url, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    text = "".join(p.get("text", "") for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []))
                    usage = data.get("usageMetadata", {})
                    u = LLMUsage(prompt_tokens=usage.get("promptTokenCount", 0),
                                 completion_tokens=usage.get("candidatesTokenCount", 0))
                    lat = int((time.monotonic() - t0) * 1000)
                    self.report_success(lat, u)
                    return LLMResult(text=text, provider=self.name, model=self.MODEL,
                                     latency_ms=lat, usage=u, cost=self.estimate_cost(u))
                err = r.text[:200]
                if r.status_code == 429:
                    if "quota" in r.text.lower() or "billing" in r.text.lower():
                        self._mark_exhausted(key, 3600)
                    else:
                        self._mark_exhausted(key, 30)
                elif r.status_code >= 500:
                    self._mark_exhausted(key, 30)
                if attempt == len(self.keys) - 1:
                    self.report_error(err)
                    return LLMResult(text="", provider=self.name, model=self.MODEL, error=f"HTTP {r.status_code}: {err}")
            except Exception as e:  # network etc.
                if attempt == len(self.keys) - 1:
                    self.report_error(str(e))
                    return LLMResult(text="", provider=self.name, model=self.MODEL, error=str(e))
        return LLMResult(text="", provider=self.name, model=self.MODEL, error="no keys available")

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        return 0.0  # free-tier keys


# ─────────────────────────── DeepSeek (OpenAI-compatible) ───────────────────────────

class DeepSeekProvider(LLMProvider):
    """DeepSeek V4 Flash via official OpenAI-compatible API. Needs DEEPSEEK_API_KEY env."""

    name = "deepseek"
    MODEL = "deepseek-v4-flash"

    def __init__(self, api_key: str | None = None, api_base: str = "https://api.deepseek.com") -> None:
        super().__init__()
        self.api_key = api_key or get_secret("deepseek_api_key", "DEEPSEEK_API_KEY", "")
        self.api_base = api_base
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
            async with httpx.AsyncClient(timeout=300) as cl:
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


# ─────────────────────────── AvalAI (Iranian gateway, OpenAI-compatible) ───────────────────────────

class AvalAIProvider(DeepSeekProvider):
    """AvalAI (avalai.ir) — OpenAI-compatible Iranian gateway with riyal billing.
    Set AVALAI_API_KEY. Optional paid fallback; interface identical to DeepSeek."""

    name = "avalai"
    MODEL = "deepseek-chat"  # their default DeepSeek model

    def __init__(self, api_key: str | None = None, api_base: str = "https://api.avalai.ir/v1") -> None:
        super().__init__(api_key=api_key or get_secret("avalai_api_key", "AVALAI_API_KEY", ""), api_base=api_base)


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
        return sorted((self.providers[n] for n in self.order if n in self.providers), key=key)

    async def complete(self, prompt: str, system: str | None = None,
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

    def health_report(self) -> list[dict]:
        return [
            {"provider": p.name, "healthy": p.health.healthy, "error_streak": p.health.error_streak,
             "last_latency_ms": p.health.last_latency_ms, "last_error": p.health.last_error,
             "cost_usd": round(p.health.cost_usd, 6)}
            for p in self.providers.values()
        ]


# ─────────────────────────── factory ───────────────────────────

def load_gemini_keys(path: str | None = None) -> list[str]:
    """Load Gemini keys: platform .env path → platform keys/ → hermes fallback."""
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates += [
        Path(get_secret("gemini_keys_path", "GEMINI_KEYS_PATH", "keys/gemini-keys.txt")),
        Path("/root/chart-platform/keys/gemini-keys.txt"),
        Path("/root/.hermes/keys/gemini-3.6-keys.txt"),
    ]
    for cand in candidates:
        if cand.exists():
            keys = [l.strip() for l in cand.read_text().splitlines()
                    if l.strip().startswith("AQ.")]
            if keys:
                return keys
    return []


def build_router() -> LLMRouter:
    providers: list[LLMProvider] = []
    go = GoProvider()
    if go.api_key:
        providers.append(go)
    gkeys = load_gemini_keys()
    if gkeys:
        providers.append(GeminiProvider(gkeys))
    providers.append(DeepSeekProvider())
    providers.append(AvalAIProvider())
    return LLMRouter(providers)


def build_chat_router() -> LLMRouter:
    """Chat/preview router — fast + quota-cheap: go-flash → gemini → avalai."""
    providers: list[LLMProvider] = []
    go = GoProvider(model="deepseek-v4-flash")
    if go.api_key:
        providers.append(go)
    gkeys = load_gemini_keys()
    if gkeys:
        providers.append(GeminiProvider(gkeys))
    providers.append(AvalAIProvider())
    return LLMRouter(providers)
