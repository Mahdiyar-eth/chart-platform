"""V4 audit P1: content sweep guard — user-facing content must stay free of
predictive/fortune-telling language (self-knowledge framing only).

Hard-banned phrases (would imply fortune-telling):
  پیش‌بینی سالانه / پیش بینی سالانه / پیشگویی آینده / فال هفتگی / طالع امروز
Neutral mentions like «نه فال», «فال‌گویی نیست», «سرنوشتِ از پیش نوشته‌شده نیست»
are ALLOWED — they are the required negative framing.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root — host-portable (was hardcoded /root/chart-platform)

BANNED = ["پیش‌بینی سالانه", "پیش بینی سالانه", "پیشگویی آینده",
          "فال هفتگی", "طالع امروز", "پیش‌بینی هفتگی"]

FILES = [
    "app/content/articles.json",
    "app/content/pages.json",
    "app/templates/index.html",
    "app/templates/faq.html",
    "app/templates/sky.html",
    "app/templates/plans.html",
    "app/templates/synastry.html",
    "app/templates/seo_page.html",
    "app/report/prompt_builder.py",
    "scripts/gen_articles.py",
]


def test_no_predictive_language_in_user_facing_content():
    for rel in FILES:
        txt = (ROOT / rel).read_text(encoding="utf-8")
        for banned in BANNED:
            assert banned not in txt, f"{rel} contains banned predictive phrase: {banned!r}"


def test_negative_framing_is_present_and_allowed():
    """The brand voice must actively say 'not fortune-telling' (allowed framing)."""
    idx = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    assert "نه فال" in idx
    # and the verified KB keeps its reflection-focused tone
    kb = json.loads((ROOT / "app/content/islamic_kb.json").read_text(encoding="utf-8"))
    assert len(kb["concepts"]) >= 25
