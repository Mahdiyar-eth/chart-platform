"""F-27 regression: QA must accept MC/ASC evidence (runtime audit finding).

Root cause: .title() mangles engine abbreviations ("MC".title()=="Mc") so
valid evidence like "Uranus trine MC" was rejected, forcing whole report
sections into generic fallback text (2 of 3 real reports degraded).
"""
from app.report.qa import _canon, qa_section

_CHART = {
    "planets": {
        "Sun": {"sign_en": "Leo", "sign_fa": "اسد", "sign_index": 4},
        "Moon": {"sign_en": "Pisces", "sign_fa": "حوت", "sign_index": 11},
        "Uranus": {"sign_en": "Capricorn", "sign_fa": "جدی", "sign_index": 9},
        "Neptune": {"sign_en": "Capricorn", "sign_fa": "جدی", "sign_index": 9},
        "Mercury": {"sign_en": "Virgo", "sign_fa": "سنبله", "sign_index": 5},
        "Pluto": {"sign_en": "Scorpio", "sign_fa": "عقرب", "sign_index": 7},
        "Mars": {"sign_en": "Leo", "sign_fa": "اسد", "sign_index": 4},
        "Node": {"sign_en": "Scorpio", "sign_fa": "عقرب", "sign_index": 7},
    },
    "angles": {"ASC": {"sign_en": "Leo", "sign_fa": "اسد", "sign_index": 4},
               "MC": {"sign_en": "Taurus", "sign_fa": "ثور", "sign_index": 1}},
}

_LONG_INSIGHT = ("این تحلیل بر پایهی موقعیت سیارات در لحظهی تولد شکل گرفته است و به بررسی "
                 "الگوهای شخصیتی و مسیر رشد فرد کمک میکند. ترکیب این عوامل در کنار یکدیگر "
                 "تصویر روشنتری از توانمندیها و زمینههای رشد ارائه میدهد. " * 3)


def _section(*evidences):
    return {"section": "career", "title_fa": "شغل",
            "intro": "مقدمه", "insights": [
                {"insight": _LONG_INSIGHT, "evidence": list(evidences),
                 "strengths": [], "challenges": []},
                {"insight": _LONG_INSIGHT, "evidence": [], "strengths": [],
                 "challenges": []},
            ]}


def test_canon_normalizes_abbreviations():
    assert _canon("MC") == "MC"
    assert _canon("Mc") == "MC"
    assert _canon("asc") == "ASC"
    assert _canon("Uranus") == "Uranus"
    assert _canon("Moon Phase") == "Moon Phase"


def test_qa_accepts_mc_and_asc_evidence():
    sec = _section({"aspect": "Uranus trine MC"},
                   {"aspect": "Sun conjunct ASC"})
    assert qa_section(sec, _CHART, "career") == []


def test_qa_accepts_factor_asc():
    sec = _section({"factor": "Asc", "sign": "Leo", "house": 1})
    assert qa_section(sec, _CHART, "career") == []


def test_qa_still_rejects_unknown_aspect_endpoint():
    sec = _section({"aspect": "Sun conjunct Sagittarius"})
    errs = qa_section(sec, _CHART, "career")
    assert any("جنبه ناشناخته" in e for e in errs)


# ─── F-27b / F-30: Persian evidence + angles without sign metadata ────────

def test_fa_evidence_accepted():
    """Persian aspect/planet/sign spellings must pass QA."""
    _c = dict(_CHART)
    sec = _section({"factor": "خورشید", "sign": "اسد", "house": 10},
                   {"aspect": "خورشید تربیع نپتون"})
    assert qa_section(sec, _c, "career") == []


def test_angle_evidence_without_sign_metadata_not_rejected():
    """Old charts: angles lack sign_en/sign_fa — absence must not reject."""
    _c = {"planets": dict(_CHART["planets"]),
          "angles": {"ASC": {"house": 1, "longitude": 144.9},
                     "MC": {"house": 10, "longitude": 5.0}}}
    sec = _section({"factor": "ASC", "sign": "Leo", "house": 1})
    assert qa_section(sec, _c, "career") == []


def test_vesta_soft_flaw_not_fatal():
    """Well-known asteroid absent from the chart is a soft flaw (no fallback)."""
    sec = _section({"aspect": "Mercury trine Vesta"})
    assert qa_section(sec, dict(_CHART), "career") == []


def test_sign_check_still_strict_when_metadata_present():
    """Wrong sign with metadata present must still fail."""
    sec = _section({"factor": "Sun", "sign": "Pisces", "house": 10})
    errs = qa_section(sec, dict(_CHART), "career")
    assert any("برج نادرست" in e for e in errs)
