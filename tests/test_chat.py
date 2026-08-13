"""Phase 5 tests — intent detection + retrieval + chat with FAKE router."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.astrology.engine import compute_from_fields
from app.chat.intents import detect_intent, route_question
from app.chat.retrieval import build_chat_prompt, retrieve_context
from app.chat.service import chat_answer

CHART = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


class FakeRouter:
    """Deterministic fake — never touches the network."""

    def __init__(self, text="پاسخ آزمایشی بر اساس چارت"):
        self.text = text
        self.calls = 0

    async def complete(self, prompt, max_tokens=2048, temperature=0.7, json_mode=False):
        self.calls += 1
        return SimpleResult(self.text)


class SimpleResult:
    def __init__(self, text):
        self.text = text
        self.provider = "fake"
        self.cost = 0.0
        self.ok = True
        self.error = None
        self.usage = SimpleUsage()


class SimpleUsage:
    prompt_tokens = 10
    completion_tokens = 20

    @property
    def total(self):
        return 30


# ─────────────────────────── intents ───────────────────────────

def test_detect_career():
    assert detect_intent("بهترین مسیر شغلی من چیست؟") == "career"


def test_detect_relationships():
    assert detect_intent("آیا ازدواج موفقی خواهم داشت؟") == "relationships"


def test_detect_emotions():
    assert detect_intent("چرا اینقدر حساس و احساساتی هستم؟") == "emotions"


def test_detect_fallback():
    assert detect_intent("سلام حالت چطوره") == "general"


def test_route_general_uses_focus_areas():
    r = route_question("یه سوال کلی دارم", ["money", "career"])
    assert r["intent"] == "general"
    assert "money" in r["domains"] and "career" in r["domains"]


# ─────────────────────────── retrieval ───────────────────────────

def test_retrieve_context_grounded():
    ctx = retrieve_context(CHART, None, ["career", "money"])
    assert ctx["chart_summary"]
    assert "career" in ctx["domains"] and "money" in ctx["domains"]
    # factors are grounded in the real chart (Mars in Cancer H11 for career)
    assert "سرطان" in ctx["domains"]["career"]["factors"] or "Mars" in ctx["domains"]["career"]["factors"]


def test_build_chat_prompt_includes_question():
    ctx = retrieve_context(CHART, None, ["identity"])
    p = build_chat_prompt("شخصیتم چطور است؟", ctx)
    assert "شخصیتم چطور است؟" in p
    assert "اسد" in p or "خورشید" in p


# ─────────────────────────── chat service ───────────────────────────

def test_chat_answer_with_fake_router():
    r = chat_answer("مسیر شغلی من چیست؟", CHART, router=FakeRouter("شغل شما تحت تأثیر خورشید در اسد است."))
    assert r["answer"] == "شغل شما تحت تأثیر خورشید در اسد است."
    assert r["intent"] == "career"
    assert r["ok"] is True
    assert r["cost_usd"] == 0.0
