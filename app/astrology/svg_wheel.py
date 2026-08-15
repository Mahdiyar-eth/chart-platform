"""
Chart wheel SVG renderer — deterministic, no external deps.

Layout (polar):
  - outer zodiac ring (12 signs, Persian labels)
  - house ring (Placidus cusps, numbered 1-12)
  - planet ring with glyphs + Persian names
  - ASC/MC markers
Returns a standalone <svg> string (RTL-friendly, uses current font stack).
"""
from __future__ import annotations

import math

from app.astrology.engine import SIGNS_FA, SIGNS_EN  # noqa: F401

SIGN_GLYPH = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_GLYPH = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Node": "☊", "Lilith": "⚸", "Chiron": "⚷", "Fortune": "⊗", "ASC": "АС", "MC": "MC",
}
PLANET_FA = {
    "Sun": "خورشید", "Moon": "ماه", "Mercury": "عطارد", "Venus": "زهره", "Mars": "مریخ",
    "Jupiter": "مشتری", "Saturn": "زحل", "Uranus": "اورانوس", "Neptune": "نپتون",
    "Pluto": "پلوتو", "Node": "گره شمالی", "Lilith": "لیلیت", "Chiron": "کایرون",
    "Fortune": "بخت", "ASC": "طالع", "MC": "میلادی وسط",
}
# 12 zodiac colors (identity palette from plan v3.1 — brightened for WCAG AA contrast on dark bg)
SIGN_COLORS = [
    "#E4572E", "#C9A227", "#D4B84C", "#C78B97", "#E3B23C", "#9BC26E",
    "#7FC4A8", "#9D8AF0", "#A78BFA", "#6E87C9", "#6FA8D8", "#4FD1C5",
]

RAD = math.pi / 180.0


def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = (deg - 90) * RAD  # 0° at top, clockwise
    return cx + r * math.cos(a), cy + r * math.sin(a)


