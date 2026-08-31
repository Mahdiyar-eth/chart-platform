"""MASTER W6 (N2) — Solar Return engine («چارت سالیانه»).

Finds the precise UTC moment the transiting Sun returns to its natal
longitude (bisection to <1/60 degree ⇒ well under 1 minute of time), then
recomputes the full chart for THAT moment at the user's CURRENT location
(not birth place — plan §5 key point).

Deterministic only. The narrative layer (LLM) lives in solar_service.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import swisseph as swe

from app.astrology.engine import (SIGNS_FA, compute_chart, jd_from_utc,
                                  sign_of)
from app.astrology.engine import BirthData

swe.set_ephe_path("ephe")
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)


def _sun_lon(jd: float) -> float:
    return swe.calc_ut(jd, swe.SUN)[0][0]


@dataclass
class SolarReturn:
    moment_utc: datetime          # exact Sun-return instant
    natal_sun_lon: float
    error_arcmin: float           # |returned sun − natal sun| in arc-minutes
    chart_json: dict              # full SR chart at the current location
    age_years: int


def _angular_gap(a: float, b: float) -> float:
    d = (a - b) % 360
    return d - 360 if d > 180 else d


def find_solar_return(natal_sun_lon: float, after_utc: datetime,
                      lat: float, lon: float, tz_name: str,
                      zodiac: str = "tropical") -> SolarReturn:
    """Bisection on the Sun's longitude gap → sub-arcminute precision."""
    # rough first guess: natal moment of this year ≈ birthday ± search window.
    # The Sun needs ~365.24d; start 20 days before the anniversary guess and
    # bracket until the gap crosses zero.
    t0 = after_utc - timedelta(days=30)
    jd0 = jd_from_utc(t0.replace(tzinfo=None))
    gap0 = _angular_gap(_sun_lon(jd0), natal_sun_lon)
    step = timedelta(days=2)
    t1 = t0
    gap1 = gap0
    for _ in range(60):  # up to ~4 months of scanning — always enough
        t1 = t1 + step
        jd1 = jd_from_utc(t1.replace(tzinfo=None))
        gap1 = _angular_gap(_sun_lon(jd1), natal_sun_lon)
        if gap0 < 0 <= gap1 or (gap0 > 0 and gap1 < 0 and abs(gap1) < 5):
            break
        gap0, t0 = gap1, t1
    lo, hi = t0, t1
    glo, ghi = gap0, gap1
    # bisection — ~25 iterations ⇒ microseconds-level convergence
    for _ in range(28):
        mid = lo + (hi - lo) / 2
        jdm = jd_from_utc(mid.replace(tzinfo=None))
        gm = _angular_gap(_sun_lon(jdm), natal_sun_lon)
        if (glo <= 0 <= ghi and gm < 0) or (glo >= 0 >= ghi and gm > 0):
            lo, glo = mid, gm
        else:
            hi, ghi = mid, gm
        if (hi - lo).total_seconds() < 0.5:  # half-second stop
            break
    moment = lo + (hi - lo) / 2
    jdm = jd_from_utc(moment.replace(tzinfo=None))
    err_deg = abs(_sun_lon(jdm) - natal_sun_lon) % 360
    err_deg = min(err_deg, 360 - err_deg)
    sr_chart = compute_chart(
        BirthData(lat=lat, lon=lon,
                  year=moment.year, month=moment.month, day=moment.day,
                  hour=moment.hour, minute=moment.minute,
                  time_known=True, jalali=False, tz_name=tz_name),
        config={"zodiac": zodiac},
    )
    return SolarReturn(
        moment_utc=moment.replace(tzinfo=timezone.utc),
        natal_sun_lon=natal_sun_lon,
        error_arcmin=round(err_deg * 60, 3),
        chart_json=sr_chart.chart_json,
        age_years=0,
    )


def solar_return_for(natal_chart: dict, current_lat: float,
                     current_lon: float, tz_name: str,
                     when_local=None, zodiac: str = "tropical") -> SolarReturn:
    """SR chart for the CURRENT solar year (this birthday → next)."""
    from zoneinfo import ZoneInfo
    planets = natal_chart.get("planets", {})
    sun_lon = float(planets["Sun"]["longitude"])
    tz = ZoneInfo(tz_name)
    now_local = when_local or datetime.now(tz)
    # candidate anniversaries in local civil years around now
    year = now_local.year
    candidates = []
    for y in (year - 1, year):
        guess = datetime(y, now_local.month, min(now_local.day, 28),
                         12, 0, tzinfo=tz).astimezone(ZoneInfo("UTC"))
        candidates.append(guess.replace(tzinfo=None))
    # Each find_solar_return is ~88 swe.calc_ut calls plus a full compute_chart.
    # There used to be a first pass over the same candidates building a `best`
    # that was never read again (it even carried an `if best is None or True:
    # pass`), so every call did the work twice — and a paid page view calls
    # this function twice, for the teaser and the content. Compute once.
    now_naive = now_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    sr_active = None
    results = [find_solar_return(sun_lon, cand, current_lat, current_lon,
                                 tz_name, zodiac)
               for cand in candidates]
    past = [r for r in results if r.moment_utc.replace(tzinfo=None) <= now_naive]
    if past:
        sr_active = max(past, key=lambda r: r.moment_utc)
    elif results:
        sr_active = min(results, key=lambda r: abs(
            (r.moment_utc.replace(tzinfo=None) - now_naive).days))
    assert sr_active is not None
    sr_active.age_years = now_local.year - sr_active.moment_utc.year
    return sr_active


