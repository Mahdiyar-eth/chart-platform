"""Galactic v2 — single source of truth for every navigation surface.

Replaces the old 5-slot bottom bar and the "کاوش" entry (explore is being
merged into chat, plan §3). Three surfaces, one list:

  top      → desktop appbar (≤5 items)
  bottom   → mobile bottom nav (EXACTLY 4 items — plan §10)
  drawer   → grouped full menu (both breakpoints)

API-first note: nav_v2_json() returns the same structure as plain dicts so a
native app can render its own tab bar from the identical source.
"""
from __future__ import annotations


class NavItem:
    __slots__ = ("group", "icon", "key", "label_fa", "needs_chart", "primary", "short_fa", "url")

    def __init__(self, key: str, label_fa: str, url: str, icon: str = "",
                 group: str = "", needs_chart: bool = False, primary: bool = False,
                 short_fa: str = ""):
        self.key = key
        self.label_fa = label_fa
        # Bottom-nav label. Must stay short — a wrapped tab label reads as a
        # broken layout on mobile. Falls back to label_fa when short enough.
        self.short_fa = short_fa or label_fa
        self.url = url
        self.icon = icon
        self.group = group
        self.needs_chart = needs_chart
        self.primary = primary

    def as_dict(self) -> dict:
        return {"key": self.key, "label_fa": self.label_fa, "short_fa": self.short_fa,
                "url": self.url, "icon": self.icon, "group": self.group,
                "needs_chart": self.needs_chart, "primary": self.primary}


NAV_ITEMS: list[NavItem] = [
    # ── primary surfaces ────────────────────────────────────────────────
    NavItem("home", "خانه", "/", icon="icon-home"),
    NavItem("chart", "چارت رایگان", "/birth-form", icon="icon-compass", primary=True, short_fa="چارت"),
    NavItem("mychart", "چارت من", "/dashboard", icon="icon-grid", needs_chart=True),
    # PLAN §3: «کاوش» retired as a product — conversation is the one place you ask.
    NavItem("chat", "گفت‌وگو", "/chats", icon="icon-chat", needs_chart=True),
    NavItem("learn", "آموزش", "/learn", icon="icon-book"),
    NavItem("plans", "محصول‌ها", "/plans", icon="icon-tag"),
    NavItem("account", "من", "/account", icon="icon-user"),

    # ── secondary (drawer / contextual) ─────────────────────────────────
    NavItem("synastry", "سازگاری دو نفر", "/synastry", icon="icon-heart", group="خدمات"),
    NavItem("sky", "آسمان امروز", "/sky", icon="icon-sun", group="خدمات"),
    NavItem("rectify", "بازبینی ساعت تولد", "/rectify", icon="icon-clock", group="خدمات"),

    NavItem("articles", "مقاله‌ها", "/articles", icon="icon-book-open", group="یادگیری"),
    NavItem("guide", "راهنما", "/guide", icon="icon-help", group="یادگیری"),
    NavItem("faq", "سؤال‌های پرتکرار", "/faq", icon="icon-help", group="یادگیری"),
    NavItem("glossary", "واژه‌نامه", "/glossary", icon="icon-book", group="یادگیری"),
    NavItem("solar_guide", "چارت سالیانه چیست؟", "/solar-guide", icon="icon-sun", group="یادگیری"),
    NavItem("reloc_guide", "چارت مهاجرت چیست؟", "/relocation-guide", icon="icon-compass", group="یادگیری"),

    NavItem("credits", "اعتبار من", "/credits", icon="icon-sparkles", group="حساب"),
    NavItem("reports", "گزارش‌های من", "/reports", icon="icon-book-open", group="حساب"),
    NavItem("orders", "سفارش‌ها", "/orders", icon="icon-tag", group="حساب"),
    NavItem("settings", "تنظیمات", "/settings", icon="icon-user", group="حساب"),

    NavItem("about", "دربارهٔ ما", "/about", icon="icon-link", group="دربارهٔ ما"),
    NavItem("contact", "تماس با پشتیبانی", "/contact", icon="icon-chat", group="دربارهٔ ما"),
    NavItem("privacy", "حریم خصوصی", "/privacy", icon="icon-lock", group="دربارهٔ ما"),
    NavItem("terms", "قوانین", "/terms", icon="icon-book", group="دربارهٔ ما"),
    NavItem("refund", "استرداد وجه", "/refund", icon="icon-refresh", group="دربارهٔ ما"),
]

# PLAN §10 — bottom nav is EXACTLY 4 slots. Labels must never wrap.
_BOTTOM_NO_CHART = ["home", "chart", "learn", "account"]
_BOTTOM_WITH_CHART = ["home", "mychart", "chat", "account"]
# PLAN §10 — desktop top bar
_TOP_NO_CHART = ["home", "chart", "learn", "plans"]
_TOP_WITH_CHART = ["mychart", "chat", "learn", "plans"]

BOTTOM_SLOTS = 4
TOP_MAX = 5


def _visible(item: NavItem, has_chart: bool) -> bool:
    return not item.needs_chart or has_chart


def nav_for(*, has_chart: bool) -> dict:
    """Return {'bottom': [...], 'top': [...], 'drawer': [(group, [items...])]}."""
    by_key = {n.key: n for n in NAV_ITEMS}

    bottom = [by_key[k] for k in (_BOTTOM_WITH_CHART if has_chart else _BOTTOM_NO_CHART)]
    assert len(bottom) == BOTTOM_SLOTS, "bottom nav must stay at 4 slots"

    top = [by_key[k] for k in (_TOP_WITH_CHART if has_chart else _TOP_NO_CHART)
           if _visible(by_key[k], has_chart)][:TOP_MAX]

    groups: dict[str, list[NavItem]] = {}
    for it in NAV_ITEMS:
        if it.group and _visible(it, has_chart):
            groups.setdefault(it.group, []).append(it)

    return {"bottom": bottom, "top": top, "drawer": list(groups.items())}


def nav_v2_json(*, has_chart: bool) -> dict:
    """API-first: identical structure, plain dicts — for the native app."""
    nav = nav_for(has_chart=has_chart)
    return {
        "top": [i.as_dict() for i in nav["top"]],
        "bottom": [i.as_dict() for i in nav["bottom"]],
        "drawer": [{"group": g, "items": [i.as_dict() for i in items]}
                   for g, items in nav["drawer"]],
    }
