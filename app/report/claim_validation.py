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


def sign_of(planet_key: str, chart: dict, default: str = "") -> str:
    """Actual sign from the chart for a planet key ('sun', 'moon', 'ascendant'...)."""
    if planet_key == "ascendant":
        ang = (chart.get("angles") or {}).get("asc", {}) or (chart.get("angles") or {}).get("ascendant", {})
        return (ang.get("sign") if isinstance(ang, dict) else "") or default
    pl = (chart.get("planets") or {}).get(planet_key, {})
    return (pl.get("sign") if isinstance(pl, dict) else "") or default


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