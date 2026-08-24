"""MASTER W5 (N1, plan §5) — «امروزِ تو» reflective daily layer.

Five cards, all derived from TODAY'S REAL transits to the user's own chart
(never sun-sign fluff):

| card            | source                                    | cost |
|-----------------|-------------------------------------------|------|
| sky_today       | most active transit today + meaning seed  | 0    |
| reflection_line | one line from that same transit + a question | 0 |
| inner_weather   | real Moon sign/phase today + natal house it lights up | 0 |
| active_area     | which life-area today's transits cluster in + why | 0 |
| relationship_today | Venus/Mars today vs the user's chart   | 0 |
| daily_insight   | ONE cheap LLM sentence (flash) — cached per (chart_id, date) | ~$0.002 |

Hard rules (plan §5): no scoring, no luck, no certainty. Fresh dot = content
changes when (chart_id, date) changes — AC-3 proves it with an injected date.
FREE product: this is the return hook, not revenue.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.astrology.big_three import SIGNS_FA
from app.astrology.transits import _aspect as _aspect_of
from app.astrology.transits import _angular_diff, _lon
from app.report.qa import FORBIDDEN_PATTERNS

# natal target → Persian label used across cards
_TARGET_FA = {"Sun": "خورشیدت", "Moon": "ماهت", "ASC": "طالع‌ت",
              "Venus": "زهره‌ات", "Mars": "مریخت", "Mercury": "عطاردت"}

# transit aspect → short reflective meaning seed (deterministic, honest tone)
_MEANING_SEED = {
    "هم‌نشینی": "یک انرژی با بخشی از وجودت هم‌راستا می‌شود؛ چیزی که معمولاً پخش است امروز متمرکز دیده می‌شود.",
    "سه‌گانه": "جریان امروز روان است؛ کاری که مدت‌ها عقب افتاده بود امروز راحت‌تر جلو می‌رود.",
    "شش‌گانه": "یک فرصت کوچک و واقعی امروز باز است — اگر خودت یک قدم برداری.",
    "تربیع": "یک اصطکاک سالم دیده می‌شود؛ جایی که مقاومت می‌کنی دقیقاً همان‌جا رشد ممکن است.",
    "مقابله": "آینه‌ای روبه‌رویت است؛ واکنشت به دیروز متفاوت از امروز خواهد بود — ببین کدام را انتخاب می‌کنی.",
}

# house → life area label (for active_area card)
_HOUSE_AREA_FA = {
    1: ("هویت و ظاهر", "خودِ تو و نحوهٔ دیده‌شدنت"),
    2: ("پول و دارایی", "امنیت مالی و ارزش‌های شخصی"),
    3: ("گفت‌وگو و یادگیری", "ارتباطات، پیام‌ها، یادگیری روزمره"),
    4: ("خانه و ریشه‌ها", "خانواده، خانه، احساس امنیت"),
    5: ("عشق و خلاقیت", "عشق، فرزند، بازیابی خلاقیت"),
    6: ("کار روزمره و سلامت", "روتین، خدمت، بدن"),
    7: ("شراکت و ازدواج", "رابطهٔ نزدیک و طرف مقابل"),
    8: ("عمق و تحول", "منابع مشترک، عمق احساسی، تحول"),
    9: ("سفر و معنا", "سفر، آموزش، جهان‌بینی"),
    10: ("مسیر شغلی", "کار، جایگاه اجتماعی، آیندهٔ حرفه‌ای"),
    11: ("دوستان و آرزوها", "شبکهٔ اجتماعی، پروژه‌های جمعی، آرزوها"),
    12: ("درون و استراحت", "تنهایی، رؤیا، ترمیم درونی"),
}

_MOON_PHASE_FA = {"New": "ماه نو", "Waxing": "ماه در حال پرشدن",
                  "Full": "ماه کامل", "Waning": "ماه در حال کم‌نور شدن"}


def _today_moon(chart_json: dict, when=None) -> dict:
    """Real Moon position today + which NATAL house it currently lights up."""
    import swisseph as swe
    from datetime import datetime, timezone  # noqa: F401
    from zoneinfo import ZoneInfo
    from app.astrology.engine import jd_from_utc
    now = when or datetime.now(timezone.utc)
    jd = jd_from_utc(now.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)) \
        if now.tzinfo else jd_from_utc(now)
    lon = _lon(swe.MOON, jd)
    s_idx = int(lon // 30)
    # natal house: find which house cusp range contains the Moon's longitude
    houses = chart_json.get("houses") or {}
    natal_house = None
    cusps = []
    for i in range(1, 13):
        c = houses.get(f"h{i}") or houses.get(str(i)) or houses.get(i)
        if isinstance(c, dict):
            c = c.get("longitude")
        if isinstance(c, (int, float)):
            cusps.append((i, float(c)))
    if cusps:
        ordered = sorted(cusps, key=lambda t: t[1])
        for idx, (hnum, clon) in enumerate(ordered):
            nxt = ordered[(idx + 1) % len(ordered)][1]
            if nxt <= clon:  # wrap-around segment
                if lon >= clon or lon < nxt:
                    natal_house = hnum
                    break
            elif clon <= lon < nxt:
                natal_house = hnum
                break
        if natal_house is None and ordered:
            natal_house = ordered[0][0]
    phase_deg = chart_json.get("moon_phase_deg")
    return {
        "sign_fa": SIGNS_FA[s_idx],
        "natal_house": natal_house,
    }


def _venus_mars_today(chart_json: dict, when=None) -> dict | None:
    """Venus/Mars today vs the user's natal points — closest aspect wins."""
    import swisseph as swe
    from datetime import datetime, timezone
    now = when or datetime.now(timezone.utc)
    from app.astrology.engine import jd_from_utc
    jd = swe.julday(now.year, now.month, now.day, now.hour / 24)
    natal = chart_json.get("planets", {})
    angles = chart_json.get("angles", {})
    targets = {"Sun": natal.get("Sun"), "Moon": natal.get("Moon"),
               "ASC": angles.get("ASC"), "Venus": natal.get("Venus"),
               "Mars": natal.get("Mars"), "Mercury": natal.get("Mercury")}
    targets = {k: v for k, v in targets.items() if v}
    best = None
    for body, fa in ((swe.VENUS, "ناهید"), (swe.MARS, "مریخ")):
        lon = _lon(body, jd)
        for tname, t in targets.items():
            diff = _angular_diff(lon, float(t.get("longitude", 0)))
            asp = _aspect_of(diff)
            if not asp:
                continue
            name, orb = asp
            if best is None or orb < best["orb"]:
                best = {"planet_fa": fa, "sign_fa": SIGNS_FA[int(lon // 30)],
                        "target_fa": _TARGET_FA.get(tname, tname),
                        "aspect": name, "orb": orb}
    return best


def build_daily_cards(session, chart, tz_name: str, when_local=None) -> dict:
    """The five cards for /today (N1). All deterministic except daily_insight.
    `when_local` is injectable for tests (AC-3: tomorrow must differ)."""
    from app.today.service import local_today
    day = (when_local.date() if when_local else local_today(tz_name))
    chart_json = chart.chart_json
    # the reference instant for "now" — injected in tests, real now otherwise
    ref_utc = when_local or datetime.now(timezone.utc)

    facts = __import__("app.today.service", fromlist=["today_facts"]).today_facts(chart_json)
    # attach the natal HOUSE + target_fa of each transit for the area card
    planets = chart_json.get("planets", {})
    angles = chart_json.get("angles", {})
    _tfa = {"Sun": "خورشیدت", "Moon": "ماهت", "ASC": "طالع‌ت"}
    for f in facts:
        t = f.get("target", "")
        src = planets.get(t) or angles.get(t) or {}
        f["house"] = src.get("house")
        f.setdefault("target_fa", _tfa.get(t, t))

    # ── card 1: sky_today ──
    top = facts[0] if facts else None
    sky_today = None
    if top:
        meaning = _MEANING_SEED.get(top["aspect_fa"],
                                    "آسمان امروز نقطه‌ای از چارتت را روشن می‌کند.")
        t_fa = _TARGET_FA.get(top.get("target", ""), top.get("target_fa") or top.get("target", ""))
        sky_today = {
            **top,
            "meaning": f"«{top['planet_fa']}» امروز با {t_fa} {top['aspect_fa']} است — {meaning}",
        }

    # ── card 2: reflection_line (from the SAME transit — no invention) ──
    reflection_line = None
    if top:
        q_map = {"مشتری": "کدام فرصت امروز جلوی چشم توست که ندیده‌ای؟",
                 "زحل": "کدام تعهد امروز یک قدم جلوتر می‌رود؟",
                 "اورانوس": "چه چیزی امروز برای تکراری شدن فریاد می‌زند؟",
                 "نپتون": "کدام رؤیا را مدت‌هاست به خودت نمی‌گویی؟",
                 "پلوتو": "چه چیزی آمادهٔ رها شدن است؟",
                 "مریخ": "کدام اقدام کوچک امروز انرژی می‌خواهد؟",
                 "ناهید": "چه چیزی امروز ارزش لذت بردن دارد؟"}
        reflection_line = {
            "line": _MEANING_SEED.get(top["aspect_fa"], "امروز یک نقطهٔ روشن در چارتت فعال است."),
            "question": q_map.get(top["planet_fa"], "امروز چه چیزی بیشتر از همیشه توجهت را می‌خواهد؟"),
        }
    else:
        reflection_line = {"line": "آسمان امروز آرام است.", "question": "چه چیزی این هفته بی‌صدا منتظر توجه توست؟"}

    # ── card 3: inner_weather (real Moon) ──
    moon_today = _today_moon(chart_json, when=ref_utc)
    area = (_HOUSE_AREA_FA.get(moon_today["natal_house"], (None, None))[0]
            if moon_today["natal_house"] else None)
    inner_weather = {
        "sign_fa": moon_today["sign_fa"],
        "phase_fa": _MOON_PHASE_FA.get(chart_json.get("moon_phase", ""), ""),
        "area_fa": area,
        "text": (f"ماه امروز در {moon_today['sign_fa']} است"
                 + (f" و خانهٔ {moon_today['natal_house']} چارتت را روشن می‌کند — حوزهٔ {area}"
                    if moon_today["natal_house"] and area else "")
                 + "."),
    }

    # ── card 4: active_area (cluster of today's transits) ──
    active_area = None
    if len(facts) >= 2:
        # the most-repeated target_fa across today's transits marks the loud
        # area: Sun/Moon/ASC hits = identity/emotions/outer-life respectively.
        counts: dict[str, int] = {}
        for f in facts[:3]:
            tfa = f.get("target_fa") or ""
            if tfa:
                counts[tfa] = counts.get(tfa, 0) + 1
        if counts:
            t_top = max(counts, key=lambda k: counts[k])
            area_map = {"خورشیدت": ("هویت و مسیر", "چند گذر همزمان روی خورشیدت نشسته‌اند — هویت و مسیر امروز پررنگ است"),
                        "ماهت": ("درون و احساس", "گذرها روی ماهت فعال‌اند — دنیای احساس امروز بلندترین صداست"),
                        "طالع‌ت": ("ظاهر و برخورد", "گذرهای امروز روی طالعت — نحوهٔ دیده‌شدنت پررنگ است")}
            title, why = area_map.get(t_top, ("امروز", "فعالیت امروز متمرکز است"))
            active_area = {"target": t_top, "title": title, "why": why}
    if active_area is None and moon_today.get("natal_house"):
        h = moon_today["natal_house"]
        title, why = _HOUSE_AREA_FA.get(h, (f"خانهٔ {h}", "فعالیت امروز اینجا متمرکز است"))
        active_area = {"house": h, "title": title, "why": why}

    # ── card 5: relationship_today (real Venus/Mars) ──
    vm = _venus_mars_today(chart_json, when=ref_utc)
    relationship_today = None
    if vm:
        relationship_today = {
            **vm,
            "text": (f"{vm['planet_fa']} امروز در {vm['sign_fa']}، {vm['aspect']} با {vm['target_fa']} — "
                     + _MEANING_SEED.get(vm["aspect"], "نگاه امروزی‌ات به نزدیک‌ها کمی تازه است.")),
        }

    return {
        "date": day.isoformat(),
        "sky_today": sky_today,
        "reflection_line": reflection_line,
        "inner_weather": inner_weather,
        "active_area": active_area,
        "relationship_today": relationship_today,
        "facts_count": len(facts),
    }


# ─────────────────────── LLM insight with DAILY cache ───────────────────────

INSIGHT_TEMPLATE = """تو مشاور تأملی هستی. فقط بر پایهٔ این گذر واقعی امروز نسبت به چارت کاربر:
{transit_block}

یک جملهٔ کوتاه (حداکثر ۳۵ کلمه) بنویس که:
- به همین گذر اشاره کند (سیاره و نوع زاویه)،
- لحن تأملی و صادق باشد، نه پیشگویی؛ نه «فال»، نه «شانس»، نه وعده.
- پاسخ فقط متن ساده باشد؛ بدون JSON و بدون مارک‌داون."""


async def daily_insight_async(cards: dict) -> str | None:
    """One cheap flash call → one reflective sentence. Brand-gated."""
    sky = cards.get("sky_today")
    if not sky:
        return None
    block = (f"- {sky['planet_fa']} امروز در {sky['sign_fa']}، {sky['aspect_fa']} "
             f"با {sky.get('target_fa', sky.get('target', ''))} (اورب {sky.get('orb')})")
    prompt = INSIGHT_TEMPLATE.format(transit_block=block)
    try:
        from app.core.llm import build_chat_router
        router = build_chat_router()
        res = await router.complete(prompt, max_tokens=160, temperature=0.7)
        if not res.ok:
            return None
        text = (res.text or "").strip().strip('"')
        flat = text.replace("\u200c", "")
        if any(__import__("re").search(p, flat) for p in FORBIDDEN_PATTERNS):
            return None
        return text[:400] or None
    except Exception:  # noqa: BLE001 — the free layer must never break
        return None


async def get_daily_layer(session, chart, tz_name: str) -> dict:
    """Full N1 payload for /today: 5 cards + LLM insight cached per (chart,date).
    Cache key: `today:{chart_id}:{YYYY-MM-DD}` — tomorrow is a NEW key (AC-3)."""
    import json as _json
    import os
    cards = build_daily_cards(session, chart, tz_name)
    key_date = cards["date"]
    payload = dict(cards)
    payload["insight"] = None
    cache_key = f"today:{chart.id}:{key_date}"
    try:
        import redis.asyncio as redis_async
        r = redis_async.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
                                 decode_responses=True)
        raw = await r.get(cache_key)
        await r.aclose()
        if raw:
            payload["insight"] = raw or None
            payload["cached"] = True
            return payload
    except Exception:  # noqa: BLE001
        pass
    insight = await daily_insight_async(cards)
    if insight:
        payload["insight"] = insight
        try:
            import redis.asyncio as redis_async
            r = redis_async.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
                                     decode_responses=True)
            await r.set(cache_key, insight, ex=2 * 86400)  # expire 48h later
            await r.aclose()
        except Exception:  # noqa: BLE001
            pass
    return payload
