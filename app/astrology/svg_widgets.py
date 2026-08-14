"""SVG widgets (plan §9.3) — aspect grid, element donut, house bar, KPI cards.

All deterministic, dark theme (#0b1026), Vazirmatn font, sized for inline
embedding on the web and in the PDF.
"""
from __future__ import annotations

SIGNS_ELEMENTS = {
    "حمل": "آتش", "اسد": "آتش", "قوس": "آتش",
    "ثور": "خاک", "سنبله": "خاک", "جد ی": "خاک",
    "جوزا": "هوا", "میزان": "هوا", "دلو": "هوا",
    "سرطان": "آب", "عقرب": "آب", "حوت": "آب",
}
ELEMENT_COLORS = {"آتش": "#f5c518", "خاک": "#4caf7d", "هوا": "#5ac8fa", "آب": "#7b6cf6"}
ASPECT_FA = {"Conjunction": "هم پیوند", "Opposition": "تقابل", "Trine": "سه گانه",
             "Square": "تربیع", "Sextile": "شش گانه", "Quincunx": "نیم شش گانه"}


def _svg_open(w: int, h: int) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="100%" font-family="Vazirmatn, Tahoma, sans-serif">']


def _svg_close() -> list[str]:
    return ["</svg>"]


def aspect_grid_svg(planet_positions: dict) -> str:
    """Colored matrix of planet pairs (x = y planet). planets: {name: {"lon": float, "sign_fa": str}}."""
    names = [n for n in planet_positions if n not in ("ASC", "MC", "Part_of_Fortune", "Vertex")]
    if len(names) < 2:
        return ""
    n = len(names)
    cell, header = 34, 46
    w, h = n * cell + 80, n * cell + header + 10
    p = _svg_open(w, h)
    p.append(f'<rect width="{w}" height="{h}" fill="#0b1026" rx="16"/>')
    p.append('<text x="24" y="30" fill="#cfd6ff" font-size="15" font-weight="700">ماتریس جنبه‌ها</text>')
    for i, name in enumerate(names):
        x = 70 + i * cell
        p.append(f'<text x="{x + cell // 2}" y="{header - 14}" fill="#8b96c9" font-size="11" text-anchor="middle">{name}</text>')
        p.append(f'<text x="{x + cell // 2}" y="{h - 8}" fill="#8b96c9" font-size="11" text-anchor="middle">{name}</text>')
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lon_i = planet_positions[names[i]]["longitude"]
            lon_j = planet_positions[names[j]]["longitude"]
            diff = abs(lon_i - lon_j) % 360
            diff = min(diff, 360 - diff)
            color, orb, asp = None, None, None
            for asp, (max_orb, c) in {
                "Conjunction": (8, "#f5c518"), "Opposition": (8, "#ff6b6b"),
                "Trine": (7, "#4caf7d"), "Square": (7, "#ff8a5c"),
                "Sextile": (5, "#5ac8fa"), "Quincunx": (3, "#c792ea"),
            }.items():
                if abs(diff - {"Conjunction": 0, "Opposition": 180, "Trine": 120,
                               "Square": 90, "Sextile": 60, "Quincunx": 150}[asp]) <= max_orb:
                    color, orb = c, round(abs(diff - {"Conjunction": 0, "Opposition": 180,
                                                      "Trine": 120, "Square": 90,
                                                      "Sextile": 60, "Quincunx": 150}[asp]), 1)
                    break
            x, y = 70 + j * cell, header + i * cell
            if color and asp:
                p.append(f'<circle cx="{x + cell // 2}" cy="{y + cell // 2}" r="9" fill="{color}" fill-opacity="0.85">'
                         f'<title>{names[i]} {ASPECT_FA.get(asp, asp)} {names[j]} (orb {orb}°)</title></circle>')
            else:
                p.append(f'<rect x="{x + 6}" y="{y + 6}" width="{cell - 12}" height="{cell - 12}" rx="6" '
                         f'fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)"/>')
    p.extend(_svg_close())
    return "".join(p)


