"""Article banner SVGs (1200×630) — brand-consistent, zero cost, deterministic.

Category → symbol map; dark glass + gold theme matching the site. No external
images, no LLM — instant generation for every article (plan: images for SEO
articles, free tier first; paid FLUX only if user approves)."""

SYMBOLS = {
    "برج‌ها": "♈",
    "آموزش نجوم": "☉",
    "سیارات": "☽",
    "خانه‌ها": "▣",
    "ترانزیت": "➶",
    "سازگاری": "⚭",
    "شغل و موفقیت": "⚖",
    "ماه": "☽",
    "پیش‌بینی": "◈",
}
FALLBACK = "✦"

GRAD = {
    "برج‌ها": ("#1a1530", "#3a2a5e"),
    "آموزش نجوم": ("#101a38", "#1f3a6e"),
    "سیارات": ("#14102a", "#3a1f4a"),
    "خانه‌ها": ("#0f1f2c", "#1f4a5e"),
    "ترانزیت": ("#10142e", "#2a2a5e"),
    "سازگاری": ("#2a1030", "#5e1f4a"),
    "شغل و موفقیت": ("#1c2a10", "#3a5e1f"),
    "ماه": ("#1a1a2a", "#3a3a5e"),
}


def article_banner_svg(category: str, title: str) -> str:
    sym = (SYMBOLS.get(category, FALLBACK) + "\ufe0e")  # \ufe0e = text presentation (no emoji)
    c1, c2 = GRAD.get(category, ("#12102a", "#2a2a5e"))
    t = title[:48]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>
    </linearGradient>
    <radialGradient id="r" cx="0.5" cy="0.45" r="0.6">
      <stop offset="0" stop-color="rgba(212,175,55,.16)"/><stop offset="1" stop-color="rgba(212,175,55,0)"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#g)"/>
  <rect width="1200" height="630" fill="url(#r)"/>
  <circle cx="1010" cy="120" r="180" fill="none" stroke="rgba(212,175,55,.25)" stroke-width="1"/>
  <circle cx="1010" cy="120" r="120" fill="none" stroke="rgba(212,175,55,.18)" stroke-width="1"/>
  <circle cx="140" cy="540" r="150" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="1"/>
  <text x="600" y="170" font-size="150" text-anchor="middle" fill="rgba(212,175,55,.9)" font-family="serif">{sym}</text>
  <line x1="340" y1="360" x2="860" y2="360" stroke="rgba(212,175,55,.5)" stroke-width="2"/>
  <text x="600" y="430" font-size="44" text-anchor="middle" fill="#f4efe2"
        font-family="Vazirmatn, Tahoma, sans-serif" font-weight="700">{t}</text>
  <text x="600" y="500" font-size="26" text-anchor="middle" fill="rgba(232,226,245,.7)"
        font-family="Vazirmatn, Tahoma, sans-serif">چارت تولد — نقشه‌ی آسمان تو</text>
</svg>"""
