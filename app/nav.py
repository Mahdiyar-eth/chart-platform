"""D1/D2 — single source of truth for all three navigation bars (HERMES-PLAN-v1 §7).

Every nav in base.html renders from NAV_ITEMS via nav_for(); no hand-written lists.
State-aware: users without a chart see the growth CTA; with-chart users get their tools.
"""
from __future__ import annotations


class NavItem:
    def __init__(self, key: str, label_fa: str, url: str, icon: str = "",
                 group: str = "", needs_chart: bool = False, primary: bool = False):
        self.key = key
        self.label_fa = label_fa
        self.url = url
        self.icon = icon
        self.group = group
        self.needs_chart = needs_chart
        self.primary = primary  # the ONE emphasized action


NAV_ITEMS: list[NavItem] = [
    NavItem("home", "خانه", "/", icon="icon-home"),
    # state-aware primary action (replaces the ambiguous FAB):
    NavItem("chart", "چارت رایگان", "/birth-form", icon="icon-compass", primary=True),
    NavItem("mychart", "چارت من", "/dashboard", icon="icon-grid", needs_chart=True),
    NavItem("explore", "کاوش", "/explore", icon="icon-star", needs_chart=True),
    NavItem("synastry", "سیناستری", "/synastry", icon="icon-heart"),
    NavItem("rectify", "بازبینی ساعت", "/rectify", icon="icon-clock"),
    # R16: /sky = public "today's sky" page — label must say that; the PERSONAL
    # transit timeline lives on the chart page (/transits/{chart_id}) + dashboard.
    NavItem("transits", "آسمان امروز", "/sky", icon="icon-sun"),
    NavItem("plans", "پلن‌ها", "/plans", icon="icon-tag"),
    # drawer-only groups:
    NavItem("articles", "مقالات", "/articles", icon="icon-book-open", group="یادگیری"),
    NavItem("learn", "آموزش نجوم", "/learn", icon="icon-book", group="یادگیری"),
    NavItem("guide", "راهنما", "/guide", icon="icon-help", group="یادگیری"),
    NavItem("faq", "سؤالات پرتکرار", "/faq", icon="icon-help", group="یادگیری"),
    
    NavItem("account", "حساب من", "/account", icon="icon-user", group="حساب"),
    NavItem("credits", "اعتبار من", "/credits", icon="icon-sparkles", group="حساب"),
    NavItem("orders", "سفارش‌ها", "/orders", icon="icon-tag", group="حساب"),
    NavItem("reports", "گزارش‌ها", "/reports", icon="icon-book-open", group="حساب"),
    NavItem("about", "درباره ما", "/about", icon="icon-link", group="دربارهٔ ما"),
    NavItem("contact", "تماس با پشتیبانی", "/contact", icon="icon-chat", group="دربارهٔ ما"),
    NavItem("privacy", "حریم خصوصی", "/privacy", icon="icon-lock", group="دربارهٔ ما"),
    NavItem("terms", "قوانین", "/terms", icon="icon-book", group="دربارهٔ ما"),
    NavItem("refund", "استرداد وجه", "/refund", icon="icon-refresh", group="دربارهٔ ما"),
]

_BOTTOM_NO_CHART = ["home", "chart", "synastry", "plans", "account"]
_BOTTOM_WITH_CHART = ["home", "mychart", "explore", "synastry", "account"]
_TOP_BASE = ["home", "synastry", "rectify", "transits", "plans"]


def _visible(item: NavItem, has_chart: bool) -> bool:
    return not item.needs_chart or has_chart


def nav_for(*, has_chart: bool) -> dict:
    """Return {'bottom': [...], 'top': [...], 'drawer': [(group, [items...])]}."""
    bottom_keys = _BOTTOM_WITH_CHART if has_chart else _BOTTOM_NO_CHART
    by_key = {n.key: n for n in NAV_ITEMS}

    bottom = []
    for k in bottom_keys:
        it = by_key[k]
        # a user WITH a chart never sees the free-chart CTA in the bottom bar
        if has_chart and k == "chart":
            continue
        bottom.append(it)

    top = [by_key[k] for k in _TOP_BASE if _visible(by_key[k], has_chart)]
    if has_chart and by_key["mychart"] not in top:
        top.insert(1, by_key["mychart"])
    top = top[:5]  # R18/X21: hard cap — max 5 top items

    groups: dict[str, list[NavItem]] = {}
    for it in NAV_ITEMS:
        if it.group and _visible(it, has_chart):
            groups.setdefault(it.group, []).append(it)
    drawer = list(groups.items())
    return {"bottom": bottom, "top": top, "drawer": drawer}
