"""
Auto QA — every section must pass before it enters the report (plan v3.1 §6.4).

Checks: valid JSON, evidence grounded in Chart JSON, no invented factors,
no medical/fortune absolutes, min length, no boilerplate repetition.
"""
from __future__ import annotations

import json
import re

FORBIDDEN_PATTERNS = [
    # medical claims (تشخیص/بستری are common Persian verbs — too blunt to ban)
    r"درمان", r"دارو", r"بیماری", r"مرگ", r"فوت",
    # absolute fortune claims (حتما/همیشه/هرگز are common Persian adverbs)
    r"قطعاً", r"قطعی", r"یقیناً", r"مطمئناً", r"پیشگویی",
    # divination claims (غیب alone = "the unseen", poetic — ban only گویی/گو)
    r"غیبگویی", r"غیبگو", r"طلسم", r"جادو",
    # predictive TONE without explicit divination words (audit round 2):
    # «در آینده نزدیک», «به‌زودی», «مقدر شده/است», «سرنوشت تو», «نصیب تو»,
    # «در انتظار توست», «روزی خواهی/روزی به», «خواهی رسید/شد/داشت/یافت»,
    # «فال گرفتن/گفتن» — high-precision phrases; common neutral uses excluded
    r"در آینده(ی)? نزدیک",
    r"به ?زودی",
    r"مقدر",
    r"سرنوشت تو",
    r"نصیب تو",
    r"در انتظار تو",
    r"روزی (خواهی|به )",
    r"خواهی (رسید|شد|داشت|یافت|گشت)",
    r"فال (گرفتن|گرفت|گفتن|گفت|خواندن|خواند)",
]

VALID_PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                 "Uranus", "Neptune", "Pluto", "Node", "Lilith", "Chiron",
                 "ASC", "MC", "Fortune", "Vertex", "Vx", "VX",
                 "Vesta", "Ceres", "Pallas", "Juno"}

ASPECT_NAMES = {"Conjunction", "Sextile", "Square", "Trine", "Opposition",
                "Quincunx", "SemiSquare", "Sesquiquadrate", "Trigon", "Parallel"}


# Persian→English normalization (F-27b, runtime audit): deepseek writes
# evidence in mixed Persian/English («شش‌ضلعی» for sextile, «تربیع» for square,
# «خورشید» for Sun, «Leo» for اسد). QA must accept both spellings.
# NOTE: keys are written WITHOUT ZWNJ — _norm_token strips ZWNJ before lookup.
_FA_ASPECTS = {
    "اتصال": "Conjunction", "ترکیب": "Conjunction", "همنشینی": "Conjunction",
    "قرینگی": "Opposition", "مقابله": "Opposition", "برابر": "Opposition",
    "تربیع": "Square", "چهارضلعی": "Square",
    "سهضلعی": "Trine", "سه ضلعی": "Trine", "سهگانه": "Trine",
    "ششضلعی": "Sextile", "شش ضلعی": "Sextile", "ششگانه": "Sextile",
    "پنجضلعی": "Quintile", "غیرمتعارف": "Quincunx", "نیمهتربیع": "SemiSquare",
}
_FA_PLANETS = {
    "خورشید": "Sun", "ماه": "Moon", "عطارد": "Mercury", "زهره": "Venus",
    "مریخ": "Mars", "مشتری": "Jupiter", "زحل": "Saturn", "اورانوس": "Uranus",
    "نپتون": "Neptune", "پلوتو": "Pluto", "گره": "Node", "گرهی": "Node",
    "لیلیت": "Lilith", "کیوان": "Saturn", "بهرام": "Mars", "تیر": "Mercury",
    "ناهید": "Venus", "هرمز": "Jupiter", "کایرون": "Chiron",
    "صعود": "ASC", "طالع": "ASC", "صعودی": "ASC",
    "میانه": "MC", "میانه آسمان": "MC", "میل": "MC",
    "قله": "Vx", "راس": "Vx", "بخت": "Fortune", "نقطه": "Fortune",
}
_FA_SIGNS = {
    "حمل": "Aries", "بره": "Aries", "ثور": "Taurus", "گاو": "Taurus",
    "جوزا": "Gemini", "دوپیکر": "Gemini", "خرچنگ": "Cancer", "سرطان": "Cancer",
    "اسد": "Leo", "شیر": "Leo", "سنبله": "Virgo", "دوشیزه": "Virgo",
    "میزان": "Libra", "ترازو": "Libra", "عقرب": "Scorpio", "کژدم": "Scorpio",
    "قوس": "Sagittarius", "کمان": "Sagittarius", "جدی": "Capricorn", "بزغاله": "Capricorn",
    "دلو": "Aquarius", "آبریز": "Aquarius", "حوت": "Pisces", "ماهی": "Pisces",
}


