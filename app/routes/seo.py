"""H1.9 — public pages & SEO routes extracted from main.py
(sitemap, robots, learn/sign/articles, guide/about/faq/sky, static pages).
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.main import templates

router = APIRouter()


CITY_PAGES = {
    "tehran": {"city_fa": "تهران", "province_fa": "تهران", "lat": 35.6892, "lon": 51.3890},
    "mashhad": {"city_fa": "مشهد", "province_fa": "خراسان رضوی", "lat": 36.2605, "lon": 59.6168},
    "esfahan": {"city_fa": "اصفهان", "province_fa": "اصفهان", "lat": 32.6546, "lon": 51.6680},
    "shiraz": {"city_fa": "شیراز", "province_fa": "فارس", "lat": 29.5918, "lon": 52.5837},
    "tabriz": {"city_fa": "تبریز", "province_fa": "آذربایجان شرقی", "lat": 38.0800, "lon": 46.2919},
    "karaj": {"city_fa": "کرج", "province_fa": "البرز", "lat": 35.8400, "lon": 50.9391},
    "qom": {"city_fa": "قم", "province_fa": "قم", "lat": 34.6401, "lon": 50.8764},
    "ahvaz": {"city_fa": "اهواز", "province_fa": "خوزستان", "lat": 31.3183, "lon": 48.6706},
    "kermanshah": {"city_fa": "کرمانشاه", "province_fa": "کرمانشاه", "lat": 34.3277, "lon": 47.0778},
    "rasht": {"city_fa": "رشت", "province_fa": "گیلان", "lat": 37.2808, "lon": 49.5832},
}


@router.get("/birth-chart/{slug}", response_class=HTMLResponse)
def birth_chart_city(request: Request, slug: str):
    """G12 (§61) — SEO landing per birth city. Flag-gated (G11) so ops can
    switch the whole city set off pre/post launch without a deploy."""
    from app.feature_flags import flag
    if not flag("seo_cities", "on"):
        raise HTTPException(404, "not found")
    c = CITY_PAGES.get(slug.lower())
    if not c:
        raise HTTPException(404, "not found")
    return templates.TemplateResponse(request, "birth_chart_city.html", {
        "title": f"چارت تولد {c['city_fa']} — دقیق‌ترین محاسبه نجومی آنلاین",
        "city": c, "slug": slug,
        "description": f"چارت تولد {c['city_fa']} را با موتور نجومی محاسبه کن: طالع، خورشید و ماه دقیق با ساعت و مختصات {c['city_fa']} — رایگان و آنلاین.",
    })


@router.get("/moon", response_class=HTMLResponse)
def moon_index(request: Request):
    from app.seo.content import SIGNS
    from app.seo.moon_signs import MOON_SIGNS
    items = []
    for slug, page in MOON_SIGNS.items():
        meta = SIGNS[slug]
        fa_name = meta["title"].split(" ")[1]
        items.append({"slug": slug, "fa": fa_name,
                      "element": meta["element"], "intro": page["intro"][:110] + "…"})
    return templates.TemplateResponse(request, "moon_index.html", {
        "title": "ماه در برج‌ها — معنی جایگاه ماه در چارت تولد",
        "items": items,
        "meta_description": "معنی ماه در ۱۲ برج: احساسات، عشق، کار و راه آرامش. جایگاه ماه چارت تولدت را رایگان کشف کن.",
        "canonical": f"{request.url.scheme}://{request.url.netloc}/moon",
    })


@router.get("/moon-in/{slug}", response_class=HTMLResponse)
def moon_in_sign(request: Request, slug: str):
    from fastapi import HTTPException
    from app.seo.content import SIGNS
    from app.seo.moon_signs import MOON_SIGNS
    page = MOON_SIGNS.get(slug)
    if not page:
        raise HTTPException(404, "not found")
    meta = SIGNS[slug]
    full = dict(page)
    full["element"] = meta["element"]
    full["ruler"] = meta["ruler"]
    fa_name = meta["title"].split(" ")[1]
    full["title"] = f"ماه در {fa_name} — احساسات، عشق و کار"
    neighbors = [{"slug": sl, "fa": SIGNS[sl]["title"].split(" ")[1]}
                 for sl in MOON_SIGNS if sl != slug]
    return templates.TemplateResponse(request, "moon_page.html", {
        "title": full["title"],
        "page": full,
        "neighbors": neighbors,
        "meta_description": (meta.get("keywords") or full["title"]),
        "canonical": f"{request.url.scheme}://{request.url.netloc}/moon-in/{slug}",
    })


@router.get("/sitemap.xml")
def sitemap_xml():
    import os
    from fastapi.responses import Response
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.negar.io").rstrip("/")
    urls = ["/", "/plans", "/birth-form", "/synastry", "/rectify", "/learn", "/privacy",
            "/terms", "/refund", "/disclaimer", "/contact",
            "/guide", "/about", "/faq", "/articles", "/glossary",
            "/deep-report", "/self-discovery", "/sky-today"]
    try:
        from app.seo.content import GUIDES, PLANETS, HOUSES, SIGNS
        urls += [f"/learn/{k}" for k in GUIDES]
        urls += [f"/learn/{k}" for k in PLANETS]
        urls += [f"/learn/{k}" for k in HOUSES]
        urls += [f"/signs/{s['slug']}" for s in SIGNS.values()]
        from app.seo.moon_signs import MOON_SIGNS
        urls.append("/moon")
        urls += [f"/moon-in/{k}" for k in MOON_SIGNS]
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.routes.seo import CITY_PAGES
        urls += [f"/birth-chart/{slug}" for slug in CITY_PAGES]
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.main import _load_articles
        urls += [f"/articles/{a['slug']}" for a in _load_articles()]
    except Exception:  # noqa: BLE001
        pass
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in out:
        body += f'  <url><loc>{base}{u}</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>\n'
    body += "</urlset>\n"
    return Response(content=body, media_type="application/xml")


@router.get("/robots.txt")
def robots_txt():
    import os
    from fastapi.responses import Response
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.negar.io").rstrip("/")
    return Response(content=f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n",
                    media_type="text/plain")


@router.get("/learn", response_class=HTMLResponse)
def learn_index(request: Request):
    from app.seo.content import GUIDES, PLANETS, HOUSES
    return templates.TemplateResponse(request, "seo_index.html", {
        "title": "آموزش چارت تولد — مقالات نجومی",
        "guides": GUIDES, "planets": PLANETS, "houses": HOUSES,
    })


@router.get("/learn/{slug}", response_class=HTMLResponse)
def learn_page(request: Request, slug: str):
    from fastapi import HTTPException
    from app.seo.content import GUIDES, PLANETS, HOUSES, SIGNS
    page = GUIDES.get(slug) or PLANETS.get(slug) or HOUSES.get(slug) or (
        next((s for s in SIGNS.values() if s["slug"] == slug), None))
    if not page:
        raise HTTPException(404, "not found")
    is_sign = slug in (s["slug"] for s in SIGNS.values())
    canonical = f"{request.url.scheme}://{request.url.netloc}/" + \
                (f"signs/{slug}" if is_sign else f"learn/{slug}")
    return templates.TemplateResponse(request, "seo_page.html", {
        "title": page["title"], "page": page, "slug": slug,
        "meta_description": (page.get("keywords") or page.get("title")),
        "canonical": canonical,
    })


@router.get("/signs/{slug}", response_class=HTMLResponse)
def sign_page(request: Request, slug: str):
    from fastapi import HTTPException
    from app.seo.content import SIGNS
    sign = next((s for s in SIGNS.values() if s["slug"] == slug), None)
    if not sign:
        raise HTTPException(404, "not found")
    canonical = f"{request.url.scheme}://{request.url.netloc}/signs/{slug}"
    return templates.TemplateResponse(request, "seo_page.html", {
        "title": sign["title"], "page": sign, "slug": slug,
        "meta_description": sign["keywords"],
        "canonical": canonical,
    })


@router.get("/guide", response_class=HTMLResponse)
def page_guide(request: Request):
    from app.main import _load_pages
    data = _load_pages()["guide"]
    return templates.TemplateResponse(request, "page.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "sections": data["sections"], "hero": data["title"],
    })


@router.get("/about", response_class=HTMLResponse)
def page_about(request: Request):
    from app.main import _load_pages
    data = _load_pages()["about"]
    return templates.TemplateResponse(request, "page.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "sections": data["sections"], "hero": data["title"],
    })


@router.get("/faq", response_class=HTMLResponse)
def page_faq(request: Request):
    from app.main import _load_pages
    data = _load_pages()["faq"]
    cats = data.get("categories") or [{"name": "عمومی", "items": data.get("items", [])}]
    return templates.TemplateResponse(request, "faq.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "categories": cats,
    })


@router.get("/glossary", response_class=HTMLResponse)
def glossary_page(request: Request):
    """R.7 / T2 (F3): linkable glossary of 60+ astrology terms.

    Previously /glossary returned 404 (the plan's F3 workstream was never built).
    Each term has a #anchor and many deep-link to the /learn or /signs pages that
    already exist, so the glossary cross-links without duplicating content.
    """
    from app.seo.glossary import build_glossary
    return templates.TemplateResponse(request, "glossary.html", {
        "title": "واژه‌نامهٔ نجوم و چارت تولد",
        "glossary": build_glossary(),
    })


@router.get("/articles", response_class=HTMLResponse)
def page_articles(request: Request, page: int = 1, cat: str = ""):
    """R13/P2: pagination + category filter — 12 per page instead of one
    endless wall; `cat` filters server-side so links stay shareable."""
    from app.main import _load_articles
    arts = _load_articles()
    categories = sorted({a.get("category", "عمومی") for a in arts})
    if cat:
        arts = [a for a in arts if a.get("category", "عمومی") == cat]
    PER_PAGE = 12
    total = len(arts)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(max(1, page), pages)
    chunk = arts[(page - 1) * PER_PAGE: page * PER_PAGE]
    return templates.TemplateResponse(request, "articles_index.html", {
        "title": "مقالات نجوم و چارت تولد",
        "meta": "مجموعه مقالات آموزشی نجوم، چارت تولد، سیارات، برج‌ها و تحلیل شخصیت — به زبان ساده",
        "articles": chunk,
        "categories": categories,
        "active_cat": cat,
        "page": page,
        "pages": pages,
        "total": total,
        "base_url": "/articles?cat=" + cat if cat else "/articles",
    })


@router.get("/sky", response_class=HTMLResponse)
def page_sky(request: Request):
    from app.astrology.sky import sky_today
    return templates.TemplateResponse(request, "sky.html", {
        "title": "آسمان امروز — فاز ماه، موقعیت سیارات و جنبه‌های آسمانی",
        "meta": "موقعیت امروز سیارات، فاز ماه، جنبه‌های آسمانی و رجوعی‌ها — با توضیح ساده و تخصصی برای خودشناسی و تأمل",
        "sky": sky_today(),
    })


# ── P9 — landing pages (plan v2.0 §14: Landing 2/3/4) ───────────────────────
@router.get("/deep-report", response_class=HTMLResponse)
def landing_deep_report(request: Request):
    return templates.TemplateResponse(request, "landing.html", {
        "h1": "فقط یک چارت نبین؛ بفهم چه چیزهایی در آن مهم‌اند.",
        "sub": "گزارش عمیق زایچه هر ۱۳ حوزه‌ی زندگی را با شواهد نجومی باز می‌کند — کدام سیاره، کدام خانه، کدام زاویه. نه ادعای کلی، نه جمله‌های مبهم.",
        "cta": "گزارش عمیق من را شروع کن", "cta_href": "/birth-form?redirect=/plans",
        "cta_note": "اول چارت رایگان بساز، بعد گزارش را انتخاب کن",
        "chips": ["۱۳+ بخش", "شاهد نجومی برای هر بینش", "PDF و Word", "نسخه‌ی صوتی", "گفت‌وگو با هوش مصنوعی (طلایی)"],
        "cards": [
            {"icon": "book-open", "title": "شخصیت، ذهن، احساسات، رابطه، شغل و بیشتر",
             "body": "هر حوزه در یک بخش جدا با عمق کافی؛ به‌جای یک پاراگراف کلی، چندین صفحه تحلیل اختصاصی روی چارتِ خودت."},
            {"icon": "compass", "title": "هر بینش با شاهد نجومی",
             "body": "«این بخش در چارت تو بیشتر دیده می‌شود چون مریخ در خانه‌ی دهم و در زاویه با زحل است» — قابل ردیابی، قابل فهم."},
            {"icon": "book", "title": "PDF ۲۵+ صفحه و Word",
             "body": "گزارش را دانلود کن، چاپ کن یا در موبایل ذخیره کن. نسخه‌ی صوتی هم برای شنیدن در مسیر."},
        ],
        "faq": "آیا این پیشگویی است؟ نه. گزارش زایچه ادعای پیش‌بینی ندارد؛ الگوهای چارت را به زبان ساده توضیح می‌دهد تا خودت تصمیم‌های آگاهانه‌تری بگیری.",
    })


@router.get("/self-discovery", response_class=HTMLResponse)
def landing_self_discovery(request: Request):
    return templates.TemplateResponse(request, "landing.html", {
        "h1": "سؤال‌های سخت درباره‌ی خودت را ساده شروع کن.",
        "sub": "نیازی به دانش نجوم نیست. چارت تولدت را بساز و با سؤال‌های ساده شروع کن — هر پاسخ با شواهد نجومی چارتِ خودت.",
        "cta": "کاوش خودم را شروع کن", "cta_href": "/birth-form?redirect=/explore",
        "cta_note": "اولین کاوش رایگان است",
        "chips": ["اولین کاوش رایگان", "پاسخ با شواهد چارت", "بدون دانش قبلی"],
        "cards": [
            {"icon": "chat", "title": "چرا بعضی الگوها در زندگی‌ام تکرار می‌شوند؟",
             "body": "کاوش الگوها به تو نشان می‌دهد کدام ترکیب‌های سیاره‌ای در چارتت پررنگ‌اند و چرا."},
            {"icon": "heart", "title": "در روابط چه الگویی دارم؟",
             "body": "الگوی عاطفی، نیازها و واکنش‌هایت در رابطه — از دید ترکیب ماه، زهره و خانه‌های مربوط."},
            {"icon": "sun", "title": "مسیر شغلی مناسب من چیست؟",
             "body": "نقاط قوت قابل اتکا، سبک کاری و انگیزه‌ی واقعی‌ات — از خورشید، خانه‌ی دهم و سیارات مرتبط."},
            {"icon": "compass", "title": "نقاط قوت واقعی من چیست؟",
             "body": "نه تعریف کلی، بلکه ترکیب دقیق سیاره‌ها و خانه‌ها در چارت خودت."},
            {"icon": "refresh", "title": "چه چیزی رشد مرا کند می‌کند؟",
             "body": "الگوهای چالشی چارت — با زبان همدلانه و راهنمای عمل، نه ترساندن."},
        ],
        "faq": "هر کاوش چقدر طول می‌کشد؟ حدود یک دقیقه. پاسخ‌ها کوتاه، شاهددار و بر اساس محاسبه‌ی دقیق نجومی چارتِ خودت هستند.",
    })


@router.get("/sky-today", response_class=HTMLResponse)
def landing_sky_today(request: Request):
    return templates.TemplateResponse(request, "landing.html", {
        "h1": "هر روز یک لحظه برای دیدن آسمان و دیدن خودت.",
        "sub": "آسمان امروز: فاز ماه، موقعیت سیارات و جنبه‌های مهم امروز — به‌علاوه‌ی ارتباط هر کدام با چارتِ خودت، یک تأمل کوتاه و یک اقدام کوچک.",
        "cta": "آسمان امروز را ببین", "cta_href": "/sky",
        "cta_note": "رایگان — بدون ثبت‌نام",
        "chips": ["فاز ماه", "موقعیت سیارات", "ارتباط با چارتت", "تأمل روزانه"],
        "cards": [
            {"icon": "moon", "title": "امروز آسمان چه می‌گوید",
             "body": "فاز ماه و جنبه‌های اصلی امروز — به زبان ساده، با درجه و زمان دقیق."},
            {"icon": "compass", "title": "این برای چارتِ تو چه معنی دارد",
             "body": "گذرهای مهم نسبت به جایگاه سیاره‌های خودت — کدام بخش از زندگی‌ات این روزها فعال‌تر است."},
            {"icon": "book-open", "title": "یک تأمل و یک اقدام",
             "body": "هر روز یک سؤال کوتاه برای تأمل و یک قدم کوچک عملی — نه دستور، نه پیش‌گویی."},
        ],
        "faq": "آیا این پیش‌بینی روزانه است؟ نه. «آسمان امروز» یک نگاه آموزشی-تأملی است: فاز ماه و گذرها را توضیح می‌دهد، نه اینکه چه اتفاقی برایت می‌افتد.",
    })



@router.get("/articles/{slug}", response_class=HTMLResponse)
def page_article(slug: str, request: Request):
    from fastapi import HTTPException
    from app.main import _load_articles
    from app.seo.article_banner import article_banner_svg
    arts = _load_articles()
    art = next((a for a in arts if a["slug"] == slug), None)
    if not art:
        raise HTTPException(404, "article not found")
    # B-3 (F1 audit): related links must be TOPIC-related, not arbitrary. Prefer
    # same-category siblings (up to 6) so a reader following "مقالات مرتبط" stays
    # on-topic; only fall back to other categories when the category is too sparse.
    _cat = art.get("category", "")
    others = [a for a in arts if a["slug"] != slug and a.get("category") == _cat]
    if len(others) < 3:  # category too thin → pad with other topics (still relevant by order)
        others += [a for a in arts if a["slug"] != slug and a.get("category") != _cat]
    others = others[:6]
    # R.8 / S3: deep-link the first occurrence of glossary terms in the body so a
    # reader can jump to the definition (plan F3: «هر اصطلاح در اولین ظهور شرح داشته باشد»).
    # The body is admin-authored (trusted, CMS) and link_glossary_terms only wraps a
    # fixed term string in a safe `<a href="/glossary#…">`. We mark the RESULTing
    # paragraphs as Markup (after linking, since string slicing would drop Markup),
    # so Jinja doesn't autoescape the anchor tags.
    from markupsafe import Markup
    from app.seo.glossary import link_glossary_terms
    body = link_glossary_terms(art.get("body") or [])
    body = [
        ({**b, "p": Markup(b["p"])} if ("p" in b and isinstance(b["p"], str)) else b)
        for b in body
    ]
    art = {**art, "body": body}
    return templates.TemplateResponse(request, "article.html", {
        "title": art["title"], "meta": art.get("meta", ""), "art": art,
        "banner_svg": article_banner_svg(art.get("category", ""), art["title"]),
        "others": others,
    })


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {"title": "حریم خصوصی"})


@router.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html", {"title": "قوانین استفاده"})


@router.get("/refund", response_class=HTMLResponse)
def refund_page(request: Request):
    return templates.TemplateResponse(request, "refund.html", {"title": "شرایط استرداد"})


@router.get("/disclaimer", response_class=HTMLResponse)
def disclaimer_page(request: Request):
    return templates.TemplateResponse(request, "disclaimer.html", {"title": "سلب مسئولیت"})


@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse(request, "contact.html", {"title": "تماس با ما"})