def render_chart_svg(chart: dict, size: int = 800) -> str:
    cx = cy = size / 2
    R = size / 2 - 8
    r_outer, r_sign, _, r_planet, r_inner = R, R * 0.84, R * 0.72, R * 0.55, R * 0.30

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
             f'width="100%" height="100%" font-family="Vazirmatn, Tahoma, sans-serif">']
    parts.append(f'<rect width="{size}" height="{size}" fill="#0b1026" rx="24"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="#2a3566" stroke-width="2"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="#10173a" stroke="#2a3566" stroke-width="1.5"/>')

    houses = chart.get("houses", {})
    cusps = [houses[f"h{i+1}"] for i in range(12)] if houses else []
    angles = chart.get("angles", {})
    planets = chart.get("planets", {})

    # ── zodiac segments (12 × 30°) ──
    for i in range(12):
        a0, a1 = i * 30, (i + 1) * 30
        x0, y0 = _polar(cx, cy, r_outer, a0)
        x1, y1 = _polar(cx, cy, r_outer, a1)
        x2, y2 = _polar(cx, cy, r_sign, a1)
        x3, y3 = _polar(cx, cy, r_sign, a0)
        col = SIGN_COLORS[i]
        parts.append(f'<path d="M{x0:.1f},{y0:.1f} A{r_outer:.1f},{r_outer:.1f} 0 0 1 {x1:.1f},{y1:.1f} '
                     f'L{x2:.1f},{y2:.1f} A{r_sign:.1f},{r_sign:.1f} 0 0 0 {x3:.1f},{y3:.1f} Z" '
                     f'fill="{col}" fill-opacity="0.16" stroke="{col}" stroke-opacity="0.6" stroke-width="1"/>')
        mx, my = _polar(cx, cy, (r_outer + r_sign) / 2, a0 + 15)
        parts.append(f'<text x="{mx:.1f}" y="{my:.1f}" font-size="{size*0.030:.0f}" '
                     f'fill="{col}" text-anchor="middle" dominant-baseline="middle">{SIGNS_FA[i]}</text>')

    # ── house cusps (lines + numbers) — skipped when birth time unknown ──
    for i in range(len(cusps)):
        c = cusps[i]
        x0, y0 = _polar(cx, cy, r_inner, c)
        x1, y1 = _polar(cx, cy, r_outer, c)
        emph = i in (0, 9)  # ASC / MC lines
        parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                     f'stroke="{"#f5c518" if emph else "#3d4c8f"}" stroke-width="{"2" if emph else "1"}"/>')
        nx, ny = _polar(cx, cy, (r_inner + r_planet) / 2, c)
        parts.append(f'<text x="{nx:.1f}" y="{ny:.1f}" font-size="{size*0.02:.0f}" fill="#8fa3d8" '
                     f'text-anchor="middle" dominant-baseline="middle">{i + 1}</text>')

    # ── planets (labels spidered across multiple radii to avoid overlap) ──
    items = [(name, p["longitude"]) for name, p in planets.items()
             if name != "Fortune"]
    items.sort(key=lambda t: t[1])
    SPREAD = 9.0   # degrees — wider catch (mobile labels are wide)
    clusters: list[list[tuple[str, float]]] = []
    for it in items:
        # circular distance — 359° and 1° are 2° apart, not 358°
        if clusters:
            prev_lon = clusters[-1][-1][1]
            d = abs(it[1] - prev_lon)
            if d > 180:
                d = 360 - d
            if d < SPREAD:
                clusters[-1].append(it)
                continue
        clusters.append([it])
    # label radius tiers (inner → outer) for radial spidering
    tiers = [size * 0.034, size * 0.056, size * 0.078, size * 0.100]
    for cluster in clusters:
        n = len(cluster)
        for i, (name, lon) in enumerate(cluster):
            if n == 1:
                a_off = 0.0
                glyph_r = r_planet
                label_r = r_planet + size * 0.058
            else:
                # angular spread around cluster center + alternating radii
                span = min(22.0, 6.0 * n)
                a_off = (i - (n - 1) / 2) * (span / max(n - 1, 1))
                glyph_r = r_planet
                label_r = r_planet + tiers[i % len(tiers)]
            px, py = _polar(cx, cy, glyph_r, lon)
            glyph = PLANET_GLYPH.get(name, "•")
            col = "#f5c518" if name == "Sun" else "#e8ecff"
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{size*0.016:.0f}" '
                         f'fill="#10173a" stroke="{col}" stroke-width="1.2"/>')
            parts.append(f'<text x="{px:.1f}" y="{py:.1f}" font-size="{size*0.024:.0f}" fill="{col}" '
                         f'text-anchor="middle" dominant-baseline="middle">{glyph}</text>')
            lx, ly = _polar(cx, cy, label_r, lon + a_off)
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="{size*0.020:.0f}" fill="#c2cdf2" '
                         f'text-anchor="middle" dominant-baseline="middle">{PLANET_FA.get(name, name)}</text>')

    # ── ASC / MC labels ──
    for key, label in (("ASC", "طالع"), ("MC", "MC")):
        if key in angles:
            lon = angles[key]["longitude"]
            px, py = _polar(cx, cy, r_inner - size * 0.03, lon)
            parts.append(f'<text x="{px:.1f}" y="{py:.1f}" font-size="{size*0.022:.0f}" fill="#f5c518" '
                         f'text-anchor="middle" dominant-baseline="middle" font-weight="bold">{label}</text>')

    parts.append("</svg>")
    return "".join(parts)


def save_chart_svg(chart: dict, path: str, size: int = 800) -> str:
    svg = render_chart_svg(chart, size=size)
    with open(path, "w") as f:
        f.write(svg)
    return path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from app.astrology.engine import compute_from_fields
    from app.astrology.golden_data import GOLDEN_CHARTS

    b = GOLDEN_CHARTS[0]["birth"]
    c = compute_from_fields(**b).chart_json
    # bandit B108 accepted: developer-only CLI debug output — never executed
    # at runtime, filename constant, single-tenant server.
    save_chart_svg(c, "/tmp/chart_wheel.svg")  # nosec B108 — dev CLI only
    print("SVG written → /tmp/chart_wheel.svg")
