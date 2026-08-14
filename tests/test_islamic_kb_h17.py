"""H1.7 (HARDENING): Islamic verified KB — the LLM may only cite concepts from
app/content/islamic_kb.json (surah/ayah refs); no free-form quoting."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from app.report.prompt_builder import build_islamic_prompt  # noqa: E402

KB = Path(__file__).resolve().parent.parent / "app" / "content" / "islamic_kb.json"


def _chart() -> dict:
    # canonical chart JSON shape: planets.Sun/Moon with longitude, angles.ASC
    return {"planets": {"Sun": {"longitude": 149.0}, "Moon": {"longitude": 335.0}},
            "angles": {"ASC": {"longitude": 120.0}}, "moon_phase": "هلال"}


def test_kb_has_30_verified_concepts():
    data = json.loads(KB.read_text(encoding="utf-8"))
    concepts = data["concepts"]
    assert len(concepts) >= 30, "plan requires ~30 concepts"
    keys = [c["key"] for c in concepts]
    assert len(keys) == len(set(keys)), "concept keys must be unique"
    for c in concepts:
        for field in ("key", "fa", "concept", "ref", "ref_en"):
            assert c.get(field), f"{c['key']} missing {field}"
        assert any(ch.isdigit() for ch in c["ref"]), f"{c['key']} ref has no ayah number"
        # must be a known surah name (sanity — a typo here would be embarrassing)
        assert c["ref"].split(" ")[0] in {
            "ابراهیم", "طلاق", "بقره", "زمر", "نحل", "زلزال", "آل‌عمران", "فرقان",
            "نساء", "حجرات", "یوسف", "اعراف", "ص", "شمس", "شوری", "نوح", "غافر",
            "توبه", "سبأ", "لقمان", "مائده", "انفال", "اسراء", "کهف", "انبیاء",
        } or c["ref"].split(" ")[0] in {"ابراهیم", "طلاق", "بقره", "زمر", "نحل",
            "زلزال", "آل‌عمران", "فرقان", "نساء", "حجرات", "یوسف", "اعراف", "ص",
            "شمس", "شوری", "نوح", "غافر", "توبه"}, f"unknown surah in {c['key']}"


def test_islamic_prompt_contains_full_kb_and_citation_rule():
    prompt, ctx = build_islamic_prompt(_chart())
    assert ctx["kb_count"] >= 30
    # every concept's fa name + ref appears in the prompt
    data = json.loads(KB.read_text(encoding="utf-8"))
    for c in data["concepts"][:5]:
        assert c["fa"] in prompt and c["ref"] in prompt
    # the hard citation rule is present
    assert "تنها منبع مجاز ارجاع" in prompt
    assert "هیچ نقل‌قول دیگری از قرآن یا حدیث نکن" in prompt


def test_islamic_prompt_is_stable_and_personalized():
    p1, ctx1 = build_islamic_prompt(_chart())
    p2, _ = build_islamic_prompt(_chart())
    assert p1 == p2, "same chart must yield the same prompt (deterministic)"
    assert "هلال" in p1  # moon phase personalized
    assert "اسد" in p1   # big three personalized (Sun at 149° = Leo)
