"""QA predictive-tone tests (audit round 2 — ZAYCHE-COMPLETE-REPORT).

Verifies qa_section rejects soft predictive phrasing (fortune-telling TONE)
that carries no explicit divination word, while allowing neutral astrological
vocabulary (e.g. «خانه سرنوشت» = the 10th house's traditional name).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.astrology.engine import compute_from_fields
from app.report.qa import qa_section

CHART = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json

LONG = ("این جایگاه نشان می‌دهد که کیفیت زندگی شما با گذر زمان و تلاش پیوسته شکل می‌گیرد. "
        "نقش سیارات در این بخش از چارت، الگوی مشخصی از رشد و بلوغ را نشان می‌دهد که با تجربه‌های "
        "واقعی زندگی هماهنگ است. شما با شناخت این الگو می‌توانید انتخاب‌های آگاهانه‌تری داشته باشید "
        "و مسیر خود را با دقت بیشتری ادامه دهید. این نگاه، ریشه در محاسبات نجومی دقیق و تحلیل "
        "جایگاه سیارات دارد و به شما کمک می‌کند تصویر روشن‌تری از ظرفیت‌های خود ببینید. زندگی، "
        "حاصل ترکیب انتخاب‌های شما و شرایط پیرامون است و چارت، نقشه‌ای برای شناخت بهتر این ترکیب.")


def _section(phrase: str) -> dict:
    """Build a valid 2-insight section where the FIRST insight carries `phrase`."""
    return {
        "section": "relationships",
        "title_fa": "روابط",
        "intro": LONG,
        "insights": [
            {"insight": phrase + " " + LONG,
             "evidence": [{"factor": "Venus", "sign": "Libra", "house": 2}],
             "strengths": ["الف"], "challenges": ["ب"], "practical_advice": "ج."},
            {"insight": LONG,
             "evidence": [{"factor": "Saturn", "sign": "Pisces", "house": 7}],
             "strengths": ["د"], "challenges": ["ه"], "practical_advice": "و."},
        ],
    }


def _forbidden_errors(phrase: str) -> list[str]:
    return [e for e in qa_section(_section(phrase), CHART, "relationships")
            if "عبارت ممنوع" in e]


# ── predictive TONE phrases must be rejected ─────────────────────────────
@pytest.mark.parametrize("phrase", [
    "در آینده نزدیک اتفاقات مهمی رخ می‌دهد",
    "به‌زودی خبر خوبی دریافت خواهی کرد",
    "به زودی مسیر شغلی شما تغییر می‌کند",
    "مقدر شده است که در این دوره به آرامش برسی",
    "سرنوشت تو این است که به موفقیت برسی",
    "موفقیت نصیب تو خواهد شد",
    "شانس در انتظار توست",
    "روزی خواهی فهمید چرا این اتفاق افتاد",
    "در نیمه دوم زندگی به آرامش خواهی رسید",
    "او برای تو فال گرفت و نتیجه را گفت",
])
def test_qa_rejects_predictive_tone(phrase: str):
    errs = _forbidden_errors(phrase)
    assert errs, f"پیش‌گویی «{phrase}» باید رد شود"


# ── ZWNJ-insensitive: پیش‌گویی (with نیم‌فاصله) still caught ────────────
def test_qa_rejects_zwnj_variant():
    errs = _forbidden_errors("این متن پیش‌گویی درباره آینده شماست")
    assert errs, "نوشتن پیش‌گویی با نیم‌فاصله باید گرفته شود"


# ── neutral astrological vocabulary must NOT be rejected ─────────────────
@pytest.mark.parametrize("phrase", [
    "خانه دهم را خانه سرنوشت و جایگاه شغل می‌نامند",   # سرنوشت alone = OK
    "نگاه به آینده با تأمل، بخشی از سفر خودشناسی است",   # آینده alone = OK
    "ترانزیت زحل هر ۲۹ سال یک بار تکرار می‌شود",
    "این الگو در انتظار بررسی دقیق‌تر محاسبات است",       # انتظار ≠ در انتظار تو
])
def test_qa_allows_neutral_astro_language(phrase: str):
    errs = _forbidden_errors(phrase)
    assert not errs, f"عبارت خنثی «{phrase}» نباید رد شود: {errs}"


# ── existing guards still work (regression) ──────────────────────────────
@pytest.mark.parametrize("phrase", [
    "قطعاً در این ماه اتفاق بزرگی می‌افتد",
    "این درمان برای بیماری شما تجویز می‌شود",
    "طلسم و جادو بر زندگی شما اثر دارد",
])
def test_qa_keeps_original_forbidden_words(phrase: str):
    errs = _forbidden_errors(phrase)
    assert errs, f"واژهٔ صریح ممنوع «{phrase}» باید رد شود"
