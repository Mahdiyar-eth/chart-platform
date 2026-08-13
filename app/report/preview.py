"""Free insights preview (plan v3.0 §8) — deterministic rule-engine teaser.

3-5 short insights derived from the ACTIVE RULES (no LLM, no cost, instant).
Powers POST /api/charts/{id}/preview and the chart page "اینسایتهای رایگان".
"""
from __future__ import annotations

from app.astrology.big_three import big_three
from app.astrology.svg_wheel import PLANET_FA
from app.report.rules import DOMAINS, evaluate

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


def _insight_text(domain: str, rec: dict) -> str:
    """Human-readable one-liner from the active rule record (deterministic)."""
    detail = rec.get("detail") or {}
    factor = PLANET_FA.get(rec.get("factor", ""), rec.get("factor", ""))
    sign = detail.get("sign_fa") or ""
    house = detail.get("house")
    aspect = detail.get("aspect")
    if aspect and isinstance(aspect, str):
        return f"{factor} — جنبهی «{aspect}» با عامل مهمی در «{_TITLE.get(domain, domain)}» فعال است."
    if sign and house:
        return f"{factor} در برج {sign} و خانهی {house} — عامل اصلی حوزهی «{_TITLE.get(domain, domain)}»."
    if sign:
        return f"{factor} در برج {sign} — تأثیرگذار بر حوزهی «{_TITLE.get(domain, domain)}»."
    return f"عامل «{factor}» در حوزهی «{_TITLE.get(domain, domain)}» فعال است."


def free_insights(chart: dict, limit: int = 5) -> dict:
    """Top N domains by active-rule count (priority tiebreak) → 1-line insight each."""
    active = evaluate(chart)
    ranked = sorted(
        active.items(),
        key=lambda kv: (len(kv[1]) if kv[1] else 0,
                        -_PRIORITY.index(kv[0]) if kv[0] in _PRIORITY else 99),
        reverse=True,
    )
    bt = big_three(chart)
    teaser = {
        "sun": bt.get("Sun", {}).get("sign_fa", ""),
        "moon": bt.get("Moon", {}).get("sign_fa", ""),
        "asc": bt.get("ASC", {}).get("sign_fa", ""),
    }
    out = []
    for domain, rules in ranked:
        if not rules or len(out) >= limit:
            continue
        rec = rules[0]
        out.append({
            "domain": domain,
            "domain_title": _TITLE.get(domain, domain),
            "rule_id": rec.get("rule_id", ""),
            "factor": rec.get("factor", ""),
            "insight": _insight_text(domain, rec),
        })
    return {
        "big_three": teaser,
        "insights": out,
        "full_report_teaser": "گزارش کامل، هر ۱۳ حوزهی زندگی را با تحلیل عمیق و راهکارهای عملی پوشش میدهد.",
    }


# ─── LLM enrichment (plan: attractive plain-language insights, cheap LLM) ───

ENRICH_TEMPLATE = """تو نویسندهی محتوای ساده و جذاب برای یک سایت آسترولوژی فارسی هستی.

اینها واقعیتهای محاسبهشدهی چارت تولد یک کاربر است (به زبان تخصصی — هر خط یک واقعیت):
{facts_block}

هر واقعیت را به زبان ساده و جذاب بازنویسی کن که یک کاربر عادی (بدون دانش آسترولوژی) بفهمد «این برای زندگی من یعنی چه».

# قوانین
- هر مورد ۲ تا ۳ جملهی روان فارسی.
- وقتی نام سیاره/برج را میآوری، معنای سادهاش را هم بگو (مثلاً: «مشتری، سیارهی رشد و برکت»).
- غیرپیشگویانه: هرگز نگو «حتماً/قطعاً اتفاق میافتد». از «به احتمال»، «گرایش»، «مسیر» استفاده کن.
- دلسوز و غیرقضاوتی؛ بدون ادعای پزشکی یا مالی قطعی.
- ترتیب را دقیقاً حفظ کن (متن اول برای واقعیت اول، و...).
- پاسخ فقط JSON معتبر — بدون مقدمه و بدون مارکداون.

# خروجی
{{"insights": ["متن ۱", "متن ۲", "متن ۳", "متن ۴", "متن ۵"]}}
"""


async def enrich_insights_async(chart: dict, insights: dict) -> dict | None:
    """Rewrite the deterministic one-liners as plain-language insights via the
    cheap preview router (deepseek-flash flat-subscription). Returns a new
    insights dict with enriched text, or None on failure (caller keeps the
    deterministic originals)."""
    facts = [i["insight"] for i in insights.get("insights", [])]
    if not facts:
        return None
    from app.core.llm import build_router
    router = build_router("preview")
    prompt = ENRICH_TEMPLATE.format(facts_block="\n".join(f"- {f}" for f in facts))
    res = await router.complete(prompt, max_tokens=900, temperature=0.6, json_mode=True)
    if not res.ok:
        return None
    try:
        data = __import__("json").loads(res.text)
        new_texts = data.get("insights") or []
        if not isinstance(new_texts, list) or not new_texts:
            return None
        out = dict(insights)
        out["insights"] = [
            {**itm, "insight": new_texts[i]} if i < len(new_texts) else itm
            for i, itm in enumerate(insights.get("insights", []))
        ]
        out["enriched"] = True
        return out
    except Exception:
        return None
