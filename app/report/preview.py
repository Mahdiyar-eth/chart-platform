"""Free preview (MASTER W2 — plan §3.3) — the chart page must ANSWER the user.

Old version: 5 one-liners from the rule engine; `personal_question` and
`focus_areas` (asked in the form!) were ignored. New free output:

1. Big Three + wheel (chart page, already there)
2. **answer_preview** — a short real answer to THE question the user asked
   (one cheap LLM call, deepseek-flash via build_router("preview"))
3. **patterns** — 3 dominant chart patterns, each with astrological EVIDENCE
   («ماه در عقرب در خانهٔ ۸ ⇒ …»)
4. **next_transit** — 1 important upcoming transit with a date (teaser for
   the «۱۲ ماه آیندهٔ من» product)
5. **element_summary** — element/modality distribution + one interpretive line
6. **full_report_teaser** — what the full report adds, with a real example

COST CONTROL (plan §9): the LLM call is cached PERMANENTLY on chart_id in
Redis (`freepreview:{chart_id}`, no TTL). Second load of the same chart =
zero LLM calls (AC-1). Deterministic fallback keeps everything working with
ENRICH_INSIGHTS=0 / Redis down / LLM down.
"""
from __future__ import annotations

import re

from app.astrology.big_three import big_three
from app.astrology.svg_wheel import PLANET_FA
from app.report.qa import FORBIDDEN_PATTERNS
from app.report.rules import evaluate

