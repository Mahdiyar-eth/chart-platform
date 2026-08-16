"""A2 — deterministic Claim/Evidence validation (M8 amendment).

Cross-checks an LLM section against the actual chart factors instead of
trusting the prompt: extract planet+sign claims from the output text and
verify them against the chart positions. This is the hard gate behind
"critical hallucination = 0" — a nice prompt alone guarantees nothing.

Usage:
    from app.report.claim_validation import validate_section, critical_facts

    rep = validate_section("identity", output_text, chart_json)
    rep.mismatches      # [(planet, claimed_sign, actual_sign), ...]  → hallucination
    rep.grounded        # ≥1 chart-fact referenced correctly
    rep.critical_hallucination  # bool — ANY mismatch is critical
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── dictionaries ──────────────────────────────────────────────────────────
# Persian names (as generated in prompt context) → canonical English sign keys
SIGN_FA: dict[str, str] = {
    "حمل": "aries", "ثور": "taurus", "جوزا": "gemini", "سرطان": "cancer",
    "اسد": "leo", "سنبله": "virgo", "میزان": "libra", "عقرب": "scorpio",
    "قوس": "sagittarius", "جدی": "capricorn", "دلو": "aquarius", "حوت": "pisces",
}
SIGN_EN: dict[str, str] = {
    "aries": "aries", "taurus": "taurus", "gemini": "gemini", "cancer": "cancer",
    "leo": "leo", "virgo": "virgo", "libra": "libra", "scorpio": "scorpio",
    "sagittarius": "sagittarius", "capricorn": "capricorn",
    "aquarius": "aquarius", "pisces": "pisces",
}
PLANET_FA: dict[str, str] = {
    "خورشید": "sun", "ماه": "moon", "عطارد": "mercury", "زهره": "venus",
    "مریخ": "mars", "مشتری": "jupiter", "زحل": "saturn", "اورانوس": "uranus",
    "نپتون": "neptune", "پلوتو": "pluto", "طالع": "ascendant",
}
# English planet strings commonly found in model output
PLANET_EN: dict[str, str] = {
    "sun": "sun", "moon": "moon", "mercury": "mercury", "venus": "venus",
    "mars": "mars", "jupiter": "jupiter", "saturn": "saturn",
    "uranus": "uranus", "neptune": "neptune", "pluto": "pluto",
    "ascendant": "ascendant", "rising": "ascendant", "اسندنت": "ascendant",
}

_SIGN_FA_RE = re.compile("|".join(re.escape(k) for k in SIGN_FA))
_SIGN_EN_RE = re.compile(r"\b(" + "|".join(SIGN_EN) + r")\b", re.I)
_PLANET_FA_RE = re.compile("|".join(re.escape(k) for k in PLANET_FA))
_PLANET_EN_RE = re.compile(r"\b(" + "|".join(PLANET_EN) + r")\b", re.I)


_SIGN_ORDER = ["aries", "taurus", "gemini", "cancer", "leo", "virgo",
               "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"]


def sign_of(planet_key: str, chart: dict, default: str = "") -> str:
    """Actual sign from the chart for a planet key ('sun', 'moon', 'ascendant'...)."""
    if planet_key == "ascendant":
        ang = (chart.get("angles") or {}).get("asc", {}) or (chart.get("angles") or {}).get("ASC", {})
        if isinstance(ang, dict):
            return (ang.get("sign") or _sign_from_lon(ang.get("longitude"))) or default
        return default
    pl = (chart.get("planets") or {}).get(planet_key, {})
    if not isinstance(pl, dict):
        return default
    return (pl.get("sign") or _sign_from_lon(pl.get("longitude"))) or default


def _sign_from_lon(lon: object) -> str:
    if lon is None:
        return ""
    try:
        return _SIGN_ORDER[int(float(lon) // 30) % 12]
    except (TypeError, ValueError):
        return ""


def critical_facts(chart: dict) -> list[tuple[str, str]]:
    """(planet_key, sign_key) pairs that must never be contradicted."""
    facts: list[tuple[str, str]] = []
    for pk in ("sun", "moon", "mercury", "venus", "mars", "jupiter",
               "saturn", "uranus", "neptune", "pluto"):
        s = sign_of(pk, chart)
        if s:
            facts.append((pk, s))
    a = sign_of("ascendant", chart)
    if a:
        facts.append(("ascendant", a))
    return facts


@dataclass
class ValidationReport:
    claims_found: int = 0
    matches: list[tuple[str, str]] = field(default_factory=list)
    mismatches: list[tuple[str, str, str]] = field(default_factory=list)  # (planet, claimed, actual)
    house_mismatches: list[tuple[str, int, int]] = field(default_factory=list)
    degree_mismatches: list[tuple[str, float, float]] = field(default_factory=list)
    aspect_mismatches: list[tuple[str, str, str, str]] = field(default_factory=list)
    retro_mismatches: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # unverifiable/soft signals
    grounded: bool = False
    critical_hallucination: bool = False

    @property
    def ok(self) -> bool:
        return self.grounded and not self.critical_hallucination


def _normalize_sign(raw: str) -> str:
    raw = raw.strip().lower()
    return SIGN_FA.get(raw, SIGN_EN.get(raw, ""))


def _normalize_planet(raw: str) -> str:
    raw = raw.strip().lower()
    return PLANET_FA.get(raw, PLANET_EN.get(raw, ""))


def extract_claims(text: str) -> list[tuple[str, str]]:
    """Find (planet, sign) claims. Chunks are split on sentence/compound
    separators only (never on Persian 'و', which appears inside words).
    Within a chunk, planets and signs are paired by order of appearance when
    counts match; unequal counts → chunk skipped (no false hallucinations)."""
    claims: list[tuple[str, str]] = []
    for chunk in re.split(r"[،,;؛.\n]", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        planets: list[str] = [m.group(0) for m in _PLANET_FA_RE.finditer(chunk)]
        planets += [m.group(0) for m in _PLANET_EN_RE.finditer(chunk)]
        signs: list[str] = [m.group(0) for m in _SIGN_FA_RE.finditer(chunk)]
        signs += [m.group(0) for m in _SIGN_EN_RE.finditer(chunk)]
        if len(planets) == 1 and len(signs) == 1:
            claims.append((_normalize_planet(planets[0]), _normalize_sign(signs[0])))
        elif len(planets) == len(signs) and len(planets) > 1 and len(planets) <= 4:
            for p, s in zip(planets, signs):
                claims.append((_normalize_planet(p), _normalize_sign(s)))
    return claims


def validate_section(domain: str, output_text: str, chart: dict) -> ValidationReport:
    """Deterministic cross-check: every planet+sign claim in the output must
    match the chart. A mismatch anywhere = critical hallucination."""
    facts = critical_facts(chart)
    fact_lookup = dict(facts)
    rep = ValidationReport()

    for planet, claimed in extract_claims(output_text):
        actual = fact_lookup.get(planet)
        if not actual:
            continue  # planet not in chart — not a claim about a known fact
        rep.claims_found += 1
        if claimed == actual:
            rep.matches.append((planet, claimed))
        else:
            rep.mismatches.append((planet, claimed, actual))
            rep.critical_hallucination = True

    # grounded = at least one TRUE chart-fact reference (any planet)
    rep.grounded = len(rep.matches) > 0
    return rep


# ═══════════════ A2b — advanced claim types (final amendment set) ═══════════
# planet→house, planet→degree, planet↔planet aspect, ASC/MC sign,
# retrograde, transit (unverifiable), moon-uncertainty (soft note).

HOUSE_FA = {"اول": 1, "دوم": 2, "سوم": 3, "چهارم": 4, "پنجم": 5, "ششم": 6,
            "هفتم": 7, "هشتم": 8, "نهم": 9, "دهم": 10, "یازدهم": 11, "دوازدهم": 12}
ASPECT_FA = {"مقارنه": "conjunction", "تریتون": "trine", "سکستایل": "sextile", "مربع": "square",
             "تقابل": "opposition", "سداسی": "sextile", "مثلثی": "trine",
             "conjunction": "conjunction", "trine": "trine", "sextile": "sextile",
             "square": "square", "opposition": "opposition", "تثلیث": "trine"}
RETRO_FA = ["رتروگراد", "بازگشتی", "وارونه", "retrograde"]


def _num(text: str) -> str:
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٤٥٦", "0123456789456"))


def _lon_of(planet_key: str, chart: dict) -> float | None:
    if planet_key == "ascendant":
        ang = (chart.get("angles") or {}).get("asc") or (chart.get("angles") or {}).get("ASC") or {}
        lon = ang.get("longitude")
        return float(lon) if lon is not None else None
    p = (chart.get("planets") or {}).get(planet_key, {})
    lon = p.get("longitude") if isinstance(p, dict) else None
    return float(lon) if lon is not None else None


def house_of(planet_key: str, chart: dict) -> int | None:
    """Whole-sign: index of the 30°-segment above the ASC longitude."""
    asc = _lon_of("ascendant", chart)
    lon = _lon_of(planet_key, chart)
    if asc is None or lon is None:
        return None
    return int(((lon - asc) % 360.0) // 30) + 1


def degree_of(planet_key: str, chart: dict) -> float | None:
    lon = _lon_of(planet_key, chart)
    return (lon % 30.0) if lon is not None else None


def aspect_between(p1: str, p2: str, chart: dict) -> tuple[str, float] | None:
    """Closest major aspect (orb ≤ 6°): (kind, orb). None when not an aspect."""
    l1, l2 = _lon_of(p1, chart), _lon_of(p2, chart)
    if l1 is None or l2 is None:
        return None
    diff = abs(l1 - l2) % 360.0
    diff = min(diff, 360.0 - diff)
    for target, kind in ((0, "conjunction"), (60, "sextile"), (90, "square"),
                         (120, "trine"), (180, "opposition")):
        orb = abs(diff - target)
        if orb <= 6.0:
            return kind, round(orb, 1)
    return None


def _extract_house(text: str) -> list[tuple[str, int]]:
    out = []
    for m in re.finditer(r"(خورشید|ماه|عطارد|زهره|مریخ|مشتری|زحل|اورانوس|نپتون|پلوتو|طالع|sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)\s*(?:در|داخل|درون)?\s*(?:خانه|خونه)\s*[\u200cٔی]*\s*(اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم|یازدهم|دوازدهم|[۰-۹0-9]+)", text, re.I):
        out.append((_normalize_planet(m.group(1)), int(_num(m.group(2))) if m.group(2).isdigit() else HOUSE_FA[m.group(2)]))
    return out


def _extract_degree(text: str) -> list[tuple[str, float]]:
    out = []
    for m in re.finditer(r"(خورشید|ماه|عطارد|زهره|مریخ|مشتری|زحل|اورانوس|نپتون|پلوتو|sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto).{0,12}?([۰-۹0-9]+)\s*(?:درجه|°)", text, re.I):
        out.append((_normalize_planet(m.group(1)), float(_num(m.group(2)))))
    return out


def _extract_aspect(text: str) -> list[tuple[str, str, str]]:
    out = []
    for m in re.finditer(r"(خورشید|ماه|عطارد|زهره|مریخ|مشتری|زحل|اورانوس|نپتون|پلوتو|sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)\s*(?:در|با)?\s*(مقارنه|تریتون|تثلیث|سکستایل|مربع|تقابل|سداسی|مثلثی|conjunction|trine|sextile|square|opposition)\s*(?:با|و|به|از)?\s*(خورشید|ماه|عطارد|زهره|مریخ|مشتری|زحل|اورانوس|نپتون|پلوتو|sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)", text, re.I):
        out.append((_normalize_planet(m.group(1)), ASPECT_FA[m.group(2).lower()], _normalize_planet(m.group(3))))
    return out


def _extract_retrograde(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"(خورشید|ماه|عطارد|زهره|مریخ|مشتری|زحل|اورانوس|نپتون|پلوتو|sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)\s*(?:در\s*حالت\s*)?(رتروگراد|بازگشتی|وارونه|retrograde)", text, re.I):
        out.append(_normalize_planet(m.group(1)))
    return out


def _is_uncertain_moon(text: str) -> bool:
    """Soft note: moon-position claims that skip uncertainty wording."""
    if "ماه" not in text:
        return False
    return not re.search(r"حدود|تقریباً|تقریبا|شاید|ممکن|نزدیک|حوالی|~", text)


def validate_advanced(domain: str, output_text: str, chart: dict) -> ValidationReport:
    """Planet/sign + house + degree + aspect + ASC/MC + retrograde validation.
    Transit and moon-uncertainty are recorded as notes, not hard failures."""
    rep = validate_section(domain, output_text, chart)
    facts = dict(critical_facts(chart))

    # planet → house (whole-sign)
    for p, h in _extract_house(output_text):
        if p not in facts:
            continue
        actual = house_of(p, chart)
        if actual is None:
            continue
        rep.claims_found += 1
        if h == actual:
            rep.matches.append((p, f"house{actual}"))
        else:
            rep.house_mismatches.append((p, h, actual))
            rep.critical_hallucination = True

    # planet → degree (±2°)
    for p, d in _extract_degree(output_text):
        if p not in facts:
            continue
        actual = degree_of(p, chart)
        if actual is None:
            continue
        rep.claims_found += 1
        if abs(d - actual) <= 2.0:
            rep.matches.append((p, f"{actual:.0f}°"))
        else:
            rep.degree_mismatches.append((p, d, actual))
            rep.critical_hallucination = True

    # planet ↔ planet aspect
    for p1, kind, p2 in _extract_aspect(output_text):
        if p1 not in facts or p2 not in facts:
            continue
        got = aspect_between(p1, p2, chart)
        if got is None:
            rep.aspect_mismatches.append((p1, p2, kind, "no major aspect"))
            rep.critical_hallucination = True
            continue
        got_kind, orb = got
        rep.claims_found += 1
        if got_kind == kind:
            rep.matches.append((p1, f"{kind} {p2}"))
        else:
            rep.aspect_mismatches.append((p1, p2, kind, got_kind))
            rep.critical_hallucination = True

    # MC — sign from chart angles, validated when the chart carries it
    mc = (chart.get("angles") or {}).get("mc")
    if isinstance(mc, dict) and (mc.get("sign") or mc.get("longitude") is not None):
        claimed_mc = re.search(r"(?:میدهد|میانه|MC|امسی)\s*[\u200cٔ]*\s*(?:آسمان\s+)?(?:در|:)\s*(?:برج\s+)?(حمل|ثور|جوزا|سرطان|اسد|سنبله|میزان|عقرب|قوس|جدی|دلو|حوت|aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)", output_text, re.I)
        actual_mc = mc.get("sign") or _sign_from_lon(mc.get("longitude")) or ""
        if claimed_mc and actual_mc:
            cs = _normalize_sign(claimed_mc.group(1))
            rep.claims_found += 1
            if cs == actual_mc:
                rep.matches.append(("mc", actual_mc))
            else:
                rep.mismatches.append(("mc", cs, actual_mc))
                rep.critical_hallucination = True
    # retrograde (only when the chart carries retrograde flags)
    chart_retro = {p: v for p, v in (chart.get("planets") or {}).items()
                   if isinstance(v, dict) and v.get("retrograde") is not None}
    for p in _extract_retrograde(output_text):
        if p not in chart_retro:
            rep.notes.append(f"retrograde-unverifiable:{p}")
        elif chart_retro[p].get("retrograde") is True:
            rep.claims_found += 1
            rep.matches.append((f"{p}-retrograde", "retrograde"))
        else:
            rep.retro_mismatches.append(p)
            rep.critical_hallucination = True

    # transit claims → prompt-keepaway note (chart has no transits today)
    if re.search(r"ترانزیت|عبور\s+سیاره|transit", output_text, re.I):
        rep.notes.append("transit-claimed-without-chart-transits")

    # moon-uncertainty soft note
    if "moon" in facts and _is_uncertain_moon(output_text):
        rep.notes.append("moon-position-without-uncertainty")

    if not rep.grounded:
        rep.grounded = len(rep.matches) > 0
    return rep