# ───────────────────────── deterministic sections ─────────────────────────

_SR_HOUSE_AREA_FA = {
    1: ("هویت", "سال تو، سال خودت: مسائل شخصی و نحوهٔ دیده‌شدن در مرکز است."),
    2: ("پول و دارایی", "تم سال روی امنیت مالی و ساختن منابع پایدار روشن می‌شود."),
    3: ("گفت‌وگو و یادگیری", "سالِ ارتباط: آموزش، سفرهای کوتاه و شبکهٔ نزدیک پررنگ است."),
    4: ("خانه و خانواده", "ریشه‌ها محوراند: خانه، خانواده و احساس امنیت بازتعریف می‌شود."),
    5: ("عشق و خلاقیت", "سال عشق، لذت و آفرینش؛ چیزی که دوستش داری جدی می‌شود."),
    6: ("کار و سلامت", "روتین، خدمت و بدن: کیفیت روزمره تعیین‌کنندهٔ سال توست."),
    7: ("شراکت و ازدواج", "«ما» محور سال است: رابطه‌ها و شراکت‌ها آزمایش و تثبیت می‌شوند."),
    8: ("عمق و تحول", "سال تحول: منابع مشترک و پیوندهای عمیق دگرگون می‌شوند."),
    9: ("سفر و معنا", "افق باز می‌شود: سفر، آموزش و جهان‌بینی گسترش می‌یابد."),
    10: ("مسیر شغلی", "سالِ کارنامه: جایگاه اجتماعی و اهداف حرفه‌ای زیر نورافکن است."),
    11: ("دوستان و آرزوها", "آرزوهای بزرگ و هم‌مسیرها؛ پروژه‌های جمعی شکل می‌گیرند."),
    12: ("درون و ترمیم", "سالِ درون: استراحت، جمع‌بندی و پاک‌سازی پیش از چرخهٔ تازه."),
}


def sr_sections(sr: SolarReturn, natal_chart: dict) -> dict:
    """Deterministic content: mood line, dominant house, top-5 dated transits,
    main theme, seasonal reflection question."""
    cj = sr.chart_json
    # dominant house = SR ASC sign's natural house proxy: use SR ASC as house 1;
    # the strongest planet = closest to an angle gets highlighted via houses.
    planets_in_house: dict[int, list[str]] = {}
    for name, p in cj.get("planets", {}).items():
        h = p.get("house")
        if h:
            planets_in_house.setdefault(h, []).append(name)
    # house with most planets wins (ties → lower number)
    dom_house = max(planets_in_house, key=lambda k: (len(planets_in_house[k]), -k)) \
        if planets_in_house else 1
    area_title, area_text = _SR_HOUSE_AREA_FA.get(
        dom_house, ("سال نو", "چرخهٔ تازه‌ای شروع شده است."))

    # mood from Moon phase at the SR moment
    phase = cj.get("moon_phase", "")
    mood_map = {"New": "شروع تازه — انرژی کاشتن، نه برداشت.",
                "Waxing": "سازندگی — سالِ ساختن و پرکردن ظرف‌های خالی.",
                "Full": "اوج‌گیری — آنچه کاشته شد این سال دیده می‌شود.",
                "Waning": "جمع‌بندی — سالِ سبک‌کردن و انتخاب دوباره."}
    mood = mood_map.get(phase, "چرخه‌ای که تازه بسته شده و دوباره باز می‌شود.")

    # top-5 upcoming transits WITHIN the solar year, with dates
    from app.astrology.transits import upcoming_transits
    evs = upcoming_transits(cj, days=360)[:5]
    transits = [{
        "date": e["start"],
        "headline": f"{e['planet_fa']} در {e['sign_fa'].replace('برج ', '')} {e['aspect']} با "
                    f"{'خورشید سال' if e['target'] == 'Sun' else ('ماه سال' if e['target'] == 'Moon' else 'طالع سال')}",
    } for e in evs]

    theme = (f"خورشید سال تو در خانهٔ {dom_house} نشسته — {area_text}")
    q_seasonal = {
        1: "این سال می‌خواهی «چه کسی» باشی؟",
        2: "چه چیزی برایت ارزش ساختن دارد؟",
        3: "با چه کسی/چه چیزی باید بیشتر حرف بزنی؟",
        4: "کجا «خانه» حس می‌کنی؟",
        5: "به چه چیزی دوباره جان می‌دهی؟",
        6: "کدام عادت روزمره را بازسازی می‌کنی؟",
        7: "با کدام قولِ مشترک کنار می‌آیی؟",
        8: "چه چیزی آمادهٔ دگرگونی است؟",
        9: "کدام افق را جدی می‌گیری؟",
        10: "چه اثری از تو بماند؟",
        11: "با کدام جمع می‌سازی؟",
        12: "چه چیزی را به پایان برده‌ای تا سبک شوی؟",
    }.get(dom_house, "این سال برای تو چه تمی دارد؟")

    return {
        "moment_utc": sr.moment_utc.strftime("%Y-%m-%d %H:%M"),
        "precision_arcmin": sr.error_arcmin,
        "dominant_house": dom_house,
        "area_title": area_title,
        "mood": mood,
        "theme": theme,
        "transits": transits,
        "seasonal_question": q_seasonal,
        "sun_sign_fa": SIGNS_FA[sign_of(float(cj["planets"]["Sun"]["longitude"]))],
    }
