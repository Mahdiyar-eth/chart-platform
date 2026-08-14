"""A6 (audit r4): bot-created charts carry capability tokens in share URLs so the
ownership-guarded web routes (/chart, /plans, /transit) work for bot users."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from app.bots.handler import chart_actions_keyboard


def test_keyboard_without_token_plain_urls(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://chart.example.com")
    kb = chart_actions_keyboard("abc-123")
    urls = [b["url"] for row in kb["inline_keyboard"] for b in row if "url" in b]
    assert "/chart/abc-123" in urls[0]
    assert "?t=" not in urls[0]


def test_keyboard_with_token_appends_capability(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://chart.example.com")
    kb = chart_actions_keyboard("abc-123", "tok_secret_9")
    urls = [b["url"] for row in kb["inline_keyboard"] for b in row if "url" in b]
    assert urls[0] == "https://chart.example.com/chart/abc-123?t=tok_secret_9"
    # plans keeps chart= and appends t= with & (well-formed query string)
    assert urls[1] == "https://chart.example.com/plans?chart=abc-123&t=tok_secret_9"
    assert urls[2] == "https://chart.example.com/transit/abc-123?t=tok_secret_9"
