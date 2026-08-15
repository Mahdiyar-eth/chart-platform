"""H1.9 — public pages & SEO routes extracted from main.py
(sitemap, robots, learn/sign/articles, guide/about/faq/sky, static pages).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.main import templates

router = APIRouter()


@router.get("/sitemap.xml")
def sitemap_xml():
    import os
    from fastapi.responses import Response
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.negar.io").rstrip("/")
    urls = ["/", "/plans", "/birth-form", "/synastry", "/rectify", "/learn", "/privacy",
            "/terms", "/refund", "/disclaimer", "/contact",
            "/guide", "/about", "/faq", "/articles",
            "/deep-report", "/self-discovery", "/sky-today"]
    try:
        from app.seo.content import GUIDES, PLANETS, HOUSES, SIGNS
        urls += [f"/learn/{k}" for k in GUIDES]
        urls += [f"/learn/{k}" for k in PLANETS]
        urls += [f"/learn/{k}" for k in HOUSES]
        urls += [f"/signs/{s['slug']}" for s in SIGNS.values()]
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


@router.get("/articles", response_class=HTMLResponse)
def page_articles(request: Request):
    from app.main import _load_articles
    arts = _load_articles()
    categories = sorted({a.get("category", "عمومی") for a in arts})
    return templates.TemplateResponse(request, "articles_index.html", {
        "title": "مقالات نجوم و چارت تولد",
        "meta": "مجموعه مقالات آموزشی نجوم، چارت تولد، سیارات، برج‌ها و تحلیل شخصیت — به زبان ساده",
        "articles": arts,
        "categories": categories,
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
    return templates.TemplateResponse(request, "article.html", {
        "title": art["title"], "meta": art.get("meta", ""), "art": art,
        "banner_svg": article_banner_svg(art.get("category", ""), art["title"]),
        "others": [a for a in arts if a["slug"] != slug][:6],
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
