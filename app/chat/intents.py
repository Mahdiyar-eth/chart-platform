"""Intent detection (Persian) — Question → Intent (plan v3.1 §13 AI Chat).

Deterministic keyword classifier; no LLM call needed for routing.
"""
from __future__ import annotations


INTENTS: dict[str, list[str]] = {
    "identity": ["شخصیت", "من کیستم", "هویت", "خودشناسی", "نفس", "طبع", "روحیات", "خلقیات", "روحیه", "خصوصیت"],
    "emotions": ["احساس", "هیجان", "عاطفه", "غم", "شادی", "ناراحت", "دلتنگی", "عصبی", "حس", "ماه"],
    "career": ["شغل", "کار", "حرفه", "مسیر شغلی", "موفقیت کاری", "درآمد شغلی", "ریاست", "مدیریت", "بیزینس", "کسب و کار", "استارتاپ"],
    "money": ["پول", "ثروت", "مالی", "درآمد", "پس‌انداز", "سرمایه", "بدهی", "خرج", "مادیات", "ریال", "تومان"],
    "relationships": ["ازدواج", "عشق", "عاشق", "رابطه", "همسر", "دوستی", "شریک", "نامزدی", "خواستگار", "طلاق", "مهر"],
    "family": ["خانواده", "پدر", "مادر", "فرزند", "بچه", "خواهر", "برادر", "خانه", "خانوادگی"],
    "wellbeing": ["سلامت", "انرژی", "خستگی", "ورزش", "بدن", "خواب", "استرس", "آرامش", "نشاط"],
    "education": ["تحصیل", "درس", "دانشگاه", "مدرسه", "یادگیری", "آموزش", "کتاب", "مدرک", "رشته"],
    "network": ["دوست", "رفیق", "شبکه", "ارتباطات", "آشنا", "همکار", "معاشرت", "محبوبیت"],
    "creativity": ["خلاقیت", "هنر", "نقاشی", "موسیقی", "نوشتن", "ایده", "ابتکار", "نوآوری"],
    "spirituality": ["معنویت", "روح", "عرفان", "دین", "مذهب", "مراقبه", "مدیتیشن", "انرژی معنوی", "دعا"],
    "karma": ["کارما", "سرنوشت", "تقدیر", "بدهی کارمایی", "زندگی قبلی", "درس زندگی", "مقصد روح"],
    "transit": ["امسال", "امسال", "آینده", "پیش رو", "گذر", "ترانزیت", "پیش‌بینی", "کی بهتر", "کی بدتر", "سال آینده", "ماه آینده", "موفقیت آینده"],
    "strength": ["نقطه قوت", "قوت", "توانایی", "استعداد", "مهارت", "چه کارایی بلدم", "قدرت"],
    "weakness": ["نقطه ضعف", "ضعف", "چالش", "مشکل", "عیب", "کمبود", "محدودیت"],
}

FALLBACK = "general"


def detect_intent(question: str) -> str:
    """Return best-matching intent key (or 'general')."""
    q = question.strip().lower()
    best, best_score = FALLBACK, 0
    for intent, kws in INTENTS.items():
        score = sum(1 for kw in kws if kw in q)
        if score > best_score:
            best, best_score = intent, score
    return best


def route_question(question: str, focus_areas: list[str] | None = None) -> dict:
    """Intent + domain list to fetch from the report/chart."""
    intent = detect_intent(question)
    domain_map = {
        "identity": ["identity"], "emotions": ["emotions"], "career": ["career"],
        "money": ["money"], "relationships": ["relationships"], "family": ["family"],
        "wellbeing": ["wellbeing"], "education": ["education"], "network": ["network"],
        "creativity": ["creativity"], "spirituality": ["spirituality"],
        "karma": ["karma"], "transit": ["career", "money", "wellbeing"],
        "strength": ["identity", "wellbeing", "career"], "weakness": ["identity", "karma"],
        "general": list((focus_areas or ["identity", "emotions", "career", "money", "relationships"])),
    }
    return {"intent": intent, "domains": domain_map[intent]}