def element_donut_svg(sign_counts: dict) -> str:
    """Donut of element distribution. sign_counts: {sign_fa: count}."""
    counts = {"آتش": 0, "خاک": 0, "هوا": 0, "آب": 0}
    for sign, cnt in sign_counts.items():
        el = SIGNS_ELEMENTS.get(sign)
        if el:
            counts[el] += cnt
    total = sum(counts.values()) or 1
    w, h, cx, cy, r = 320, 220, 130, 110, 80
    p = _svg_open(w, h)
    p.append(f'<rect width="{w}" height="{h}" fill="#0b1026" rx="16"/>')
    p.append('<text x="24" y="28" fill="#cfd6ff" font-size="15" font-weight="700">تعادل عناصر</text>')
    ang = -90
    for el, col in ELEMENT_COLORS.items():
        frac = counts[el] / total
        a1, a2 = ang, ang + frac * 360
        import math
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        x2, y2 = cx + r * math.cos(math.radians(a2)), cy + r * math.sin(math.radians(a2))
        large = 1 if (a2 - a1) > 180 else 0
        if frac > 0.001:
            p.append(f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}" fill-opacity="0.8"/>')
        ang = a2
    p.append(f'<circle cx="{cx}" cy="{cy}" r="46" fill="#0b1026"/>')
    p.append(f'<text x="{cx}" y="{cy - 2}" fill="#fff" font-size="22" font-weight="800" text-anchor="middle">{total}</text>')
    p.append(f'<text x="{cx}" y="{cy + 18}" fill="#8b96c9" font-size="11" text-anchor="middle">سیاره</text>')
    ly = 40
    for el, col in ELEMENT_COLORS.items():
        p.append(f'<circle cx="212" cy="{ly}" r="6" fill="{col}"/>')
        p.append(f'<text x="226" y="{ly + 4}" fill="#cfd6ff" font-size="12">{el} — {counts[el]}</text>')
        ly += 26
    p.extend(_svg_close())
    return "".join(p)


def house_bar_svg(house_counts: dict) -> str:
    """Horizontal bar chart of planet counts per house (1-12).
    When birth time is unknown there are no houses — the widget renders a
    notice instead of fake zeros (audit P0)."""
    w, h = 320, 260
    p = _svg_open(w, h)
    p.append(f'<rect width="{w}" height="{h}" fill="#0b1026" rx="16"/>')
    if not house_counts:
        p.append('<text x="24" y="28" fill="#cfd6ff" font-size="15" font-weight="700">توزیع خانه‌ها</text>')
        p.append('<text x="24" y="80" fill="#8b96c9" font-size="12">ساعت تولد نامعلوم است؛</text>')
        p.append('<text x="24" y="100" fill="#8b96c9" font-size="12">خانه‌ها محاسبه نشده‌اند.</text>')
        p.extend(_svg_close())
        return "".join(p)
    p.append('<text x="24" y="28" fill="#cfd6ff" font-size="15" font-weight="700">توزیع خانه‌ها</text>')
    maxv = max(house_counts.values()) if house_counts else 1
    for i in range(12):
        n = house_counts.get(i + 1, 0)
        bw = 120 * n / maxv
        y = 48 + i * 16
        p.append(f'<text x="24" y="{y + 10}" fill="#8b96c9" font-size="11">خانه {i + 1}</text>')
        p.append(f'<rect x="90" y="{y}" width="{max(bw, 4)}" height="10" rx="5" fill="#6a5acd" fill-opacity="{0.35 + 0.55 * n / maxv}"/>')
        if n:
            p.append(f'<text x="{98 + bw}" y="{y + 10}" fill="#fff" font-size="11">{n}</text>')
    p.extend(_svg_close())
    return "".join(p)


def kpi_svg(items: list[tuple[str, str]]) -> str:
    """KPI card row for PDF final page. items: [(label_fa, value_fa)] — max 4."""
    n = len(items)
    card_w, gap, h = 150, 12, 86
    w = n * card_w + (n - 1) * gap + 40
    p = _svg_open(w, h + 20)
    for i, (label, value) in enumerate(items[:4]):
        x = 20 + i * (card_w + gap)
        p.append(f'<rect x="{x}" y="12" width="{card_w}" height="{h}" rx="14" fill="#121a3f" '
                 f'stroke="rgba(255,255,255,0.09)"/>')
        p.append(f'<text x="{x + card_w // 2}" y="40" fill="#f5c518" font-size="17" font-weight="800" text-anchor="middle">{value}</text>')
        p.append(f'<text x="{x + card_w // 2}" y="62" fill="#8b96c9" font-size="11" text-anchor="middle">{label}</text>')
    p.extend(_svg_close())
    return "".join(p)


# ────────────────────────────── transit year timeline (plan §9.3 / §10) ──────────────────────────────

_SLOW_FA = {"Jupiter": "مشتری", "Saturn": "زحل", "Uranus": "اورانوس", "Neptune": "نپتون", "Pluto": "پلوتو"}
_ASPECT_ORBS = {"Conjunction": 5.0, "Opposition": 5.0, "Trine": 5.0, "Square": 4.5, "Sextile": 3.5}