def _norm_token(s: str) -> str:
    """Best-effort Persian→English normalization of an evidence token."""
    t = s.strip().replace("\u200c", "").replace("‌", "")
    if t in _FA_ASPECTS:
        return _FA_ASPECTS[t]
    if t in _FA_PLANETS:
        return _FA_PLANETS[t]
    if t in _FA_SIGNS:
        return _FA_SIGNS[t]
    return t


def _canon(name: str) -> str:
    """Normalize an aspect endpoint to its canonical engine key.

    F-27 (runtime audit): `.title()` mangles the all-caps abbreviations the
    engine emits — "MC".title() == "Mc", "ASC".title() == "Asc" — so valid
    evidence like "Uranus trine MC" / "Sun conjunct ASC" was rejected by QA
    and whole report sections fell back to generic text. F-27b extends this
    with Persian→English normalization of aspects/planets/signs.
    """
    t = _norm_token(name).title()
    t = {"Asc": "ASC", "Mc": "MC"}.get(t, t)  # Vx stays "Vx" — matches engine key
    return t


def parse_section(raw: str) -> dict | None:
    """Robust JSON extraction (strip code fences, find first { ... })."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # find balanced JSON object
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def qa_section(section: dict | None, chart: dict, domain: str) -> list[str]:
    """Return list of QA failures (empty = pass)."""
    errors: list[str] = []
    if section is None:
        return ["خروجی JSON نامعتبر است"]
    # F-32b (runtime audit): the model keeps citing factors that are NOT active
    # in this section (e.g. Node/Lilith/Fortune in a spirituality section whose
    # only active factor is Neptune) — those are fabrications from the model's
    # own astrological memory. Scope evidence to the domain's active factors;
    # when a domain has no active rule at all the builder falls back to Big
    # Three, so every chart factor stays allowed in that case.
    try:
        from app.report.rules import evaluate
        _active_factors = {r["factor"] for r in evaluate(chart).get(domain, [])}
    except Exception:  # noqa: BLE001 — QA must never crash the worker
        _active_factors = set()
    _allow_any = not _active_factors

    insights = section.get("insights", [])
    if not isinstance(insights, list) or len(insights) < 2:
        errors.append(f"{domain}: تعداد insight کافی نیست ({len(insights)})")
    is_cultural = domain == "islamic"  # cultural chapter: evidence = values, not planets

    total_words = 0
    for ins in insights:
        text = ins.get("insight", "")
        if not isinstance(text, str) or len(text.split()) < 40:
            errors.append(f"{domain}: insight کوتاه است")
        total_words += len(text.split())

        for pat in FORBIDDEN_PATTERNS:
            # ZWNJ (نیم‌فاصله) makes Persian spelling ambiguous — normalize it away
            # so «پیش‌گویی» and «پیشگویی» both match the no-ZWNJ pattern.
            if re.search(pat, text.replace("\u200c", "")):
                errors.append(f"{domain}: عبارت ممنوع «{pat}» در متن")
                break

        # evidence groundedness
        for ev in ins.get("evidence", []):
            if is_cultural:
                if not ev:
                    errors.append(f"{domain}: evidence بدون عامل")
                continue
            if isinstance(ev, str):  # model wrote "Pluto Conjunction Node"
                f = ev.split()[0] if ev.split() else ""
            elif isinstance(ev, dict) and ev.get("aspect"):  # {"aspect": "Sun Conjunct ASC"}
                aparts = str(ev["aspect"]).split()
                f = aparts[0] if aparts else ""
                if len(aparts) >= 3 and _canon(aparts[0]) in VALID_PLANETS \
                        and _canon(aparts[-1]) in VALID_PLANETS \
                        and (_canon(aparts[-1]) in chart.get("planets", {})
                             or _canon(aparts[-1]) in chart.get("angles", {})
                             or _canon(aparts[-1]) in {"Vesta", "Ceres", "Pallas", "Juno"}):
                    continue  # valid aspect dict — grounded; no sign/scope check
                elif len(aparts) < 3:
                    continue  # {"aspect": "Conjunction"} — supplementary, skip
                else:
                    errors.append(f"{domain}: جنبه ناشناخته در evidence: {ev.get('aspect')}")
            else:
                f = ev.get("factor", "") if isinstance(ev, dict) else ""
            f = _canon(f.title()) if isinstance(f, str) and f else f
            if not f:
                errors.append(f"{domain}: evidence بدون عامل")
            elif f == "Moon Phase" or f == "Phase":
                pass  # moon phase evidence — grounded in chart["moon_phase"]
            elif f not in VALID_PLANETS:
                # aspect-style string evidence: "Pluto Conjunction Node" or bare "Sextile"
                parts = f.split()
                if len(parts) >= 3 and parts[0] in VALID_PLANETS and parts[2] in VALID_PLANETS:
                    pass  # valid aspect string
                elif len(parts) == 1 and parts[0] in ASPECT_NAMES:
                    pass  # bare aspect name — supplementary evidence
                elif isinstance(ev, dict) and ev.get("p1") in VALID_PLANETS and ev.get("p2") in VALID_PLANETS:
                    pass  # valid aspect dict
                else:
                    errors.append(f"{domain}: عامل جعلی در evidence: {f}")
            elif f not in chart.get("planets", {}) and f not in chart.get("angles", {}):
                # F-27b: a well-known body absent from THIS chart (e.g. the model
                # cites Vesta from training data) is a soft flaw — rejecting the
                # whole section 3× and falling back to generic text is worse.
                if f not in {"Vesta", "Ceres", "Pallas", "Juno", "Lilith", "Chiron"}:
                    errors.append(f"{domain}: عامل {f} در چارت وجود ندارد")
            elif not _allow_any and f not in _active_factors:
                # F-32b: factor is in the chart but NOT active for this section
                # (the builder only sent the active ones) — citing it means the
                # model is improvising from astrological memory. Reject, and the
                # feedback loop tells it to stick to the listed factors.
                errors.append(f"{domain}: عامل {f} خارج از عوامل فعال این بخش است")
            else:
                # verify sign/house if present
                src = chart["planets"].get(f) or chart["angles"].get(f)
                if isinstance(ev, dict) and "sign" in ev and ev["sign"] is not None:
                    # F-30: charts built before the angles sign-metadata fix have
                    # no sign on ASC/MC/Vx — absence of data must not reject a
                    # correct evidence, so only check when the source has a sign.
                    # F-31 (runtime audit): the model writes «برج جدی» (prefix),
                    # «Leo» vs «اسد» — strip the برج prefix; and moon-phase
                    # evidence puts «فاز …» in the sign slot — skip sign check.
                    _ev_sign = str(ev["sign"]).replace("برج ", "").replace("برج", "").strip()
                    src_signs = {s for s in (str(src.get("sign_en", "")).lower(),
                                             str(src.get("sign_fa", "")).lower(),
                                             str(src.get("sign_index", ""))) if s}
                    if (_ev_sign and _ev_sign not in {"نامشخص", "ناشناخته", "نامعلوم", "-", "—"}
                            and src_signs and not _ev_sign.startswith("فاز")
                            and _ev_sign.lower() not in src_signs):
                        errors.append(f"{domain}: برج نادرست در evidence برای {f}: {ev.get('sign')}")

    if total_words < 150:
        errors.append(f"{domain}: کل بخش کوتاه است ({total_words} کلمه)")

    return errors


def qa_repetition(sections: dict[str, dict]) -> list[str]:
    """Boilerplate check: identical sentences across sections."""
    errors = []
    sentences = {}
    for dom, sec in sections.items():
        if not sec:
            continue
        for ins in sec.get("insights", []):
            text = ins.get("insight", "")
            for s in re.split(r"[.؟!]", text):
                s = s.strip()
                if len(s) > 25:
                    sentences.setdefault(s, []).append(dom)
    for s, doms in sentences.items():
        if len(set(doms)) >= 3:
            errors.append(f"جمله تکراری در {len(set(doms))} بخش: «{s[:40]}…»")
    return errors