_TITLE = {
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

_PRIORITY = ["identity", "mind", "emotions", "career", "money"]

_ELEMENT_LINE_FA = {
    "Fire": "آتش (شور، شروع، بیان)",
    "Earth": "خاک (ثبات، عمل، ساختن)",
    "Air": "هوا (اندیشه، گفت‌وگو، پیوند)",
    "Water": "آب (احساس، شهود، عمق)",
}

_MODALITY_LINE_FA = {
    "Cardinal": "کاردینال (آغازگر)",
    "Fixed": "ثابت (پایدار)",
    "Mutable": "تغییرپذیر (منعطف)",
}


# ────────────────────────── deterministic core ──────────────────────────

def _factor_label(chart: dict, rec: dict) -> str:
    """«ماه در عقرب در خانهٔ ۸» — always pull sign from the CHART (F-32 rule)."""
    planets = chart.get("planets", {})
    angles = chart.get("angles", {})
    src = planets.get(rec["factor"]) or angles.get(rec["factor"]) or {}
    fa = str(PLANET_FA.get(rec["factor"]) or rec["factor"] or "")
    parts: list[str] = [fa]
    if src.get("sign_fa"):
        parts.append(f"در {src['sign_fa']}")
    d = rec.get("detail") or {}
    house = d.get("house") or src.get("house")
    if house:
        parts.append(f"در خانهٔ {house}")
    return " ".join(parts)


def _pattern_text(domain: str, rec: dict) -> str:
    """One-line dominant pattern WITH evidence prefix (deterministic)."""
    detail = rec.get("detail") or {}
    factor = str(PLANET_FA.get(rec.get("factor", "")) or rec.get("factor") or "")
    sign = detail.get("sign_fa") or ""
    house = detail.get("house")
    aspect = detail.get("aspect")
    title = _TITLE.get(domain, domain)
    if aspect and isinstance(aspect, str):
        return f"{factor} — جنبهٔ «{aspect}» با نقطهٔ مهمی از چارت؛ پررنگ در حوزهٔ {title}."
    if sign and house:
        return f"{factor} در برج {sign} و خانهٔ {house} — ستون اصلی حوزهٔ {title}."
    if sign:
        return f"{factor} در برج {sign} — تأثیرگذار بر حوزهٔ {title}."
    return f"عامل «{factor}» فعال در حوزهٔ {title}."


def _top_patterns(chart: dict, n: int = 3) -> list[dict]:
    """Top-N domains by active-rule count → pattern line + evidence label."""
    active = evaluate(chart)
    ranked = sorted(
        active.items(),
        key=lambda kv: (len(kv[1]) if kv[1] else 0,
                        -_PRIORITY.index(kv[0]) if kv[0] in _PRIORITY else 99),
        reverse=True,
    )
    out: list[dict] = []
    for domain, rules in ranked:
        if not rules or len(out) >= n:
            continue
        rec = rules[0]
        out.append({
            "domain": domain,
            "domain_title": _TITLE.get(domain, domain),
            "rule_id": rec.get("rule_id", ""),
            "factor": rec.get("factor", ""),
            "evidence": _factor_label(chart, rec),
            "insight": _pattern_text(domain, rec),
        })
    return out


def _element_summary(chart: dict) -> dict:
    counts: dict = chart.get("elements") or {}
    modalities: dict = chart.get("modalities") or {}
    if not counts:
        return {}
    top_el = max(counts, key=lambda k: counts[k])
    top_mo = max(modalities, key=lambda k: modalities[k]) if modalities else ""
    total = sum(counts.values()) or 1
    line = (f"چیدمان سیاره‌های تو بیشتر {_ELEMENT_LINE_FA.get(top_el, top_el)} است "
            f"({counts[top_el]} از {total})")
    if top_mo:
        line += f" و رویکرد غالب‌ات {_MODALITY_LINE_FA.get(top_mo, top_mo)}"
    line += " — یعنی انرژی پیش‌فرضی که با آن به زندگی واکنش نشان می‌دهی."
    return {
        "elements": counts,
        "elements_fa": {k: _ELEMENT_LINE_FA.get(k, k) for k in counts},
        "modalities": modalities,
        "dominant_element": top_el,
        "line": line,
    }


def _next_transit(chart: dict) -> dict | None:
    """The single nearest upcoming slow-planet transit with a start date."""
    try:
        from app.astrology.transits import upcoming_transits
        events = upcoming_transits(chart, days=90)
        if not events:
            return None
        e = events[0]
        target = {"Sun": "خورشیدت", "Moon": "ماهت", "ASC": "طالع‌ت",
                  "Venus": "زهره‌ات", "Mars": "مریخت", "Mercury": "عطاردت"}.get(
                      e.get("target"), e.get("target", ""))
        aspect_fa = str(e["aspect"])  # transits.py returns Persian names already
        sign_fa = str(e.get("sign_fa", "")).replace("برج ", "")
        return {
            "date": e.get("start", ""),
            "planet_fa": e.get("planet_fa", ""),
            "sign_fa": sign_fa,
            "target_fa": target,
            "aspect_fa": aspect_fa,
            "headline": f"از حدود {e.get('start', '')}: {e.get('planet_fa', '')} در {sign_fa} {aspect_fa} با {target}",
        }
    except Exception:  # noqa: BLE001 — teaser must never break the preview
        return None


# ────────────────────────── LLM answer layer ──────────────────────────

ANSWER_TEMPLATE = """تو مشاور خودشناسی هستی که بر پایهٔ چارت تولد واقعی کاربر حرف می‌زند.

کاربر هنگام ساختن چارتش این سؤال شخصی نوشته است:
«{question}»

حوزه‌هایی که برایش مهم بوده‌اند: {focus_areas}

## عوامل واقعی چارت (تنها منبع مجاز — هرگز چیزی اختراع نکن)
{factors_block}

## وظیفه
۱. به همین سؤال، یک پاسخ کوتاه (۴-۶ جمله) بده.
۲. سه الگوی غالب چارت را در قالب همان ساختار زیر بنویس.

# قوانین طلایی
- هر ادعا فقط با شاهد نجومی از فهرست بالا (سیاره/برج/خانه/جنبه).
- هیچ قطعیتی دربارهٔ آینده: نه «حتماً»، نه «مقدر»، نه پیشگویی، نه پزشکی.
- لحن تأملی، صادق و دلسوز — آینهٔ خودشناسی، نه فال.
- پاسخ فقط JSON معتبر — بدون مقدمه و بدون مارک‌داون.

## خروجی JSON
{{
  "question_answer": "پاسخ ۴-۶ جمله‌ای به سؤال کاربر، با اشاره به حداقل یک شاهد نجومی",
  "patterns": [
    {{"title": "نام کوتاه الگو", "text": "۲-۳ جمله دربارهٔ الگو", "evidence": "همان شاهد نجومی، مثل: ماه در عقرب در خانهٔ ۸"}}
  ]
}}
دقیقاً ۳ الگو بنویس."""


def _factors_block_for_free(chart: dict, active_domains: list[str]) -> str:
    """Compact evidence block across the given domains (+ big three fallback)."""
    lines: list[str] = []
    seen: set[str] = set()
    for key, fa in (("Sun", "Sun"), ("Moon", "Moon"), ("ASC", "ASC")):
        src = (chart.get("planets") or chart.get("angles") or {}).get(key) or {}
        if key == "ASC":
            src = (chart.get("angles") or {}).get("ASC") or {}
        if src.get("sign_en") or src.get("sign_fa"):
            label = {"Sun": "خورشید", "Moon": "ماه", "ASC": "طالع"}[key]
            sign = src.get("sign_fa") or ""
            lines.append(f"- {label}: برج {sign}")
            seen.add(key)
    from app.report.prompt_builder import factors_block as _fb
    active = evaluate(chart)
    for dom in active_domains[:5]:
        block = _fb(chart, dom, active.get(dom, []))
        for ln in block.splitlines():
            s = ln.strip()
            if s.startswith("- ") and s not in lines:
                lines.append(s)
    return "\n".join(lines[:18])


def _qa_ok(text: str) -> bool:
    """Same brand gate as paid reports: no divination/certainty claims."""
    flat = text.replace("\u200c", "")
    return not any(re.search(p, flat) for p in FORBIDDEN_PATTERNS)


async def enrich_free_preview_async(chart: dict, profile: dict) -> dict | None:
    """One cheap LLM call → answer to THE user's question + 3 patterns.
    Returns None on failure (caller keeps deterministic baseline)."""
    question = (profile or {}).get("personal_question") or ""
    focus = (profile or {}).get("focus_areas") or []
    patterns = profile.get("_patterns") or []
    # No personal question → nothing to answer; keep the deterministic preview.
    if not question.strip():
        return None
    domains = [p["domain"] for p in patterns] or list(_PRIORITY)
    factors_block = _factors_block_for_free(chart, domains)
    prompt = ANSWER_TEMPLATE.format(
        question=question.strip()[:500],
        focus_areas="، ".join(focus) or "—",
        factors_block=factors_block,
    )
    from app.core.llm import build_router
    router = build_router("preview")
    res = await router.complete(prompt, max_tokens=900, temperature=0.5,
                                json_mode=True)
    if not res.ok:
        return None
    import json as _json
    try:
        data = _json.loads(res.text)
    except Exception:  # noqa: BLE001
        return None
    answer = str(data.get("question_answer") or "").strip()
    pats = data.get("patterns") or []
    if len(answer) < 60 or not _qa_ok(answer):
        return None
    clean_pats = []
    for p in pats[:3]:
        if isinstance(p, dict) and str(p.get("text", "")).strip() \
                and _qa_ok(str(p.get("text", ""))):
            clean_pats.append({
                "title": str(p.get("title", "")).strip()[:80],
                "text": str(p.get("text", "")).strip(),
                "evidence": str(p.get("evidence", "")).strip() or "",
            })
    return {"question_answer": answer, "llm_patterns": clean_pats}


# ────────────────────────── public entry ──────────────────────────

def free_insights(chart: dict, limit: int = 3) -> dict:
    """Deterministic baseline (always available): 3 patterns with evidence,
    next transit teaser, element summary, honest full-report teaser."""
    bt = big_three(chart)
    teaser = {
        "sun": bt.get("Sun", {}).get("sign_fa", ""),
        "moon": bt.get("Moon", {}).get("sign_fa", ""),
        "asc": bt.get("ASC", {}).get("sign_fa", ""),
    }
    out = {
        "big_three": teaser,
        "insights": [],
        "patterns": _top_patterns(chart, limit),
        "next_transit": _next_transit(chart),
        "element_summary": _element_summary(chart),
        "full_report_teaser": (
            "گزارش کامل، هر ۱۳ حوزهٔ زندگی را جداگانه باز می‌کند: برای هر حوزه "
            "تحلیل عمیق با شاهد نجومی، نقاط قوت و چالش و یک پیشنهاد عملی — "
            "مثلاً برای حوزهٔ شغل: «کدام ساختار انگیزشی‌ات به کدام مسیر می‌خورد و چرا»."
        ),
    }
    # back-compat: old template iterated `insights` — map patterns into it too
    out["insights"] = [
        {"domain": p["domain"], "domain_title": p["domain_title"],
         "rule_id": p["rule_id"], "factor": p["factor"], "insight": p["insight"]}
        for p in out["patterns"]
    ]
    return out
