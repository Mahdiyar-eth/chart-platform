"""focus_areas + personal_question must actually affect the report (broken-promise fix)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.prompt_builder import (FOCUS_TO_DOMAIN, build_personal_question_prompt,
                                       order_domains_by_focus)
from app.report.rules import DOMAINS


def test_focus_mapping_covers_all_form_labels():
    form_labels = ["هویت و شخصیت", "ذهن و منطق", "عواطف و شهود", "پول و ثروت", "شغل",
                   "روابط و ازدواج", "خانواده", "انرژی و تندرستی", "خلاقیت",
                   "آموزش و مهاجرت", "شبکه‌ها و دوستان", "معنویت", "کارما"]
    for label in form_labels:
        assert label in FOCUS_TO_DOMAIN, f"missing mapping for {label}"
        assert FOCUS_TO_DOMAIN[label] in DOMAINS


def test_order_domains_by_focus_puts_focused_first():
    domains = list(DOMAINS.keys())  # 13 domains, identity first
    ordered = order_domains_by_focus(domains, ["پول و ثروت", "شغل"])
    assert ordered[0] == "money"      # focused first
    assert ordered[1] == "career"
    assert len(ordered) == len(domains)
    assert set(ordered) == set(domains)


def test_order_domains_no_focus_keeps_order():
    domains = list(DOMAINS.keys())
    assert order_domains_by_focus(domains, None) == domains
    assert order_domains_by_focus(domains, []) == domains


def test_order_domains_ignores_unknown_labels():
    domains = list(DOMAINS.keys())
    ordered = order_domains_by_focus(domains, ["چیزی ناموجود", "پول و ثروت"])
    assert ordered[0] == "money"
    assert len(ordered) == len(domains)


def test_personal_question_prompt_contains_question():
    # minimal chart shape
    chart = {"planets": {}, "aspects": [], "moon_phase": "رو به رشد",
             "birth": {"time_known": True}}
    prompt, ctx = build_personal_question_prompt(chart, "چرا همیشه دیر تصمیم می‌گیرم؟")
    assert "چرا همیشه دیر تصمیم می‌گیرم؟" in prompt
    assert ctx["domain"] == "personal_question"
    # the prompt must NOT ask for predictive claims
    assert "آینده" not in prompt or "هرگز ادعای قطعی" in prompt
