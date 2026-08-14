"""
Rule Engine — data-driven, NOT if/else (Claude review #3).

Each rule: factor, condition, domain, weight, interpretation_key, priority, evidence.
Evaluates canonical Chart JSON → active factors per domain. The LLM never
calculates — this module decides WHAT to tell the writer.
"""
from __future__ import annotations

from dataclasses import dataclass

# 13 life domains (plan v3.1 §8)
DOMAINS = {
    "identity": "هویت و شخصیت",
    "mind": "ذهن و منطق",
    "emotions": "عواطف و شهود",
    "money": "پول و ثروت",
    "career": "شغل و مسیر حرفهای",
    "relationships": "روابط و ازدواج",
    "family": "خانواده و ریشهها",
    "wellbeing": "انرژی و تندرستی",
    "creativity": "فرزند و خلاقیت",
    "education": "آموزش و مهاجرت",
    "network": "شبکهها و دوستان",
    "spirituality": "معنویت",
    "karma": "الگوهای رشد و کارما",
}


@dataclass
class Rule:
    id: str
    domain: str
    factor: str          # planet/angle: Venus, Moon, ASC, MC, 7th_house_cusp...
    condition: dict      # e.g. {"sign": "Libra"}, {"house": 7}, {"aspect": ("Moon", "trine", 6.0)}
    weight: float        # 0..1 — importance
    interpretation_key: str  # i18n key for prompt builder
    priority: int = 1    # higher = always included
    evidence: bool = True


