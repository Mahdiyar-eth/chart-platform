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
                       "این موقعیت به شما خلاقیت و جسارت می‌بخشد و شما را در مسیر شناخته شدن قرار می‌دهد. "
                       "شما به دنبال دیده شدن هستید و از چالش‌ها نمی‌ترسید، بلکه آن‌ها را فرصتی برای رشد می‌دانید. "
                       "مسیر شما ساختن، الهام بخشیدن و هدایت دیگران به سمت بهترین نسخه خودشان است. "
                       "اراده شما در برج اسد از خورشید می‌آید و این اراده در خانه اول به شکل ظاهر شما دیده می‌شود.",
            "evidence": [{"factor": "Sun", "sign": "اسد", "house": 1}],
            "strengths": ["رهبری طبیعی"], "challenges": ["غرور"],
            "practical_advice": "هر روز چند دقیقه را به تمرین تمرکز اختصاص دهید.",
        }, {
            "insight": "با طالع اسد، حضور شما در جمع‌ها پررنگ و تأثیرگذار است و دیگران به طور طبیعی به شما توجه می‌کنند. "
                       "شما به دیگران انگیزه می‌دهید، مسیر روشنی را نشان می‌دهید و در لحظه‌های سخت، تکیه‌گاه جمع هستید. "
                       "احترام و قدردانی برای شما مهم است و به دنبال رشد شخصی و پیشرفت در زندگی حرفه‌ای خود هستید. "
                       "شما در موقعیت‌های دشوار قدرت تصمیم‌گیری دارید و از پذیرش مسئولیت نمی‌گریزید. "
                       "کمک به دیگران برای شما رضایت عمیق به ارمغان می‌آورد و انرژی شما را دوچندان می‌کند. "
                       "این ویژگی‌ها در کنار اراده قوی، شما را به فردی اثرگذار در محیط خود تبدیل می‌کند.",
            "evidence": [{"factor": "ASC", "sign": "اسد", "house": 1}],
            "strengths": ["تأثیرگذاری"], "challenges": ["لجبازی"],
            "practical_advice": "خودتان را با دیگران مقایسه نکنید و روی رشد خود تمرکز کنید.",
        }],
    }


def test_clean_section_passes():
    assert qa_section(_ok_section(), CHART, "identity") == []


def test_forbidden_in_intro_rejected():
    """Predictive death phrase in intro → rejected (R.2 context-aware policy)."""
    s = _ok_section()
    s["intro"] = "در آینده نزدیک اتفاق مهمی رخ خواهد داد."
    assert qa_section(s, CHART, "identity")


def test_forbidden_in_practical_advice_rejected():
    """Medical-advice phrase → rejected (R.2 context-aware policy)."""
    s = _ok_section()
    s["insights"][0]["practical_advice"] = "برای درمان بیماری قلبی، دارو مصرف کنید."
    assert qa_section(s, CHART, "identity")


def test_forbidden_in_strengths_rejected():
    """Death-prediction phrase in strengths → rejected (R.2)."""
    s = _ok_section()
    s["insights"][0]["strengths"] = ["روزی خواهی رسید به آرامش کامل"]
    assert qa_section(s, CHART, "identity")


def test_forbidden_in_challenges_rejected():
    """Predictive tone (مقدر) in challenges → rejected (R.2)."""
    s = _ok_section()
    s["insights"][1]["challenges"] = ["مقدر شده که مسیر سختی پیش رو داشته باشی"]
    assert qa_section(s, CHART, "identity")

def test_benign_literary_words_now_pass():
    """R.2: benign literary use of مرگ/درمان/قطعی must NOT reject the section."""
    s = _ok_section()
    s["intro"] = "مرگ نفس و تولدی دوباره، درمان دل با مهر."
    assert qa_section(s, CHART, "identity") == []
