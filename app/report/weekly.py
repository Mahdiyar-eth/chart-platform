"""Weekly transit delivery — «نگاهی به آسمان هفته» (audit P0-2).

Deterministic (pyswisseph) transit computation + a reflective Persian text.
NO prediction, NO fortune-telling: the tone is self-knowledge/reflection with an
indirect Islamic framing — «نقشه‌ی موقعیت‌ها، نه سرنوشت؛ تصمیم با عقل و استخاره».
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import jdatetime
from sqlmodel import Session, select

import app.config  # noqa: F401 — load .env FIRST
from app.astrology.transits import upcoming_transits
from app.db import engine
from app.models import Chart, Subscription, WeeklyReflection

log = logging.getLogger("report.weekly")

TARGET_FA = {
    "Sun": "خورشید", "Moon": "ماه", "ASC": "طالع",
    "Venus": "ناهید", "Mars": "مریخ", "Mercury": "تیر",
}

ASPECT_REFLECTION = {
    "هم‌نشینی": "همنشینیِ {planet} با {target}ِ چارت تو — فرصتی برای تمرکز و تأمل در حوزای که این نقطه نمایندگی می‌کند",
    "سه‌گانه": "پیوندِ هماهنگِ {planet} با {target}ِ چارت تو — جریان طبیعی امور، زمان مناسبی برای بهره‌گیری آرام از شرایط",
    "تربیع": "تنشِ سازنده‌ی {planet} با {target}ِ چارت تو — دعوتی به صبر، میانه‌روی و بازبینی انتخاب‌ها",
    "مقابله": "مقابله‌ی {planet} با {target}ِ چارت تو — فرصتی برای یافتن تعادل میان دو خواسته‌ی متفاوت",
    "شش‌گانه": "پیوندِ ظریفِ {planet} با {target}ِ چارت تو — زمانی برای گام‌های کوچک و پایدار",
}

FOOTER = (
    "🕊 این‌ها فقط نقشه‌ی موقعیت‌های آسمانی‌اند، نه تعیینِ سرنوشت. "
    "آسمان بسترِ تأمل است؛ تصمیم نهایی همیشه با عقل، اختیار و توکل خودت است."
)


_MONTHS_FA = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
              "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def _shamsi(d: datetime) -> str:
    """Jalali date (Tehran) with Persian month names."""
    if d.tzinfo:
        j = jdatetime.datetime.fromgregorian(datetime=d)
    else:
        j = jdatetime.datetime.fromgregorian(datetime=d.replace(tzinfo=timezone.utc))
    return f"{j.day} {_MONTHS_FA[j.month - 1]}"


def _week_range() -> str:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=6)
    return f"{_shamsi(now)} تا {_shamsi(end)}"


def build_weekly_reflection(chart_json: dict) -> str:
    """Deterministic reflective weekly text from the next-7-days transits."""
    events = upcoming_transits(chart_json, days=7, step=1)
    lines: list[str] = []
    seen: set = set()
    for e in events[:6]:
        planet = e.get("planet_fa", "")
        target = TARGET_FA.get(e.get("target", ""), e.get("target", ""))
        aspect = e.get("aspect", "")
        template = ASPECT_REFLECTION.get(aspect, "")
        key = (planet, target)  # dedupe same planet→target across aspects
        if planet and target and template and key not in seen:
            seen.add(key)
            lines.append("• " + template.format(planet=planet, target=target) + ".")
        if len(lines) >= 3:
            break
    if not lines:
        lines = [
            "• این هفته حرکت سیارات، گذرِ برجسته‌ای با نقاط اصلی چارت تو نمی‌سازد؛ "
            "زمانِ آرامی برای مرور و تثبیت است.",
        ]

    intro = f"🌌 **نگاهی به آسمان هفته**\n{_week_range()}\n\n"
    body = "\n".join(lines)
    return intro + body + "\n\n" + FOOTER


def _week_start() -> str:
    """'YYYY-MM-DD' of the current week's Saturday (Persian week starts Sat)."""
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=(now.weekday() + 2) % 7)).strftime("%Y-%m-%d")


async def run_weekly_delivery() -> dict:
    """Send this week's reflection to every active subscription; store once per chart/week."""
    from app.bots.handler import send_message

    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        subs = s.exec(
            select(Subscription).where(
                Subscription.active == True,  # noqa: E712
                (Subscription.expires_at == None) | (Subscription.expires_at > now),  # noqa: E711
            )
        ).all()

    week = _week_start()
    sent = failed = 0
    for sub in subs:
        try:
            with Session(engine) as s:
                chart = s.get(Chart, sub.chart_id)
                if not chart:
                    continue
                already = s.exec(
                    select(WeeklyReflection).where(
                        WeeklyReflection.chart_id == sub.chart_id,
                        WeeklyReflection.week_start == week,
                    )
                ).first()
                if already:
                    continue  # already delivered for this chart this week
                text = build_weekly_reflection(chart.chart_json)
                s.add(WeeklyReflection(chart_id=sub.chart_id, week_start=week, text=text))
                prof_id = chart.profile_id  # read BEFORE session closes
                s.commit()

            await send_message(int(sub.chat_id), text, sub.platform)

            # D1: also notify the owning user's browser(s), if push is set up
            try:
                from app.push import send_to_user
                from app.models import BirthProfile
                with Session(engine) as s2:
                    prof = s2.get(BirthProfile, prof_id) if prof_id else None
                    if prof and prof.user_id:
                        send_to_user(
                            prof.user_id,
                            "نگاهی به آسمان هفته",
                            f"گزارش هفتگی چارت «{prof.name or '—'}» آماده است.",
                            "/account",
                            s2,
                        )
            except Exception as e:  # noqa: BLE001 — push must never break delivery
                log.warning("weekly push skipped for sub %s: %s", sub.id, e)

            with Session(engine) as s:
                sub_row = s.get(Subscription, sub.id)
                if sub_row:
                    sub_row.last_sent_at = now
                    s.commit()
            sent += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            log.error("weekly delivery failed for sub %s: %s", sub.id, e)

    log.info("weekly delivery done: sent=%d failed=%d", sent, failed)
    return {"sent": sent, "failed": failed}


if __name__ == "__main__":  # pragma: no cover — manual run
    print(asyncio.run(run_weekly_delivery()))
