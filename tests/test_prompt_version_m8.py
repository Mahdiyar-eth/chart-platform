"""M8 — prompt versioning + grounding contract sanity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.prompt_builder import (
    PROMPT_VERSION,
    build_all_prompts,
    build_islamic_prompt,
    build_personal_question_prompt,
)


def _chart():
    return {
        "planets": {"Sun": {"longitude": 135.0, "sign_fa": "اسد", "house": 1},
                    "Moon": {"longitude": 300.0, "sign_fa": "جدی", "house": 5}},
        "angles": {"ASC": {"longitude": 135.0, "sign_fa": "اسد"}},
        "houses": {},
        "birth": {"city_fa": "تهران", "time_known": True},
        "moon_phase": "نیم‌ماه",
    }


def test_all_prompts_carry_version_header():
    prompts = build_all_prompts(_chart())
    assert len(prompts) >= 13
    for domain, (text, ctx) in prompts.items():
        assert f"نسخه {PROMPT_VERSION}" in text, domain       # version header in prompt
        assert ctx["prompt_version"] == PROMPT_VERSION, domain  # version in context/telemetry


def test_islamic_and_personal_question_versioned():
    t, c = build_islamic_prompt(_chart())
    assert f"نسخه {PROMPT_VERSION}" in t and c["prompt_version"] == PROMPT_VERSION
    t2, c2 = build_personal_question_prompt(_chart(), "آیا مهاجرت برایم خوب است؟")
    assert f"نسخه {PROMPT_VERSION}" in t2 and c2["prompt_version"] == PROMPT_VERSION
    assert "<پرسش_کاربر>" in t2 and "</پرسش_کاربر>" in t2   # untrusted question fenced