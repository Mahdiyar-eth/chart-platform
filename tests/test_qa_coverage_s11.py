"""ZAYCHE §11 — QA coverage regression: forbidden words must be caught in
EVERY free-text field of a section (intro, practical_advice, strengths,
challenges), not just insight bodies (F-§11 final audit finding)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.qa import qa_section

CHART = {"planets": {"Sun": {"longitude": 149.7, "sign_fa": "اسد", "house": 1}},
         "angles": {"ASC": {"longitude": 149.7, "sign_fa": "اسد", "house": 1}},
         "houses": {}, "aspects": []}


def _ok_section():
    return {
        "section": "identity", "title_fa": "هویت و شخصیت",
        "intro": "بر اساس خورشید در اسد، هویت شما مشخص است.",
        "insights": [{
            "insight": "خورشید در برج اسد و خانه اول، اراده و اعتماد به نفس شما را شکل می‌دهد. "
                       "شما ذاتاً رهبر متولد شده‌اید و در مرکز توجه بودن برایتان طبیعی است. "
                       "این موقعیت به شما خلاقیت و جسارت می‌بخشد. شما به دنبال شناخته شدن هستید "
                       "و از چالش‌ها نمی‌ترسید. مسیر شما ساختن و الهام بخشیدن به دیگران است.",
            "evidence": [{"factor": "Sun", "sign": "اسد", "house": 1}],
            "strengths": ["رهبری طبیعی"], "challenges": ["غرور"],
            "practical_advice": "هر روز چند دقیقه را به تمرین تمرکز اختصاص دهید.",
        }, {
            "insight": "با طالع اسد، حضور شما در جمع‌ها پررنگ و تأثیرگذار است. "
                       "شما به دیگران انگیزه می‌دهید و مسیر روشنی را نشان می‌دهید. "
                       "احترام و قدردانی برای شما مهم است و به دنبال رشد شخصی هستید. "
                       "شما در موقعیت‌های دشوار، قدرت تصمیم‌گیری دارید. "
                       "کمک به دیگران برای شما رضایت عمیق به ارمغان می‌آورد.",
            "evidence": [{"factor": "ASC", "sign": "اسد", "house": 1}],
            "strengths": ["تأثیرگذاری"], "challenges": ["لجبازی"],
            "practical_advice": "خودتان را با دیگران مقایسه نکنید و روی رشد خود تمرکز کنید.",
        }],
    }


def test_clean_section_passes():
    assert qa_section(_ok_section(), CHART, "identity") == []


def test_forbidden_in_intro_rejected():
    s = _ok_section()
    s["intro"] = "راه‌های درمان این موضوع را بررسی می‌کنیم."
    assert qa_section(s, CHART, "identity")


def test_forbidden_in_practical_advice_rejected():
    s = _ok_section()
    s["insights"][0]["practical_advice"] = "برای درمان این مشکل، استراحت کنید."
    assert qa_section(s, CHART, "identity")


def test_forbidden_in_strengths_rejected():
    s = _ok_section()
    s["insights"][0]["strengths"] = ["عدم نیاز به درمان"]
    assert qa_section(s, CHART, "identity")


def test_forbidden_in_challenges_rejected():
    s = _ok_section()
    s["insights"][1]["challenges"] = ["ترس از مرگ"]
    assert qa_section(s, CHART, "identity")