RULES: list[Rule] = [
    # ── identity ──
    Rule("sun_sign", "identity", "Sun", {"sign": "*"}, 1.0, "sun_in_sign", 5),
    Rule("sun_house", "identity", "Sun", {"house": "*"}, 0.9, "sun_in_house", 4),
    Rule("asc_sign", "identity", "ASC", {"sign": "*"}, 1.0, "asc_in_sign", 5),
    Rule("mc_sign", "identity", "MC", {"sign": "*"}, 0.85, "mc_in_sign", 3),
    # ── mind ──
    Rule("mercury_sign", "mind", "Mercury", {"sign": "*"}, 1.0, "mercury_in_sign", 5),
    Rule("mercury_house", "mind", "Mercury", {"house": "*"}, 0.8, "mercury_in_house", 3),
    Rule("mercury_retro", "mind", "Mercury", {"retrograde": True}, 0.75, "mercury_retrograde", 3),
    # ── emotions ──
    Rule("moon_sign", "emotions", "Moon", {"sign": "*"}, 1.0, "moon_in_sign", 5),
    Rule("moon_house", "emotions", "Moon", {"house": "*"}, 0.9, "moon_in_house", 4),
    Rule("moon_phase", "emotions", "Moon", {"phase": "*"}, 0.7, "moon_phase", 3),
    # ── money ──
    Rule("venus_sign", "money", "Venus", {"sign": "*"}, 0.75, "venus_in_sign_money", 2),
    Rule("venus_house", "money", "Venus", {"house": "*"}, 0.85, "venus_in_house", 3),
    Rule("jupiter_sign", "money", "Jupiter", {"sign": "*"}, 0.8, "jupiter_in_sign", 3),
    Rule("jupiter_house", "money", "Jupiter", {"house": "*"}, 0.9, "jupiter_in_house", 4),
    Rule("saturn_sign", "money", "Saturn", {"sign": "*"}, 0.7, "saturn_in_sign", 2),
    Rule("saturn_house", "money", "Saturn", {"house": "*"}, 0.85, "saturn_in_house", 3),
    # ── career ──
    Rule("mc_sign_career", "career", "MC", {"sign": "*"}, 1.0, "mc_career", 5),
    Rule("sun_house_career", "career", "Sun", {"house": 10}, 0.9, "sun_in_10th", 4),
    Rule("saturn_house_career", "career", "Saturn", {"house": 10}, 0.85, "saturn_in_10th", 3),
    Rule("jupiter_house_career", "career", "Jupiter", {"house": 10}, 0.8, "jupiter_in_10th", 2),
    Rule("mars_house", "career", "Mars", {"house": 10}, 0.8, "mars_in_10th", 2),
    Rule("mars_sign", "career", "Mars", {"sign": "*"}, 0.8, "mars_in_sign", 3),
    # ── relationships ──
    Rule("venus_house_rel", "relationships", "Venus", {"house": 7}, 0.95, "venus_in_7th", 5),
    Rule("venus_sign_rel", "relationships", "Venus", {"sign": "*"}, 0.9, "venus_in_sign_rel", 4),
    Rule("moon_house_rel", "relationships", "Moon", {"house": 7}, 0.9, "moon_in_7th", 4),
    Rule("mars_house_rel", "relationships", "Mars", {"house": 7}, 0.85, "mars_in_7th", 3),
    Rule("saturn_house_rel", "relationships", "Saturn", {"house": 7}, 0.95, "saturn_in_7th", 5),
    Rule("saturn_retro_rel", "relationships", "Saturn", {"retrograde": True}, 0.7, "saturn_retrograde_rel", 2),
    # ── family (fallbacks: always cover) ──
    Rule("moon_house_fam", "family", "Moon", {"house": 4}, 0.9, "moon_in_4th", 4),
    Rule("sun_house_fam", "family", "Sun", {"house": 4}, 0.85, "sun_in_4th", 3),
    Rule("saturn_house_fam", "family", "Saturn", {"house": 4}, 0.8, "saturn_in_4th", 3),
    Rule("moon_sign_fam", "family", "Moon", {"sign": "*"}, 0.6, "moon_family_style", 1),
    Rule("saturn_sign_fam", "family", "Saturn", {"sign": "*"}, 0.55, "saturn_family_duty", 1),
    # ── wellbeing ──
    Rule("sun_sign_energy", "wellbeing", "Sun", {"sign": "*"}, 0.75, "sun_energy", 2),
    Rule("mars_sign_energy", "wellbeing", "Mars", {"sign": "*"}, 0.85, "mars_energy", 3),
    Rule("moon_phase_energy", "wellbeing", "Moon", {"phase": "*"}, 0.7, "moon_energy_rhythm", 2),
    # ── creativity (fallbacks) ──
    Rule("sun_house_crea", "creativity", "Sun", {"house": 5}, 0.9, "sun_in_5th", 4),
    Rule("venus_house_crea", "creativity", "Venus", {"house": 5}, 0.8, "venus_in_5th", 3),
    Rule("moon_house_crea", "creativity", "Moon", {"house": 5}, 0.8, "moon_in_5th", 3),
    Rule("mercury_house_crea", "creativity", "Mercury", {"house": 5}, 0.7, "mercury_in_5th", 2),
    Rule("sun_sign_crea", "creativity", "Sun", {"sign": "*"}, 0.6, "sun_creativity", 1),
    Rule("venus_sign_crea", "creativity", "Venus", {"sign": "*"}, 0.6, "venus_aesthetics", 1),
    # ── education (fallbacks) ──
    Rule("mercury_house_edu", "education", "Mercury", {"house": 3}, 0.85, "mercury_in_3rd", 3),
    Rule("mercury_house_edu9", "education", "Mercury", {"house": 9}, 0.9, "mercury_in_9th", 4),
    Rule("jupiter_house_edu9", "education", "Jupiter", {"house": 9}, 0.95, "jupiter_in_9th", 4),
    Rule("moon_house_edu4", "education", "Moon", {"house": 9}, 0.8, "moon_in_9th", 2),
    Rule("mercury_sign_edu", "education", "Mercury", {"sign": "*"}, 0.6, "mercury_learning", 1),
    Rule("jupiter_sign_edu", "education", "Jupiter", {"sign": "*"}, 0.6, "jupiter_growth", 1),
    Rule("moon_sign_edu", "education", "Moon", {"sign": "*"}, 0.5, "moon_learning_style", 1),
    # ── network (fallbacks) ──
    Rule("mercury_house_net", "network", "Mercury", {"house": 11}, 0.8, "mercury_in_11th", 3),
    Rule("jupiter_house_net", "network", "Jupiter", {"house": 11}, 0.9, "jupiter_in_11th", 4),
    Rule("sun_house_net", "network", "Sun", {"house": 11}, 0.8, "sun_in_11th", 3),
    Rule("mercury_sign_net", "network", "Mercury", {"sign": "*"}, 0.55, "mercury_network", 1),
    Rule("jupiter_sign_net", "network", "Jupiter", {"sign": "*"}, 0.6, "jupiter_social", 1),
    # ── spirituality ──
    Rule("neptune_sign", "spirituality", "Neptune", {"sign": "*"}, 0.9, "neptune_in_sign", 4),
    Rule("neptune_house", "spirituality", "Neptune", {"house": 12}, 0.95, "neptune_in_12th", 5),
    Rule("moon_house_spir", "spirituality", "Moon", {"house": 12}, 0.85, "moon_in_12th", 4),
    Rule("jupiter_house_spir", "spirituality", "Jupiter", {"house": 12}, 0.85, "jupiter_in_12th", 3),
    # ── karma ──
    Rule("north_node_sign", "karma", "Node", {"sign": "*"}, 0.9, "node_in_sign", 4),
    Rule("saturn_house_karma", "karma", "Saturn", {"house": "*"}, 0.85, "saturn_karma", 3),
    Rule("pluto_house", "karma", "Pluto", {"house": "*"}, 0.9, "pluto_in_house", 4),
    Rule("pluto_sign", "karma", "Pluto", {"sign": "*"}, 0.8, "pluto_in_sign", 3),
]


