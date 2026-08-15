"""ZAYCHE P4/E — Today: transit facts, daily reflection, streak.

Deterministic (no LLM): sky fact comes from compute_transits, the
reflection question is generated from the top transit, and the streak is
derived from stored reflections in the USER's local timezone.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.astrology.transits import compute_transits
from app.models import Chart, DailyReflection, BirthProfile

DEFAULT_TZ = "Asia/Tehran"

# Persian month names for the today page
MONTHS_FA = ["", "ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
             "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]

ASPECT_FA = {"Conjunction": "هم‌نشینی", "Sextile": "شش‌ضلعی", "Square": "تربیع",
             "Trine": "سه‌ضلعی", "Opposition": "مقابله"}

_QUESTION_TEMPLATES = {
    "Jupiter": "مشتری امروز با نقطه‌ای کلیدی در چارتت در ارتباط است. کدام فرصت را امروز می‌بینی که معمولاً ندیده‌ای؟",
    "Saturn": "زحل امروز نقطه‌ای از چارتت را برجسته می‌کند. کدام مسئولیت یا تعهد را امروز می‌توانی یک قدم جلوتر ببری؟",
    "Uranus": "اورانوس امروز جایی را در چارتت روشن می‌کند که تغییر می‌خواهد. کدام بخش از روال روزانه‌ات برایت تکراری شده است؟",
    "Neptune": "نپتون امروز با چارتت گفت‌وگو می‌کند. کدام رؤیا را مدت‌هاست به خودت نمی‌گویی؟",
    "Pluto": "پلوتو امروز یک لایهٔ عمیق را برجسته می‌کند. کدام چیز را باید رها کنی تا چیزی نو شروع شود؟",
    "Mars": "مریخ امروز به چارتت انرژی می‌دهد. کدام اقدام کوچک را امروز می‌توانی با انرژی شروع کنی؟",
    "Venus": "ناهید امروز در چارتت فعال است. چه چیزی امروز ارزش لذت بردن دارد که نادیده می‌گیریش؟",
}


def local_today(tz_name: str | None = None) -> date:
    return datetime.now(ZoneInfo(tz_name or DEFAULT_TZ)).date()


def _chart_tz(session: Session, chart: Chart) -> str:
    if chart.profile_id:
        p = session.get(BirthProfile, chart.profile_id)
        if p and p.tz_name:
            return p.tz_name
    return DEFAULT_TZ


def today_facts(chart_json: dict) -> list[dict]:
    """Top 3 transit facts for today (deterministic, no LLM)."""
    events = compute_transits(chart_json)
    out = []
    for e in events[:3]:
        out.append({
            "planet_fa": e["planet_fa"], "sign_fa": e["sign_fa"],
            "target_fa": {"Sun": "خورشیدت", "Moon": "ماهت", "ASC": "طالع‌ت"}.get(e["target"], e["target"]),
            "aspect_fa": ASPECT_FA.get(e["aspect"], e["aspect"]),
            "orb": e["orb"],
        })
    return out


def reflection_question(facts: list[dict]) -> str:
    if not facts:
        return "امروز آسمان آرام است. چه چیزی در روزت نیاز به توجه تو دارد؟"
    key = {"مشتری": "Jupiter", "زحل": "Saturn", "اورانوس": "Uranus",
           "نپتون": "Neptune", "پلوتو": "Pluto", "مریخ": "Mars", "ناهید": "Venus"}.get(
        facts[0]["planet_fa"])
    if not key:
        return "امروز چه انرژی‌ای در خودت بیشتر از همیشه حس می‌کنی؟"
    return _QUESTION_TEMPLATES.get(key, "امروز چه چیزی بیشتر از همیشه توجهت را می‌خواهد؟")


def compute_streak(session: Session, chart_id: str, tz_name: str) -> int:
    """Consecutive-day streak ending today or yesterday (E5: missed day
    resets; today still unwritten does not break the streak)."""
    days = set(session.exec(
        select(DailyReflection.day_local).where(DailyReflection.chart_id == chart_id)
    ).all())
    if not days:
        return 0
    tz = ZoneInfo(tz_name or DEFAULT_TZ)
    cursor = datetime.now(tz).date()
    if cursor.isoformat() not in days:
        cursor -= timedelta(days=1)  # today unwritten yet — streak survives until end of day
    streak = 0
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def today_action(facts: list[dict]) -> str:
    """E1 step 4 — one small action today (deterministic)."""
    if not facts:
        return "ده دقیقه در سکوت به حال خوبت فکر کن و یک جمله بنویس: «امروز چه چیزی به من انرژی داد؟»"
    p = facts[0]["planet_fa"]
    return {
        "مشتری": "ده دقیقه به یک فرصتِ امروز نگاه کن و یک قدم کوچک برای استفاده از آن بردار.",
        "زحل": "ده دقیقه به یک تعهدِ امروزت اختصاص بده؛ حتی نصف کار بهتر از هیچ است.",
        "اورانوس": "ده دقیقه یک روال تکراری را آگاهانه تغییر بده (مسیر، جای نشستن، ترتیب کارها).",
        "نپتون": "ده دقیقه بدون قضاوت، یک رؤیای قدیمی را روی کاغذ بنویس.",
        "پلوتو": "ده دقیقه به چیزی فکر کن که باید رها شود و اولین قدم رها کردن را بردار.",
        "مریخ": "ده دقیقه با انرژی حرکت کن؛ قدم بزن یا کاری را که عقب انداخته‌ای شروع کن.",
        "ناهید": "ده دقیقه از چیزی که دوست داری لذت ببر و شکرگزارش باش.",
    }.get(p, "ده دقیقه به سؤال امروز فکر کن و پاسخ را بدون قضاوت بنویس.")


def today_status(session: Session, chart: Chart) -> dict:
    """Everything the /today page needs (E2/E3/E5)."""
    tz_name = _chart_tz(session, chart)
    today = local_today(tz_name)
    facts = today_facts(chart.chart_json)
    existing = session.exec(
        select(DailyReflection).where(
            DailyReflection.chart_id == chart.id,
            DailyReflection.day_local == today.isoformat())
    ).first()
    return {
        "tz_name": tz_name,
        "today": today.isoformat(),
        "today_label": f"{today.day} {MONTHS_FA[today.month]}",
        "facts": facts,
        "question": reflection_question(facts),
        "action": today_action(facts),
        "streak": compute_streak(session, chart.id, tz_name),
        "today_done": bool(existing),
        "answer": existing.answer if existing else "",
    }


def submit_reflection(session: Session, chart_id: str, answer: str,
                      tz_name: str | None = None) -> tuple[dict | None, str | None]:
    """Atomic per (chart, local-day) insert. Returns (status, error).
    Duplicate same-day submission is rejected (E5)."""
    tz = tz_name or DEFAULT_TZ
    today = local_today(tz)
    answer = answer.strip()
    if not answer:
        return None, "پاسخ خالی است"
    if len(answer) > 2000:
        return None, "پاسخ خیلی طولانی است"
    row = DailyReflection(chart_id=chart_id, day_local=today.isoformat(),
                          tz_name=tz, answer=answer)
    session.add(row)
    try:
        session.commit()
    except Exception:  # noqa: BLE001 — unique violation = duplicate day
        session.rollback()
        return None, "امروز را قبلاً ثبت کرده‌ای؛ هر روز فقط یک تأمل"
    return {"ok": True, "day": today.isoformat()}, None
