"""Plan-differentiation tests (plan v3.0 §10.3): basic=5 / full=13 / gold=13+islamic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.astrology.engine import compute_from_fields
from app.report.generator import generate_sections
from app.report.prompt_builder import build_prompts_for_plan, PLAN_SECTIONS
from tests.test_report_engine import CHART, FakeRouter


def test_plan_section_sets_match_plan():
    assert PLAN_SECTIONS["basic"] == ["identity", "mind", "emotions", "career", "money"]
    assert len(PLAN_SECTIONS["full"]) == 13
    assert len(PLAN_SECTIONS["gold"]) == 14 and "islamic" in PLAN_SECTIONS["gold"]


def test_basic_plan_generates_5_sections():
    sections, metrics = generate_sections(CHART, router=FakeRouter(), plan_key="basic")
    assert len(sections) == 5
    assert set(sections) == set(PLAN_SECTIONS["basic"])
    assert metrics["calls"] == 5  # no LLM calls beyond the 5 sections


def test_full_plan_generates_13_sections():
    sections, _ = generate_sections(CHART, router=FakeRouter(), plan_key="full")
    assert len(sections) == 13
    assert set(sections) == set(PLAN_SECTIONS["full"])


def test_gold_plan_includes_islamic_chapter():
    sections, _ = generate_sections(CHART, router=FakeRouter(), plan_key="gold")
    assert "islamic" in sections
    assert len(sections) == 14
    # islamic prompt is cultural — must exist and be separate from domains
    prompts = build_prompts_for_plan(CHART, "gold")
    assert "islamic" in prompts
    assert "فرهنگ" in prompts["islamic"][0]


def test_basic_cost_less_than_gold():
    _, m1 = generate_sections(CHART, router=FakeRouter(), plan_key="basic")
    _, m2 = generate_sections(CHART, router=FakeRouter(), plan_key="gold")
    assert m1["calls"] < m2["calls"]
    assert m1["cost_usd"] <= m2["cost_usd"]