def _natal_targets(chart_json: dict) -> dict:
    """Natal personal points to track: Sun, Moon, Mercury, Venus, Mars, ASC."""
    out: dict[str, float] = {}
    plan = chart_json.get("planets", {})
    for key, fa in (("Sun", "خورشید"), ("Moon", "ماه"), ("Mercury", "عطارد"),
                    ("Venus", "ناهید"), ("Mars", "مریخ")):
        lon = plan.get(key, {}).get("longitude")
        if lon is not None:
            out[key] = float(lon)
    asc = chart_json.get("houses", {}).get("ascendant")
    if asc is not None:
        out["ASC"] = float(asc)
    return out


def transit_timeline_svg(chart_json: dict, months: int = 12) -> str:
    """12-month overview: which slow transits hit the natal chart, month by month.

    Deterministic (pyswisseph), no LLM. Grid: rows = natal points, cols = months.
    A colored cell marks a conjunction/opposition/trine/square/sextile that month.
    """
    from datetime import datetime, timedelta, timezone
    import swisseph as swe

    targets = _natal_targets(chart_json)
    now = datetime.now(timezone.utc)
    rows = [("Sun", "خورشید"), ("Moon", "ماه"), ("Mercury", "عطارد"),
            ("Venus", "ناهید"), ("Mars", "مریخ"), ("ASC", "طالع")]
    rows = [(k, fa) for k, fa in rows if k in targets]

    # month snapshots: transit lon of slow planets at first of each month
    grid: dict[tuple[int, int], tuple[str, float]] = {}  # (row, col) -> (aspect, orb)
    month_labels: list[str] = []
    base = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for col in range(months):
        when = base + timedelta(days=31 * col)
        jd = swe.julday(when.year, when.month, when.day, 0)
        month_labels.append(f"{when.month:02d}/{when.year % 100:02d}")
        for key, swe_id in (("Jupiter", 5), ("Saturn", 6), ("Uranus", 7), ("Neptune", 8), ("Pluto", 10)):
            tlon = swe.calc_ut(jd, swe_id)[0][0]
            for r_idx, (rk, _fa) in enumerate(rows):
                diff = abs(tlon - targets[rk])
                diff = min(diff, 360 - diff)
                for asp, orb in _ASPECT_ORBS.items():
                    base_ang = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}[asp]
                    if abs(diff - base_ang) <= orb:
                        cell = grid.get((r_idx, col))
                        if cell is None or cell[1] > abs(diff - base_ang):
                            grid[(r_idx, col)] = (asp, round(abs(diff - base_ang), 1))
                        break

    # layout
    col_w, row_h, left, top = 46, 26, 92, 30
    h = top + len(rows) * row_h + 26
    w = left + months * col_w + 16
    p = _svg_open(w, h)
    p.append('<text x="8" y="20" fill="#e8ecff" font-size="13" font-weight="800">نقشهی گذرهای سال آینده</text>')
    for col, ml in enumerate(month_labels):
        x = left + col * col_w
        p.append(f'<text x="{x + col_w / 2}" y="18" fill="#8b96c9" font-size="9" text-anchor="middle">{ml}</text>')
    for r_idx, (rk, fa) in enumerate(rows):
        y = top + r_idx * row_h
        p.append(f'<text x="8" y="{y + 15}" fill="#c7cdf2" font-size="11">{fa}</text>')
        for col in range(months):
            x = left + col * col_w
            cell = grid.get((r_idx, col))
            if cell:
                asp, orb = cell
                color = {"Conjunction": "#f5c518", "Opposition": "#ff6b6b",
                         "Trine": "#4caf7d", "Square": "#ff8a5c", "Sextile": "#5ac8fa"}[asp]
                marker = {"Conjunction": "☌", "Opposition": "☍", "Trine": "△",
                          "Square": "□", "Sextile": "⚹"}[asp]
                p.append(f'<circle cx="{x + col_w / 2}" cy="{y + 13}" r="6" fill="{color}" opacity="0.85"/>')
                p.append(f'<text x="{x + col_w / 2}" y="{y + 17}" fill="#0b1026" font-size="8" font-weight="800" text-anchor="middle">{marker}</text>')
    # legend
    ly = h - 18
    lx = left
    for asp, fa in (("Conjunction", "☌ همپیوند"), ("Opposition", "☍ تقابل"), ("Trine", "△ سهگانه"),
                    ("Square", "□ تربیع"), ("Sextile", "⚹ ششگانه")):
        color = {"Conjunction": "#f5c518", "Opposition": "#ff6b6b", "Trine": "#4caf7d",
                 "Square": "#ff8a5c", "Sextile": "#5ac8fa"}[asp]
        p.append(f'<text x="{lx}" y="{ly}" fill="#8b96c9" font-size="9"><tspan fill="{color}">{fa}</tspan></text>')
        lx += 96
    p.extend(_svg_close())
    return "".join(p)
