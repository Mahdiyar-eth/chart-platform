"""ZAYCHE P3 (D1/D2) — Self-discovery catalog: «خودت را کشف کن».

Each card = an intent with allowed domains + a focused instruction so the
LLM answers ONE question well (short, fast, evidence-backed) instead of a
13-section deep report.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    key: str
    title_fa: str
    benefit_fa: str          # one-line benefit (D2)
    domains: tuple[str, ...] # allowed evidence domains (rules.py DOMAINS)
    question_fa: str         # the focused question the LLM must answer
    focus: str               # extra instruction (which factors to lean on)


CARD_CATALOG: list[Card] = [
    Card("personality", "شخصیت من", "الگوی اصلی شخصیتت و چیزهایی که تو را تو می‌کنند",
         ("identity", "mind"),
         "الگوی اصلی شخصیت من چیست و چه چیزی مرا از دیگران متمایز می‌کند؟",
         "روی خورشید، طالع (ASC) و عطارد تمرکز کن — چطور این سه با هم دیده می‌شوند."),
    Card("career", "مسیر شغلی من", "ببین کدام مسیرها با ساختار انگیزشی تو هم‌خوانی دارند",
         ("career", "education", "money"),
         "کدام مسیرهای شغلی با ساختار انگیزشی و توانایی‌های طبیعی من هم‌خوانی دارند؟",
         "روی زحل، MC و خانهٔ ۱۰ تمرکز کن؛ از پیش‌بینی نتیجهٔ قطعی بپرهیز."),
    Card("relationships", "الگوی روابط من", "الگوی تکرارشوندهٔ ارتباطی‌ات را ببین",
         ("relationships", "family"),
         "الگوی اصلی من در روابط نزدیک چیست و در مواجهه با صمیمیت چطور رفتار می‌کنم؟",
         "روی زهره، ماه و خانهٔ ۷ تمرکز کن — الگو را توصیف کن نه سرنوشت را."),
    Card("money", "رابطه من با پول", "نگرش طبیعی‌ات به پول و ریسک مالی را بفهم",
         ("money",),
         "نگرش طبیعی من به پول، خرج کردن و ریسک مالی چگونه است؟",
         "روی مشتری، زحل و خانهٔ ۲ تمرکز کن؛ از وعدهٔ ثروت بپرهیز."),
    Card("strengths", "نقاط قوت من", "چیزهایی که در آن‌ها طبیعی‌تر از بقیه عمل می‌کنی",
         ("identity", "creativity"),
         "چه توانایی‌هایی در من طبیعی و پررنگ‌تر از بقیه دیده می‌شود؟",
         "جنبه‌های پایدار و قابل اتکا را برجسته کن؛ بدون اغراق."),
    Card("blind_spots", "نقاط کور من", "جاهایی که معمولاً از دیدن‌شان غافلی",
         ("karma", "wellbeing"),
         "چه الگوهایی در من هست که معمولاً خودم نمی‌بینم و دیگران زودتر متوجه می‌شوند؟",
         "صادقانه و مهربانانه؛ نه ترساندن، نه تشخیص روان‌شناسی."),
    Card("repeating_patterns", "الگوهای تکراری", "چرا یک الگوی خاص در زندگی‌ات تکرار می‌شود؟",
         ("karma", "relationships"),
         "چرا یک الگوی خاص در زندگی من تکرار می‌شود و چه چیزی آن را فعال می‌کند؟",
         "الگو را بر اساس ترکیب‌های نجومی توضیح بده؛ از «مقدر شده» بپرهیز."),
    Card("growth_blockers", "موانع رشد من", "چه چیزی جلوی رشدت را می‌گیرد و چطور نرمش می‌کند",
         ("karma", "wellbeing", "education"),
         "چه چیزی معمولاً جلوی رشد من را می‌گیرد و چه نگاهی به آن می‌تواند کمک کند؟",
         "موانع را به‌عنوان فرصت تأمل توصیف کن نه محکومیت."),
    Card("decision_style", "سبک تصمیم‌گیری من", "بفهم با ذهن تصمیم می‌گیری یا با احساس",
         ("mind", "identity"),
         "سبک طبیعی تصمیم‌گیری من چیست و در انتخاب‌های مهم چه چیزهایی را نادیده می‌گیرم؟",
         "روی عطارد، ماه و صعود تمرکز کن؛ تعادل ذهن/احساس را توضیح بده."),
    Card("communication", "ارتباط من با دیگران", "شیوهٔ طبیعی گفت‌وگو و تأثیرگذاری‌ات را ببین",
         ("network", "relationships", "mind"),
         "شیوهٔ طبیعی من در گفت‌وگو، ابراز عقیده و برقراری ارتباط چیست؟",
         "روی عطارد، زهره و خانهٔ ۳ و ۱۱ تمرکز کن."),
]

CARD_MAP: dict[str, Card] = {c.key: c for c in CARD_CATALOG}


def card_keys() -> list[str]:
    return [c.key for c in CARD_CATALOG]