def evaluate(chart: dict) -> dict[str, list[dict]]:
    """Chart JSON → {domain: [active rule records with matched factor data]}."""
    planets = chart.get("planets", {})
    angles = chart.get("angles", {})
    aspects = chart.get("aspects", [])
    moon_phase = chart.get("moon_phase", "")

    # fast lookup: planet name → position dict
    pos = {}
    for name, p in planets.items():
        d = {"sign": p.get("sign_index"), "house": p.get("house"),
             "retrograde": p.get("retrograde", False), "longitude": p.get("longitude"),
             "degree": p.get("degree_in_sign"), "sign_fa": p.get("sign_fa")}
        pos[name] = d
    for name, p in angles.items():
        pos[name] = {"sign": p.get("sign_index"), "house": None, "retrograde": False,
                     "longitude": p.get("longitude"), "degree": p.get("degree_in_sign"),
                     "sign_fa": p.get("sign_fa")}

    # aspect lookup: (a, b) → aspect dict
    aspect_map = {}
    for a in aspects:
        key = tuple(sorted([a["p1"], a["p2"]]))
        aspect_map[key] = a

    out: dict[str, list[dict]] = {}
    for rule in RULES:
        cond = rule.condition
        matched = True
        detail = None

        if "sign" in cond:
            target = pos.get(rule.factor)
            if target is None:
                matched = False
            elif cond["sign"] == "*":
                detail = target
            elif target["sign"] == cond["sign"]:
                detail = target
            else:
                matched = False
        if matched and "house" in cond:
            target = pos.get(rule.factor)
            if target is None or target.get("house") is None:
                matched = False
            elif cond["house"] == "*":
                detail = target
            elif target["house"] == cond["house"]:
                detail = detail or target
            else:
                matched = False
        if matched and "retrograde" in cond:
            target = pos.get(rule.factor)
            if target is None or target.get("retrograde") != cond["retrograde"]:
                matched = False
            else:
                detail = detail or target
        if matched and "phase" in cond:
            if cond["phase"] != "*" and moon_phase != cond["phase"]:
                matched = False
            else:
                detail = detail or {"phase": moon_phase}
        if matched and "aspect" in cond:
            p1, aname, orb = cond["aspect"]
            key = tuple(sorted([p1, rule.factor]))
            if key not in aspect_map or aspect_map[key]["aspect"] != aname:
                matched = False
            else:
                detail = detail or aspect_map[key]

        if matched:
            out.setdefault(rule.domain, []).append({
                "rule_id": rule.id,
                "factor": rule.factor,
                "weight": rule.weight,
                "interpretation_key": rule.interpretation_key,
                "priority": rule.priority,
                "evidence": rule.evidence,
                "detail": detail,
            })

    # order by priority desc then weight desc
    for dom in out:
        out[dom].sort(key=lambda r: (-r["priority"], -r["weight"]))
    return out


def domain_coverage(chart: dict) -> dict[str, int]:
    """Count of active rules per domain (for QA: no empty sections)."""
    return {d: len(r) for d, r in evaluate(chart).items()}
