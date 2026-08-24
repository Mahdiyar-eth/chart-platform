"""Synastry (plan §8 + MASTER W8) — cross-chart aspects + compatibility.

W8: the old single «سیناستری» is SPLIT into two products with different
lenses and prompts:
  - «سازگاری عاطفی» (synastry_love): Venus/Moon/Mars — emotional pattern
  - «سازگاری کاری» (synastry_work): Sun/Mars/Saturn/Mercury — work pattern

`variant` selects the lens; the overall score is variant-weighted so each
product answers its own question honestly.
"""
from __future__ import annotations

_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
            "Uranus", "Neptune", "Pluto"]
_ASPECTS = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}
_ORB = 5.0

_ASPECT_FA = {"Conjunction": "همپیوندی", "Opposition": "مقابله", "Trine": "سهگانه",
              "Square": "تربیع", "Sextile": "ششگانه"}

# domain → planets of person A involved
_DOMAINS = {
    "love": ["Venus", "Moon", "Mars"],
    "mind": ["Mercury", "Moon"],
    "career": ["Sun", "Mars", "Saturn"],
    "spirit": ["Jupiter", "Sun"],
}

# MASTER W8 — variant lenses
VARIANTS = {
    "love": {
        "title_fa": "سازگاری عاطفی",
        "domains": ["love", "mind"],          # ranked: emotional first
        "planets_a": {"Venus", "Moon", "Mars", "Mercury"},
        "question": "الگوی رابطه‌ای شما دو نفر چگونه کار می‌کند؟",
    },
    "work": {
        "title_fa": "سازگاری کاری",
        "domains": ["career", "spirit"],      # ranked: work first
        "planets_a": {"Sun", "Mars", "Saturn", "Jupiter"},
        "question": "به‌عنوان هم‌تیمی یا هم‌شرکت چطور کنار هم کار می‌کنید؟",
    },
}


def synastry(chart_a: dict, chart_b: dict, variant: str = "love") -> dict:
    v = VARIANTS.get(variant, VARIANTS["love"])
    pa = chart_a.get("planets", {})
    pb = chart_b.get("planets", {})
    connections: list[dict] = []
    for n1 in _PLANETS:
        if n1 not in pa:
            continue
        for n2 in _PLANETS:
            if n2 not in pb or n1 == n2:
                continue
            lon1 = pa[n1]["longitude"]
            lon2 = pb[n2]["longitude"]
            diff = abs(lon1 - lon2) % 360
            diff = min(diff, 360 - diff)
            for asp, ang in _ASPECTS.items():
                if abs(diff - ang) <= _ORB:
                    connections.append({
                        "a": n1, "b": n2, "aspect": asp,
                        "aspect_fa": _ASPECT_FA[asp],
                        "orb": round(abs(diff - ang), 2),
                        "a_sign": pa[n1]["sign_fa"], "b_sign": pb[n2]["sign_fa"],
                    })

    # per-domain score: weighted positive/negative aspect balance
    def _domain_score(planets_a: list[str]) -> float:
        pos = neg = 0.0
        for c in connections:
            if c["a"] not in planets_a:
                continue
            w = 1.0 / (1.0 + c["orb"])
            if c["aspect"] in ("Conjunction", "Trine", "Sextile"):
                pos += w
            else:
                neg += w
        total = pos + neg
        if total == 0:
            return 50.0
        return round(50 + 50 * (pos - neg) / total, 1)

    domains = {k: _domain_score(v_) for k, v_ in _DOMAINS.items()}
    # W8: the OVERALL score is variant-weighted — love leans on love/mind,
    # work leans on career/spirit, so two products give two honest answers.
    lens = v["domains"]
    primary = [domains[d] for d in lens if d in domains]
    secondary = [domains[d] for d, s in domains.items() if d not in lens]
    overall = round((sum(primary) / len(primary)) * 0.7
                    + (sum(secondary) / len(secondary)) * 0.3, 1)

    return {
        "variant": variant,
        "variant_title_fa": v["title_fa"],
        "connections_count": len(connections),
        "connections": sorted(connections, key=lambda c: -1.0 / (1.0 + c["orb"]))[:24],
        "domains": domains,
        "primary_domains": lens,
        "overall": overall,
        "verdict": _verdict(overall),
    }


def _verdict(score: float) -> str:
    if score >= 80:
        return "هماهنگی بسیار بالا — رابطه‌ای پر از حمایت متقابل"
    if score >= 65:
        return "هماهنگی خوب — تفاوت‌ها مکمل‌اند"
    if score >= 50:
        return "هماهنگی متوسط — نیاز به گفت‌وگو در برخی حوزه‌ها"
    if score >= 35:
        return "هماهنگی کم — چالش‌های قابل‌انتظار؛ با آگاهی قابل مدیریت"
    return "هماهنگی دشوار — نیاز به کار جدی روی ارتباط"
