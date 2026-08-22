"""Chart Platform — FastAPI app (Phase 2: free product).

Routes: landing, birth form, chart compute (sync), chart page, city search.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from pydantic import BaseModel
from contextlib import asynccontextmanager
from hmac import compare_digest
from pathlib import Path

import redis.asyncio as redis_async

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from sqlalchemy import text

import app.config  # noqa: F401 — load .env FIRST
from app.env import IS_PROD
from app.auth import get_current_user
from app.security import security_guard, chat_quota_claim, chat_quota_release, chat_quota_used
from app.astrology.big_three import big_three
from app.astrology.cities_ir import search_cities
from app.astrology.engine import compute_from_fields
from app.astrology.svg_wheel import render_chart_svg
from app.bots.handler import TELEGRAM_WEBHOOK_SECRET, handle_update
from app.chat.service import chat_answer
from app.db import engine, get_session, init_db
from fastapi.responses import JSONResponse
from app.entitlements import has as ent_has, grant_from_order as ent_grant_order, grant_from_credits as ent_grant_credits
from app.credits import balance, get_price, UnknownAction
from app.models import (AuditLog, BirthProfile, Chart, ChatMessage, Coupon, Exploration, FunnelEvent, LLMRun, Order, Plan,
                        ReferralCode, ReferralEvent, Report, ReportChunk, Subscription,
                        User, WeeklyReflection, WithdrawalRequest,)
from app import secret_store

BALE_WEBHOOK_SECRET = secret_store.get_secret("bale_webhook_secret", "BALE_WEBHOOK_SECRET", "")
from datetime import datetime, timezone
from app.payment.zarinpal import ZarinpalClient, ZarinpalError

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def _asset_version():
    """Cache-busting version from the css dir hash (design tokens/base/components)."""
    import hashlib
    d = BASE_DIR / "static" / "css"
    if not d.is_dir():
        return "0"
    h = hashlib.md5()
    for f in sorted(d.iterdir()):
        if f.suffix == ".css":
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:10]

templates.env.globals["asset_version"] = _asset_version()


# D2 (plan §7): single-source navigation, state-aware per request
from app.nav import nav_for as _nav_for




PLANS_SEED = [
    Plan(key="basic", name_fa="پایه", subtitle_fa="آغاز شناخت",
         price_toman=149_000, sort=1, active=True,
         features=["چارت تولد تعاملی + SVG", "سهگانهی اصلی (خورشید، ماه، طالع)",
                   "۵ بخش اصلی گزارش", "دانلود PDF"]),
    Plan(key="full", name_fa="کامل", subtitle_fa="گزارش ۱۳ بخشی اختصاصی",
         price_toman=349_000, sort=2, active=True,
         features=["همهی امکانات پایه", "گزارش کامل ۱۳ حوزهی زندگی",
                   "تحلیل جنبهها و خانهها", "دانلود PDF ۲۵+ صفحهای"]),
    Plan(key="gold", name_fa="طلایی", subtitle_fa="شناخت عمیق + پشتیبانی",
         price_toman=699_000, sort=3, active=True,
         features=["همه‌ی امکانات کامل", "گفت‌وگو با هوش مصنوعی (۵ سوال در روز)",
                   "به‌روزرسانی‌های آینده رایگان", "اولویت در صف تولید"]),
    # P6 — credit packs (phase G): 3/6/12 credits
    Plan(key="credit3", name_fa="۳ اعتبار", subtitle_fa="سه کاوش خودشناسی",
         price_toman=180_000, sort=4, active=True, credits_grant=3,
         features=["هر کاوش = ۱ اعتبار", "بدون تاریخ انقضا", "اعتبار باقی می‌ماند"]),
    Plan(key="credit6", name_fa="۶ اعتبار", subtitle_fa="شش کاوش خودشناسی",
         price_toman=330_000, sort=5, active=True, credits_grant=6,
         features=["ارزش ۲۰٪ بیشتر از پک ۳تایی", "بدون تاریخ انقضا", "اعتبار باقی می‌ماند"]),
    Plan(key="credit12", name_fa="۱۲ اعتبار", subtitle_fa="دوازده کاوش خودشناسی",
         price_toman=600_000, sort=6, active=True, credits_grant=12,
         features=["بهترین ارزش — ۲۰٪ ارزان‌تر از ۳+۳+۶", "بدون تاریخ انقضا", "اعتبار باقی می‌ماند"]),
    # H — همراه ماهانه/سالانه (plan v2.0 §11): Today + weekly + transit notif + 5 credits/mo
    Plan(key="monthly", name_fa="اشتراک ماهانه", subtitle_fa="همراه ماهانه‌ی زایچه — برای دنبال‌کنندگان آسمان",
         price_toman=99_000, sort=7, active=True,
         features=["نگاهی به آسمان امروز (Today) — هر روز", "تأمل هفتگی کوتاه", "اعلان گذرهای مهم",
                   "۵ اعتبار کاوش در هر ماه"]),
    Plan(key="yearly", name_fa="اشتراک سالانه", subtitle_fa="همراه سالانه — دو ماه هدیه",
         price_toman=890_000, sort=8, active=True,
         features=["همه‌ی امکانات ماهانه", "۲ ماه رایگان (به‌جای ۱۲ ماه، ۱۰ ماه پرداخت)", "اعلان گذرهای مهم",
                   "۵ اعتبار کاوش در هر ماه"]),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # expire_on_commit=False: committing must NOT expire the module-level
    # PLANS_SEED instances — tests access them directly after boot and would
    # otherwise hit DetachedInstanceError on an expired attribute.
    with Session(engine, expire_on_commit=False) as s:
        for p in PLANS_SEED:
            if s.get(Plan, p.key) is None:
                s.add(p)
        s.commit()
    yield
    await _close_arq_pool()


_APP_ENV = os.getenv("APP_ENV", "dev").lower()
app = FastAPI(title="چارت تولد", lifespan=lifespan,
              docs_url=None if _APP_ENV in ("prod", "production") else "/docs",
              openapi_url=None if _APP_ENV in ("prod", "production") else "/openapi.json")
app.middleware("http")(security_guard)   # security.py: CSRF origin check + rate limits
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.middleware("http")
async def _nav_state_middleware(request: Request, call_next):
    """D1/D2 — resolve visitor state once; expose the state-aware nav dict to all templates."""
    request.state.has_chart = False
    try:
        from app.auth import get_current_user
        u = get_current_user(request)
        if u:
            from sqlmodel import select as _sel
            with Session(engine) as _s:
                pids = _s.exec(_sel(BirthProfile.id).where(
                    BirthProfile.user_id == u.id)).all()
                if pids:
                    found = _s.exec(_sel(Chart.id).where(
                        Chart.profile_id.in_(pids))).first()
                    request.state.has_chart = bool(found)
    except Exception:
        pass
    request.state.nav = _nav_for(has_chart=request.state.has_chart)
    response = await call_next(request)
    # E4 — baseline security headers (defense in depth; nginx may also set HSTS)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
    response.headers.setdefault(
        "Content-Security-Policy-Report-Only",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self' https://analytics.negar.io",
    )
    return response



def _safe_json(obj, ensure_ascii: bool = False, **kw) -> str:
    """JSON for embedding in <script> via |safe — escapes </script> and -->
    breakout (F-08 family, 2026-08-17): user/model data JSON must never be
    able to close a script tag from inside a template.
    (2026-08-21) accept ensure_ascii= kwarg — several callers pass it and it
    was crashing `/explore` with TypeError."""
    import json as _json
    return _json.dumps(obj, ensure_ascii=ensure_ascii, **kw).replace("</", "<\\/").replace("<!--", "<\\!--")


@app.get("/sw.js")
def sw_file():
    """Service worker at ROOT scope (PWA — plan §13.9)."""
    from fastapi.responses import FileResponse
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@app.get("/liveness")
def liveness():
    """C5 (audit r4): pure process heartbeat — no dependencies. A running
    process answers 200 even if DB/Redis/R2 are all down (orchestrator
    restarts only on readiness failure)."""
    return JSONResponse({"status": "alive"})


@app.get("/readiness")
def readiness():
    """C5 (audit r4): full dependency probe — DB + Redis + worker + R2 + disk.
    Returns 503 while ANY dependency is down; the UI degraded banner keys off
    this (plan §health)."""
    from sqlalchemy import text
    out: dict = {"status": "ok"}
    code = 200
    # 1) DB
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        out["db"] = "ok"
    except Exception:  # noqa: BLE001
        out["db"] = "down"
        code = 503
    # 2) Redis (rate-limit backend in prod — REQUIRED)
    try:
        import redis as _r
        if not _r.Redis.from_url(_REDIS_URL, decode_responses=True).ping():
            raise RuntimeError("no pong")
        out["redis"] = "ok"
    except Exception:  # noqa: BLE001
        out["redis"] = "down"
        code = 503
    # 3) ARQ worker (report generation runs off-process)
    try:
        import asyncio as _asyncio
        _asyncio.run(_arq_pool())
        out["worker"] = "ok"
    except Exception:  # noqa: BLE001
        out["worker"] = "down"
        code = 503
    # 4) R2 configured (fail-closed in prod — B4)
    from app.storage import configured as _r2_configured
    out["r2"] = "ok" if _r2_configured() else "unconfigured"
    if not _r2_configured() and IS_PROD:
        out["r2"] = "down"
        code = 503
    # 5) disk headroom (watchdog threshold is 85%)
    try:
        import shutil
        free_gb = shutil.disk_usage("/").free / 2 ** 30
        out["disk_free_gb"] = round(free_gb, 1)
        if free_gb < 1.0:  # <1GB free → not ready
            out["disk"] = "critical"
            code = 503
        else:
            out["disk"] = "ok"
    except Exception:  # noqa: BLE001
        out["disk"] = "unknown"
    out["status"] = "ok" if code == 200 else "degraded"
    return JSONResponse(out, status_code=code)


@app.get("/health")
def health_check():
    """Backward-compatible alias of /readiness (audit P2-7)."""
    return readiness()


# ─────────────────────────── pages ───────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing(request: Request, ref: str = ""):
    resp = templates.TemplateResponse(request, "index.html", {"title": "چارت تولد — آینهی خودشناسی", "ref": ref})
    if ref and len(ref) <= 20:
        resp.set_cookie("chart_ref", ref, max_age=7 * 86400, httponly=True, samesite="lax", secure=True)
    return resp


@app.get("/birth-form", response_class=HTMLResponse)
def birth_form_page(request: Request):
    return templates.TemplateResponse(request, "form.html", {"title": "فرم تولد"})


@app.get("/chart/{chart_id}", response_class=HTMLResponse)
def chart_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):
        # P0 IDOR fix: bare UUID must never grant access to birth data.
        return RedirectResponse("/birth-form?e=private", status_code=303)
    bt = big_three(chart.chart_json)
    svg = render_chart_svg(chart.chart_json)
    from app.astrology.svg_widgets import aspect_grid_svg, element_donut_svg, house_bar_svg
    planets = chart.chart_json.get("planets", {})
    houses = {}
    sign_counts = {}
    for _p in planets.values():
        _h = _p.get("house")
        if _h:
            houses[_h] = houses.get(_h, 0) + 1
        _s = _p.get("sign_fa", "")
        if _s:
            sign_counts[_s] = sign_counts.get(_s, 0) + 1   # audit P1-6: real counts per sign
    # G2: guests must be nudged to claim the chart (top funnel-leak fix)
    from app.auth import get_current_user as _gcu
    is_guest = _gcu(request) is None
    return templates.TemplateResponse(request, "chart.html", {
        "title": "چارت تولد", "chart": chart, "big_three": bt, "svg": svg,
        "aspect_grid": aspect_grid_svg(planets),
        "element_donut": element_donut_svg(sign_counts),
        "house_bar": house_bar_svg(houses),
        "access_token": chart.access_token or "",
        "is_guest": is_guest,
    })



@app.post("/api/subscribe")
def api_subscribe(request: Request, contact: str = Form(...), source: str = Form("guide"),
                  session: Session = Depends(get_session)):
    """G3 — lead magnet/newsletter signup. Explicit consent recorded; rate-limited upstream."""
    import re as _re
    contact = contact.strip()
    channel = "email" if "@" in contact else "sms"
    if channel == "sms" and not _re.fullmatch(r"09\d{9}", contact):
        raise HTTPException(422, "[ZAY-SUB-001] شماره موبایل معتبر نیست (۰۹xxxxxxxxx)")
    if channel == "email" and not _re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact):
        raise HTTPException(422, "[ZAY-SUB-002] ایمیل معتبر نیست")
    from app.models import Subscriber
    token = secrets.token_urlsafe(24)
    sub = Subscriber(contact=contact, channel=channel, source=source, token=token)
    session.add(sub)
    session.commit()
    resp = JSONResponse({"ok": True, "download_url": f"/guide/download/{token}"})
    return resp


@app.get("/gift-guide", response_class=HTMLResponse)
def gift_guide_page(request: Request):
    """G3 — lead-magnet landing: PDF رایگان پشت یک فیلد تماس."""
    return templates.TemplateResponse(request, "guide_landing.html", {"title": "راهنمای رایگان چارت تولد"})


@app.get("/guide/download/{token}")
def guide_download(token: str, request: Request, session: Session = Depends(get_session)):
    """One-time-ish gated download (token issued on subscribe)."""
    from app.models import Subscriber
    sub = session.exec(select(Subscriber).where(Subscriber.token == token)).first()
    if not sub:
        raise HTTPException(404, "لینک نامعتبر است")
    path = "/root/chart-platform/app/static/guides/zayche-guide.pdf"
    if not os.path.exists(path):
        raise HTTPException(404, "فایل راهنما یافت نشد")
    return FileResponse(path, media_type="application/pdf", filename="zayche-guide.pdf")


@app.get("/unsubscribe/{token}")
def unsubscribe(token: str, request: Request, session: Session = Depends(get_session)):
    """G3 — mandatory one-click unsubscribe."""
    from app.models import Subscriber
    sub = session.exec(select(Subscriber).where(Subscriber.token == token)).first()
    if sub and sub.unsubscribed_at is None:
        sub.unsubscribed_at = datetime.now(timezone.utc)
        session.add(sub)
        session.commit()
    return HTMLResponse("<meta charset='utf-8'><body style='font-family:sans-serif;text-align:center;padding:60px'>لغو اشتراک انجام شد. دیگر پیامی دریافت نمی‌کنی.</body>")


# ─────────────────────────── api ───────────────────────────

@app.get("/api/cities")
def api_cities(q: str = Query(default="", max_length=50), limit: int = 10):
    """Iran + world city search (H0.1): Iranian cities keep province_fa;
    world cities carry country + tz so the form can pass coords."""
    from app.astrology.cities_world import search_cities_world
    results = search_cities(q, limit)
    if not results:
        results = [{"province_fa": c["country"], "city_fa": c["name"],
                    "lat": c["lat"], "lon": c["lon"], "country": c["country"],
                    "tz": c["tz"]} for c in search_cities_world(q, limit)]
    else:
        for r in results:
            r["country"] = "ایران"
    return {"results": results}


@app.post("/api/charts")
def api_create_chart(
    request: Request,
    session: Session = Depends(get_session),
    calendar: str = Form("jalali"),
    year: int = Form(...),
    month: int = Form(...),
    day: int = Form(...),
    time_known: bool = Form(False),
    hour: int | None = Form(None),
    minute: int | None = Form(None),
    city_fa: str | None = Form(None),
    province_fa: str | None = Form(None),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    name: str = Form(""),
    zodiac: str = Form("tropical"),  # tropical | sidereal (Vedic / Lahiri)
    focus_areas: str | None = Form(None),  # comma-separated
    personal_question: str | None = Form(None),
):
    """Compute chart (sync, fast) + cache. Returns chart_id."""
    # audit r4 B5: chart creation is the compute-heavy entry point — 20/min per client
    if not _rate_limit(f"chart:{_rl_client(request)}", 20, 60):
        raise HTTPException(429, "درخواستهای زیادی ثبت کردید؛ یک دقیقه صبر کنید")
    chart, profile = _compute_and_save_chart(
        session, request,
        calendar=calendar, year=year, month=month, day=day,
        time_known=time_known, hour=hour, minute=minute,
        city_fa=city_fa, province_fa=province_fa, lat=lat, lon=lon,
        name=name, zodiac=zodiac, focus_areas=focus_areas,
        personal_question=personal_question,
    )
    session.add(chart)
    session.commit()
    session.refresh(chart)
    resp = JSONResponse({
        "chart_id": chart.id,
        "profile_id": profile.id,
        "access_token": chart.access_token,
        "utc": chart.chart_json["birth"]["utc_time"],
        "engine_config": chart.chart_json["engine_config"],
        "tz_name": chart.chart_json["birth"].get("tz_name", "Asia/Tehran"),  # H0.1
    })
    # remember ownership for anonymous (and logged-in) browsers (P0-1)
    tokens = _chart_tokens(request)
    if chart.access_token:
        tokens[chart.id] = chart.access_token
        resp.set_cookie(CHART_ACCESS_COOKIE, json.dumps(tokens),
                        max_age=365 * 86400, httponly=True, samesite="lax",
                        secure=True)
    return resp


def _compute_and_save_chart(
    session: Session, request: Request,
    calendar: str, year: int, month: int, day: int,
    time_known: bool, hour: int | None, minute: int | None,
    city_fa: str | None, province_fa: str | None,
    lat: float | None, lon: float | None,
    name: str, zodiac: str, focus_areas: str | None = None,
    personal_question: str | None = None,
    user_id: str | None = None, guest: bool = False,
) -> tuple[Chart, BirthProfile]:
    """Shared chart computation + persistence (charts API, synastry orders, bots)."""
    if calendar not in ("jalali", "gregorian"):
        raise HTTPException(400, "calendar must be jalali|gregorian")
    if zodiac not in ("tropical", "sidereal"):
        raise HTTPException(400, "zodiac must be tropical|sidereal")
    if year < 1300 or year > 2100:
        raise HTTPException(400, "year out of range")
    # audit P1-9: sanitize free-text inputs that flow into the LLM prompt
    name = (name or "").strip()[:60]
    focus_areas = (focus_areas or "").strip()[:120]
    personal_question = (personal_question or "").strip()[:500]

    if lat is None or lon is None:
        city = search_cities(city_fa or "", 1)
        if not city:
            raise HTTPException(400, "city not found")
        lat, lon = city[0]["lat"], city[0]["lon"]
        province_fa = province_fa or city[0]["province_fa"]

    profile = BirthProfile(
        calendar_system=calendar,
        raw_year=year, raw_month=month, raw_day=day,
        time_known=time_known, hour=hour, minute=minute,
        city_fa=city_fa, province_fa=province_fa, lat=lat, lon=lon,
        name=name, zodiac=zodiac,
        focus_areas=[a.strip() for a in (focus_areas or "").split(",") if a.strip()],
        personal_question=personal_question or None,
        user_id=(None if guest else
                 (user_id or (get_current_user(request).id if get_current_user(request) else None))),
    )
    assert lat is not None and lon is not None
    try:
        from app.astrology.cities_world import is_iran_coords, tz_from_coords
        tz_name = tz_from_coords(lat, lon)  # H0.1: real IANA tz, not hardcoded
        # F-06 (audit v5 P1): never silently compute a non-Iranian chart with
        # Asia/Tehran — the whole chart would be off by hours. Tehran fallback
        # is allowed ONLY inside Iran; otherwise ask for a valid city.
        if tz_name is None:
            if is_iran_coords(lat, lon):
                tz_name = "Asia/Tehran"
            else:
                raise HTTPException(400,
                                    "منطقهٔ زمانی این مختصات در دسترس نیست — لطفاً شهر را انتخاب کنید")
        result = compute_from_fields(
            lat=lat, lon=lon, year=year, month=month, day=day,
            hour=hour if time_known else 12,
            minute=minute if time_known else 0,
            time_known=time_known, jalali=(calendar == "jalali"),
            tz_name=tz_name, zodiac=zodiac,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    from datetime import datetime as _dt
    profile.utc_datetime = _dt.strptime(result.chart_json["birth"]["utc_time"], "%Y-%m-%d %H:%M:%S")
    session.add(profile)
    session.flush()
    chart = Chart(profile_id=profile.id, chart_json=result.chart_json,
                  engine_config=result.chart_json["engine_config"],
                  access_token=secrets.token_urlsafe(32))
    return chart, profile


# ─────────────────────────── report (Phase 3) ───────────────────────────

CHART_ACCESS_COOKIE = "chart_access"  # {chart_id: token} — anonymous ownership (P0-1)


def _chart_tokens(request: Request) -> dict:
    raw = request.cookies.get(CHART_ACCESS_COOKIE, "")
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _owns_chart(chart: Chart | None, session: Session, request: Request) -> bool:
    """Ownership = authenticated user_id OR cryptographically-strong capability
    token (audit P0-1). A bare UUID alone must never grant access."""
    if not chart:
        return False
    # 1) registered-owner path
    if chart.profile_id:
        prof = session.get(BirthProfile, chart.profile_id)
        if prof and prof.user_id:
            u = get_current_user(request)
            return bool(u and u.id == prof.user_id)
    # 2) anonymous capability-token path
    if chart.access_token:
        supplied = request.query_params.get("t") or _chart_tokens(request).get(chart.id)
        return bool(supplied and compare_digest(supplied, chart.access_token))
    return False


def _report_gate(rep, session, request) -> bool:
    """Gate: entitlement (per-report) OR legacy paid order + ownership.

    A3 (user decision, per-report): the credit entitlement is tied to ref_id =
    rep.id, so buying one report can't unlock another. Legacy paid orders are
    still accepted so no current customer loses access during the migration.
    F-17 (audit v7 P1): the paid order must be the one that OWNS this report.
    """
    u = get_current_user(request)
    uid = u.id if u else None
    chart = session.get(Chart, rep.chart_id)
    if uid:
        ent = ent_has(session, uid, "report", ref_id=rep.id)
        if ent:
            return _owns_chart(chart, session, request)
    # legacy paid-order path (migration compat)
    paid = session.exec(
        select(Order).where(Order.report_id == rep.id, Order.status == "paid")
    ).first()
    if paid:
        if uid and paid.user_id == uid:
            ent_grant_order(session, paid)  # backfill entitlement once
        return _owns_chart(chart, session, request)
    return False


def _owns_order(order, session, request) -> bool:
    """Order ownership = owns the order's chart (audit P2-1)."""
    if not order:
        return False
    return _owns_chart(session.get(Chart, order.chart_id), session, request)


_REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_ARQ_POOL = None  # shared ARQ pool (created lazily on first enqueue)


async def _arq_pool():
    """Shared ARQ pool (audit P1: pool-per-request was wasteful)."""
    global _ARQ_POOL
    if _ARQ_POOL is None:
        from arq import create_pool
        from arq.connections import RedisSettings
        _ARQ_POOL = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
    return _ARQ_POOL


async def _close_arq_pool():
    global _ARQ_POOL
    if _ARQ_POOL is not None:
        try:
            await _ARQ_POOL.aclose()
        except Exception:  # noqa: BLE001
            pass
        _ARQ_POOL = None


def _enqueue_report(report_id: str) -> bool:
    """Enqueue ARQ job via the shared pool; False if Redis/worker unavailable."""
    try:
        import asyncio
        asyncio.run(_enqueue_async(report_id))
        return True
    except Exception:  # noqa: BLE001
        return False


async def _enqueue_async(report_id: str) -> None:
    """Enqueue one ARQ job with a short-lived pool.

    F-25 (runtime audit): a GLOBAL pool created inside asyncio.run() binds to
    whichever worker-thread loop created it first; the next request runs in a
    different thread → ``attached to a different loop`` → "queue unavailable".
    A fresh pool per enqueue costs ~ms and is thread-safe by construction.
    """
    from arq import create_pool
    from arq.connections import RedisSettings
    pool = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
    try:
        await pool.enqueue_job("generate_report", report_id)
    finally:
        await pool.aclose()


@app.post("/api/charts/{chart_id}/report")
def api_create_report(chart_id: str, request: Request,
                      session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    # ownership (P0-1): only the owner (user_id or capability token) may trigger
    if not _owns_chart(chart, session, request):
        raise HTTPException(403, "[ZAY-REPORT-003] برای تولید گزارش، ابتدا پلن را خریداری کنید")
    # plan v3.0 §8/§12: report generation happens AFTER payment — plan_key drives section set
    paid = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    if not paid:
        raise HTTPException(403, "[ZAY-REPORT-003] برای تولید گزارش، ابتدا پلن را خریداری کنید")
    # audit r4 A7: report generation is IDEMPOTENT — repeated clicks must not
    # enqueue multiple LLM jobs. queued/processing → return existing;
    # done/degraded → return existing unless ?regenerate=1; failed → re-queue.
    # F-07 (audit v5 P1): serialize concurrent requests for the same chart
    # with a transaction-scoped advisory lock — the plain SELECT-then-INSERT
    # let two simultaneous POSTs both see existing=None and enqueue two LLM jobs.
    session.exec(text("SELECT pg_advisory_xact_lock(hashtext(:ck))")
                 .bindparams(ck=f"report:{chart_id}"))
    regenerate = request.query_params.get("regenerate") == "1"
    existing = session.exec(
        select(Report).where(Report.chart_id == chart_id)
        .order_by(Report.created_at.desc())
    ).first()
    if existing and not regenerate:
        if existing.status in ("queued", "processing"):
            return {"report_id": existing.id, "status": existing.status,
                    "queued": True, "plan_key": existing.plan_key, "existing": True}
        if existing.status in ("done", "degraded"):
            return {"report_id": existing.id, "status": existing.status,
                    "queued": False, "plan_key": existing.plan_key, "existing": True}
        if existing.status == "failed":
            existing.status = "queued"
            existing.error = None
            session.commit()
            ok = _enqueue_report(existing.id)
            if not ok:
                existing.status = "failed"
                existing.error = "queue unavailable (worker not running)"
                session.commit()
            return {"report_id": existing.id, "status": existing.status,
                    "queued": ok, "plan_key": existing.plan_key, "existing": True}
    rep = Report(chart_id=chart_id, status="queued", plan_key=paid.plan_key or "full")
    session.add(rep)
    session.commit()
    session.refresh(rep)
    ok = _enqueue_report(rep.id)
    if not ok:
        rep.status = "failed"
        rep.error = "queue unavailable (worker not running)"
        session.commit()
    return {"report_id": rep.id, "status": rep.status, "queued": ok, "plan_key": rep.plan_key}


@app.get("/api/charts/{chart_id}/preview")
async def api_chart_preview(chart_id: str, request: Request, session: Session = Depends(get_session)):
    """Free 3-5 insights — deterministic baseline, enriched with a cheap LLM
    (deepseek-flash flat-subscription) when available, cached in Redis to avoid
    repeat spend. Falls back to the deterministic one-liners on any failure."""
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):
        raise HTTPException(403, "not authorized")
    from app.report.preview import enrich_insights_async, free_insights
    insights = free_insights(chart.chart_json)
    cache_key = f"enriched:{chart_id}"

    async def _cache_get() -> dict | None:
        try:
            r = redis_async.from_url(_REDIS_URL, decode_responses=True)
            raw = await r.get(cache_key)
            await r.aclose()
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _cache_set(val: dict) -> None:
        try:
            r = redis_async.from_url(_REDIS_URL, decode_responses=True)
            await r.set(cache_key, json.dumps(val, ensure_ascii=False), ex=7 * 86400)
            await r.aclose()
        except Exception:
            pass

    cached = await _cache_get()
    if cached and isinstance(cached.get("insights"), list):
        cached["cached"] = True
        return cached
    if os.getenv("ENRICH_INSIGHTS", "1") == "0":
        return insights  # enrichment disabled (tests / config)
    try:
        enriched = await asyncio.wait_for(
            enrich_insights_async(chart.chart_json, insights), timeout=7.0)
        if enriched:
            await _cache_set(enriched)
            return enriched
    except Exception:
        pass
    return insights


@app.get("/api/charts/{chart_id}/transit-year.svg")
def api_transit_year_svg(chart_id: str, request: Request, session: Session = Depends(get_session)):
    """Annual transit timeline widget (plan §9.3) — deterministic, no LLM."""
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):
        raise HTTPException(403, "not authorized")
    from app.astrology.svg_widgets import transit_timeline_svg
    from fastapi.responses import Response
    return Response(transit_timeline_svg(chart.chart_json), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/charts/{chart_id}/report")
def api_report_status(chart_id: str, request: Request, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):
        raise HTTPException(403, "not authorized")
    rep = session.exec(
        select(Report).where(Report.chart_id == chart_id).order_by(Report.created_at.desc())
    ).first()
    if not rep:
        return {"report_id": None, "status": "none"}
    return {
        "report_id": rep.id,
        "status": rep.status,
        "error": rep.error,
        "metrics": rep.metrics,
        "sections_count": len(rep.sections or {}),
        "pdf_url": f"/api/reports/{rep.id}/pdf" if rep.status in ("done", "degraded") else None,
    }


@app.get("/api/reports/{report_id}.docx")
def api_report_docx(report_id: str, request: Request,
                    session: Session = Depends(get_session)):
    rep = session.get(Report, report_id)
    if not rep or rep.status not in ("done", "degraded"):
        raise HTTPException(404, "report not ready")
    # gate: paid order + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "[ZAY-REPORT-003] برای دانلود گزارش، ابتدا خرید کنید")
    from app.report.word import report_to_docx
    title = "گزارش اختصاصی چارت تولد"
    sections = {k: {"title": (v or {}).get("title", k), "content": (v or {}).get("content", "")}
                for k, v in (rep.sections or {}).items()}
    data = report_to_docx({"title": title, "intro": "گزارش اختصاصی چارت تولد — تولید شده توسط موتور نجومی Swiss Ephemeris", "sections": sections})
    from fastapi.responses import Response
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename=chart-report-{report_id[:8]}.docx"})


@app.get("/api/reports/{report_id}/pdf")
def api_report_pdf(report_id: str, request: Request,
                   session: Session = Depends(get_session)):
    rep = session.get(Report, report_id)
    if not rep or rep.status not in ("done", "degraded") or not rep.pdf_path:
        raise HTTPException(404, "report not ready")
    # gate: paid order on this chart + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "[ZAY-REPORT-003] برای دانلود گزارش، ابتدا خرید کنید")
    from app.storage import presigned_url
    r2_url = presigned_url(rep.r2_key) if rep.r2_key else None
    if r2_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(r2_url, status_code=302)
    from fastapi.responses import FileResponse
    return FileResponse(rep.pdf_path, media_type="application/pdf",
                        filename=f"report-{report_id[:8]}.pdf")


# ─────────────────────────── commercial (Phase 4) ───────────────────────────

@app.get("/plans", response_class=HTMLResponse)
def plans_page(request: Request, session: Session = Depends(get_session)):
    plans = session.exec(select(Plan).where(Plan.active).order_by(Plan.sort)).all()
    return templates.TemplateResponse(request, "plans.html", {
        "title": "تعرفهها", "plans": plans,
    })


@app.get("/payment/result", response_class=HTMLResponse)
def payment_result_page(request: Request, order_id: str,
                        session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if not _owns_order(order, session, request):
        raise HTTPException(403, "دسترسی غیرمجاز")
    plan = session.get(Plan, order.plan_key) if order.plan_key else None
    ref_url = ""
    u = get_current_user(request)
    if u and order.status == "paid":
        from app.payment.orders import get_or_create_referral_code
        ref_url = (os.getenv('PUBLIC_BASE_URL', 'https://chart.negar.io')
                   + "/?ref=" + get_or_create_referral_code(session, u.id))
    return templates.TemplateResponse(request, "payment_result.html", {
        "title": "نتیجه‌ی پرداخت", "order": order, "plan": plan, "ref_url": ref_url,
    })


@app.get("/api/plans")
def api_plans(session: Session = Depends(get_session)):
    plans = session.exec(select(Plan).where(Plan.active).order_by(Plan.sort)).all()
    return [{"key": p.key, "name_fa": p.name_fa, "subtitle_fa": p.subtitle_fa,
             "price_toman": p.price_toman, "features": p.features} for p in plans]


class PurchasePayload(BaseModel):
    action_key: str
    chart_id: str | None = None


@app.post("/api/purchase")
def api_purchase(payload: "PurchasePayload", request: Request,
                 session: Session = Depends(get_session)):
    """A4 — unified credit purchase (single endpoint for every gated action).

    No login -> 401 login_required. Insufficient credits -> 402 with
    {needed, have, packs}. Success -> grant_from_credits -> {ok, entitlement_id}.
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"login_required": True, "next": "/plans"})
    try:
        price = get_price(session, payload.action_key)
    except UnknownAction:
        return JSONResponse(status_code=400, content={"error": "unknown_action"})
    have = balance(session, user.id)
    if have < price:
        packs = session.exec(
            select(Plan).where(
                Plan.active == True,  # noqa: E712
                Plan.key.in_(["credit3", "credit6", "credit12"]),
            )
        ).all()
        return JSONResponse(status_code=402, content={
            "needed": price, "have": have,
            "packs": [{"key": p.key, "name_fa": p.name_fa,
                       "credits": p.credits_grant, "price_toman": p.price_toman}
                      for p in packs],
        })
    ent = ent_grant_credits(
        session, user.id, payload.action_key,
        idempotency_key=f"purchase:{user.id}:{payload.action_key}:{payload.chart_id or 'none'}",
        chart_id=payload.chart_id,
    )
    return {"ok": True, "entitlement_id": ent.id, "remaining": balance(session, user.id)}


@app.get("/api/credits/me")
def api_credits_me(request: Request, session: Session = Depends(get_session)):
    """A4: current user credit balance (401 if not logged in).
    Drives the appbar credit chip + credit_cta.
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "login required")
    return {"balance": balance(session, user.id), "currency": "credit"}


def claim_anonymous_charts(session, user, cap):
    """A5 (F-37) — link an anonymous (guest) chart to a freshly-logged-in user.

    Ownership lives on the BirthProfile (`profile.user_id`), NOT the Chart. A
    guest chart has a profile with `user_id IS NULL`; claiming sets it to the
    new user. Idempotent (re-running is a no-op) and NEVER claims a chart whose
    profile already has an owner (a different user's chart is never stolen)."""
    if not cap or not user:
        return 0
    uid = user.id if hasattr(user, "id") else user
    chart = session.exec(select(Chart).where(Chart.access_token == cap)).first()
    if not chart or chart.access_token != cap or not chart.profile_id:
        return 0
    prof = session.get(BirthProfile, chart.profile_id)
    if not prof or prof.user_id:  # already owned -> never claim (idempotent + no steal)
        return 0
    prof.user_id = uid
    session.add(prof)
    session.commit()
    return 1


@app.post("/api/orders")
def api_create_order(
    request: Request,
    plan_key: str = Form(...),
    chart_id: str | None = Form(None),
    coupon: str | None = Form(None),
    secondary_chart_id: str | None = Form(None),
    chat_id: str | None = Form(None),
    platform: str | None = Form(None),
    session: Session = Depends(get_session),
):
    """Create order + payment URL (shared helper — also used by bots)."""
    # A5 (F3): account enforcement applies to the CREDIT path (/api/purchase,
    # already login-required). Retiring guest checkout on /api/orders is deferred
    # pending explicit user confirmation (would break 11 guest-purchase tests).
    user = get_current_user(request)
    from app.payment.orders import create_order, CREDIT_PACKS
    chart = session.get(Chart, chart_id) if chart_id else None
    if chart_id and not chart:
        raise HTTPException(404, "chart not found")
    if chart and not _owns_chart(chart, session, request):  # audit r4 A5: order ownership
        raise HTTPException(403, "not authorized")
    if not chart and plan_key not in CREDIT_PACKS:
        raise HTTPException(400, "[ZAY-PAY-001] برای این پلن ابتدا چارت بسازید")
    if secondary_chart_id:
        sec = session.get(Chart, secondary_chart_id)
        if not sec or not _owns_chart(sec, session, request):
            raise HTTPException(403, "not authorized")
    # F-20 (audit v8 P2): in the wallet path, fail FAST before creating the
    # order — no pending order + coupon reservation is left behind when the
    # balance can't cover the payable amount. The estimate applies the coupon
    # discount (and referral 10%) so a user whose balance covers the
    # DISCOUNTED final amount is not rejected (audit v9 residual fix).
    if request.headers.get("x-pay-with-balance", "") == "1":
        _plan = session.get(Plan, plan_key)
        est = (_plan.price_rial or 0) if _plan else 0
        if est and coupon:
            _cp = session.exec(
                select(Coupon).where(Coupon.code == coupon.strip().upper())
            ).first()
            if _cp and _cp.active:
                est = max(1, int(est * (100 - _cp.percent) / 100))
        elif est and not coupon and request.cookies.get("chart_ref"):
            est = max(1, int(est * 0.9))  # referral estimate; real check in create_order
        if not user or not _plan or (user.balance_rial or 0) < est:
            raise HTTPException(400, "[ZAY-PAY-001] موجودی کیف پول کافی نیست")
    try:
        order, pay_url = create_order(
            session, plan_key, chart_id or "",
            secondary_chart_id=secondary_chart_id, chat_id=chat_id, platform=platform,
            coupon=coupon, ref_code=request.cookies.get("chart_ref", ""),
            new_user_id=user.id if user else None,
        )
        # D3: settle from wallet when the user chose it and has enough balance
        if request.headers.get("x-pay-with-balance", "") == "1":
            from app.payment.orders import pay_order_with_balance
            if not pay_order_with_balance(session, order, user):
                # F-20: immediate compensation — cancel the order and release
                # the coupon RIGHT NOW instead of waiting for the hourly sweep
                order.status = "cancelled"
                if order.coupon_id:
                    _release_coupon(session, order)
                session.commit()
                raise HTTPException(400, "[ZAY-PAY-001] موجودی کیف پول کافی نیست")
            pay_url = None
            # F-03 (audit v5 P1): wallet-paid report must be ENQUEUED, exactly
            # like the Zarinpal callback path — otherwise the Report row stays
            # 'queued' forever (no cron sweeps queued rows).
            if order.report_id:
                rep = session.get(Report, order.report_id)
                if rep and rep.status == "queued":
                    if not _enqueue_report(rep.id):
                        rep.status = "failed"
                        rep.error = "queue unavailable at payment time — از ادمین بازتولید کنید"
                        session.add(rep)
                        session.commit()
    except LookupError:
        raise HTTPException(404, "plan not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"order_id": order.id, "payment_url": pay_url, "authority": order.authority,
            "paid_by_balance": pay_url is None}


@app.get("/api/orders/{order_id}")
def api_order_status(order_id: str, request: Request,
                     session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if not _owns_order(order, session, request):
        raise HTTPException(403, "forbidden")
    return {"order_id": order.id, "status": order.status, "ref_id": order.ref_id,
            "report_id": order.report_id}


def _release_coupon(session: Session, order) -> None:
    """audit r4 A10: undo a coupon reservation (failed payment / refund /
    stale order). Keeps used_count honest so slots are never lost."""
    if order and order.coupon_id:
        c = session.get(Coupon, order.coupon_id)
        if c and c.used_count > 0:
            c.used_count -= 1


@app.get("/api/subscriptions")
def api_my_subscriptions(request: Request, session: Session = Depends(get_session)):
    """H — list the caller's active subscriptions across their charts."""
    from app.timeutil import ensure_utc, utcnow
    from app.payment.orders import SUBSCRIPTION_MONTHLY_CREDITS
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "not logged in")
    profile_ids = [p.id for p in session.exec(
        select(BirthProfile).where(BirthProfile.user_id == user.id)).all()]
    chart_ids = [c.id for c in session.exec(
        select(Chart).where(Chart.profile_id.in_(profile_ids))).all()] if profile_ids else []
    subs = session.exec(select(Subscription).where(
        Subscription.chart_id.in_(chart_ids)).order_by(Subscription.created_at.desc())
    ).all() if chart_ids else []
    now = utcnow()
    return [{
        "id": s.id, "chart_id": s.chart_id, "plan_key": s.plan_key,
        "active": s.active and (s.expires_at is None or ensure_utc(s.expires_at) > now),
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "monthly_credits": SUBSCRIPTION_MONTHLY_CREDITS,
    } for s in subs]


@app.get("/api/coupons/check")
def api_coupon_check(code: str = Query(default=""), request: Request = None,
                     session: Session = Depends(get_session)):
    """§13 — validate a coupon WITHOUT consuming it; report_only coupons also
    check the caller's first-deep-report eligibility."""
    from app.payment.orders import REPORT_PLANS
    from app.timeutil import ensure_utc, utcnow
    cp = session.exec(select(Coupon).where(Coupon.code == code.strip().upper())).first()
    if not cp or not cp.active:
        raise HTTPException(404, "کد تخفیف نامعتبر است")
    if cp.expires_at and ensure_utc(cp.expires_at) < utcnow():
        raise HTTPException(400, "کد تخفیف منقضی شده")
    if cp.used_count >= cp.max_uses:
        raise HTTPException(400, "کد تخفیف مصرف شده")
    scope = "اولین گزارش عمیق" if cp.report_only else "همه‌ی پلن‌ها"
    if cp.report_only:
        user = get_current_user(request)
        if user:
            prior = session.exec(select(Order).where(
                Order.user_id == user.id, Order.status == "paid",
                Order.plan_key.in_(REPORT_PLANS))).first()
            if prior:
                raise HTTPException(400, "این کد فقط برای اولین گزارش عمیق است")
    return {"code": cp.code, "percent": cp.percent, "scope": scope}


@app.post("/api/subscriptions/{sub_id}/cancel")
def api_cancel_subscription(sub_id: str, request: Request,
                            session: Session = Depends(get_session)):
    """H — cancellation: entitlement ends immediately."""
    from app.payment.orders import cancel_subscription
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "not logged in")
    sub = session.get(Subscription, sub_id)
    if not sub:
        raise HTTPException(404, "subscription not found")
    ch = session.get(Chart, sub.chart_id) if sub.chart_id else None
    owner = None
    if ch and ch.profile_id:
        prof = session.get(BirthProfile, ch.profile_id)
        owner = prof.user_id if prof else None
    if owner != user.id:
        raise HTTPException(403, "not authorized")
    cancel_subscription(session, sub)
    return {"ok": True, "id": sub.id}


@app.get("/api/payments/verify")
def api_payment_verify(
    request: Request,
    Authority: str = Query(default=""),
    Status: str = Query(default=""),
    session: Session = Depends(get_session),
):
    """Zarinpal callback — verify + mark order paid, then redirect to result page."""
    order = session.exec(select(Order).where(Order.authority == Authority)).first()
    if not order:
        raise HTTPException(404, "order not found for authority")

    # idempotency (audit P0-1): duplicate callback / refresh must NOT re-verify,
    # re-extend subscription or re-consume coupon — already-paid orders just redirect.
    if order.status == "paid":
        return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)

    if Status == "OK":
        # Atomic claim (audit r3 — payment race): only ONE of N concurrent
        # duplicate callbacks may transition pending→verifying; the losers
        # redirect. audit r4 B7 state machine: pending → verifying → paid |
        # failed, and NETWORK errors re-open (pending) instead of failing —
        # money may have moved even though our verify() call died.
        from sqlalchemy import text as _text
        claimed = session.exec(_text(
            "UPDATE orders SET status = 'verifying' WHERE id = :oid AND status = 'pending' RETURNING id"
        ), params={"oid": order.id}).first()
        if not claimed:
            # another request already claimed/paid this order → just redirect
            return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)
        client = ZarinpalClient()
        try:
            v = client.verify(Authority, order.amount_rial)
            order.ref_id = v["ref_id"]
            order.card_pan = v.get("card_pan")
            from datetime import datetime, timezone
            order.paid_at = datetime.now(timezone.utc)
            order.status = "paid"
            # Coupon was RESERVED atomically at order creation (audit r4 A10) —
            # nothing to consume here; idempotency holds because the
            # pending→verifying claim above runs at most once per order.
            # monthly subscription: activate + extend 30 days (plan §7)
            from app.payment.orders import REPORT_PLANS, activate_subscription, CREDIT_PACKS, grant_credits, SUBSCRIPTION_PLANS, grant_subscription_credits
            if order.plan_key in SUBSCRIPTION_PLANS:
                activate_subscription(session, order)
                sub = session.exec(
                    select(Subscription).where(
                        Subscription.chart_id == order.chart_id,
                        Subscription.chat_id == (order.chat_id if order.chat_id else None),
                    )
                ).first()
                if sub:
                    grant_subscription_credits(session, sub)  # H — first month granted on purchase
            # P6 — credit packs: grant credits atomically + ledger row
            if order.plan_key in CREDIT_PACKS:
                grant_credits(session, order)
            # auto-generate report for report plans (basic/full/gold — NOT synastry/sub)
            if order.plan_key in REPORT_PLANS and order.chart_id and not order.report_id:
                rep = Report(chart_id=order.chart_id, status="queued",
                             plan_key=order.plan_key)
                session.add(rep)
                session.flush()
                order.report_id = rep.id
            session.commit()
            # enqueue AFTER commit (audit P0-2): worker must see the committed row;
            # if queue is unavailable, mark failed so admin "regenerate" can retry.
            if order.report_id:
                rep = session.get(Report, order.report_id)
                if rep and rep.status == "queued":
                    if not _enqueue_report(rep.id):
                        rep.status = "failed"
                        rep.error = "queue unavailable at payment time — از ادمین بازتولید کنید"
                        session.add(rep)
                        session.commit()
            # F-12 (audit v6 P1): reward the referrer AFTER the settlement
            # commit — a referral failure must NEVER roll the payment back
            # (money already moved at the gateway; rolling back here would
            # leave the order unpaid while the report still generates).
            try:
                from app.payment.orders import reward_referral
                reward_referral(session, order)
                session.commit()
            except Exception:  # noqa: BLE001 — referral is best-effort
                session.rollback()
        except ZarinpalError:
            # gateway definitively rejected the payment (authority invalid /
            # expired / transaction refused) — money did NOT move → failed
            order.status = "failed"
            _release_coupon(session, order)  # audit r4 A10
            session.commit()
        except Exception as e:  # noqa: BLE001 — network/timeout: money state UNKNOWN
            # audit r4 B7: NEVER mark failed when the payment may have gone
            # through — put the order back to pending so the user's refresh
            # (or a retry) re-verifies; Zarinpal answers code 101 on repeat
            # verifies, which lands in the paid branch above.
            # NOTE: the claim set status='verifying' via RAW SQL — the ORM still
            # holds 'pending' in memory, so assigning 'pending' back would look
            # like "no change" and never flush. Expire first so the ORM re-reads.
            session.expire(order, ["status"])
            order.status = "pending"
            order.error = f"تأیید پرداخت موقتاً ناموفق بود؛ صفحه را رفرش کنید: {str(e)[:150]}"
            session.commit()
    else:
        order.status = "failed"
        _release_coupon(session, order)  # audit r4 A10
        session.commit()

    return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)


# ── SEO / public pages (H1.9 → app/routes/seo.py) ────────────────────────────


@app.get("/api/share/{chart_id}.png")
def api_share_card(chart_id: str, request: Request,
                   session: Session = Depends(get_session)):
    if not _rate_limit(f"share:{_rl_client(request)}", 15, 60):
        raise HTTPException(429, "درخواست زیاد است")
    """OG share card (1200×630) — rendered + cached on first request."""
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.share.card import render_share_card
    from fastapi.responses import FileResponse
    path = render_share_card(chart.chart_json, chart_id)
    return FileResponse(path, media_type="image/png")


# ── admin API (H1.9 → app/routes/admin.py) ───────────────────────────────────

@app.get("/synastry", response_class=HTMLResponse)
def synastry_page(request: Request):
    return templates.TemplateResponse(request, "synastry.html", {"title": "سازگاری دو چارت"})


@app.post("/api/synastry")
def api_synastry(request: Request, session: Session = Depends(get_session),
                 name_a: str = Form(""), year_a: int = Form(...), month_a: int = Form(...),
                 day_a: int = Form(...), hour_a: int = Form(12), minute_a: int = Form(0),
                 city_a: str = Form(None), calendar_a: str = Form("jalali"),
                 zodiac_a: str = Form("tropical"),
                 name_b: str = Form(""), year_b: int = Form(...), month_b: int = Form(...),
                 day_b: int = Form(...), hour_b: int = Form(12), minute_b: int = Form(0),
                 city_b: str = Form(None), calendar_b: str = Form("jalali"),
                 zodiac_b: str = Form("tropical")):
    if not _rate_limit(f"synastry:{_rl_client(request)}", 10, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    """Free teaser (plan §8): score + verdict only. Full analysis is a paid product."""
    from app.astrology.synastry import synastry
    from app.astrology.cities_world import resolve_tz_safe
    city_a = search_cities(city_a or "", 1)
    city_b = search_cities(city_b or "", 1)
    if not city_a or not city_b:
        raise HTTPException(400, "شهرها را انتخاب کنید")
    ca = compute_from_fields(float(city_a[0]["lat"]), float(city_a[0]["lon"]), year_a, month_a, day_a,
                             hour_a, minute_a, True, calendar_a == "jalali",
                             resolve_tz_safe(float(city_a[0]["lat"]), float(city_a[0]["lon"])) or "Asia/Tehran", zodiac=zodiac_a)
    cb = compute_from_fields(float(city_b[0]["lat"]), float(city_b[0]["lon"]), year_b, month_b, day_b,
                             hour_b, minute_b, True, calendar_b == "jalali",
                             resolve_tz_safe(float(city_b[0]["lat"]), float(city_b[0]["lon"])) or "Asia/Tehran", zodiac=zodiac_b)
    r = synastry(ca.chart_json, cb.chart_json)
    return {
        "a": name_a or "شخص اول", "b": name_b or "شخص دوم",
        "score": r["overall"], "verdict": r["verdict"], "free": True, "full_locked": True,
    }


@app.post("/api/insight/share")
def api_insight_share(request: Request, kind: str = Form("insight"),
                      title: str = Form(""), headline: str = Form(""),
                      date_fa: str = Form("")):
    """A8 — viral share for Daily Insight / Weekly / Transit cards (mirrors G7).
    Guest page shows ONLY headline + title — no birth data."""
    import hmac as _hmac, hashlib
    from app.auth import _AUTH_SECRET
    if kind not in ("insight", "weekly", "transit"):
        raise HTTPException(400, "[ZAY-PAY-001] درخواست نامعتبر")
    payload = f"{kind}|{title[:120]}|{headline[:400]}|{date_fa[:40]}"
    tok = _hmac.new(_AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return {"url": f"/si/{tok}?p={payload.replace('|', '%7C')}"}


@app.get("/si/{token}", response_class=HTMLResponse)
def insight_share_page(request: Request, token: str, p: str = Query("")):
    """Guest preview for shared insight/transit card (rate-limited, no leak)."""
    if not _rate_limit(f"share:{_rl_client(request)}", 30, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    import hmac as _hmac, hashlib
    from app.auth import _AUTH_SECRET
    parts = p.split("|")
    if len(parts) != 4:
        raise HTTPException(404, "not found")
    kind, title, headline, date_fa = parts
    payload = f"{kind}|{title}|{headline}|{date_fa}"
    expect = _hmac.new(_AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    if not _hmac.compare_digest(expect.encode(), token.encode()):
        raise HTTPException(404, "not found")
    return templates.TemplateResponse(request, "insight_share.html", {
        "title": "بینش نجومی — زایچه",
        "kind": kind, "headline": headline, "date_fa": date_fa or title,
    })


@app.post("/api/synastry/share")
def api_synastry_share(request: Request, name_a: str = Form(""), name_b: str = Form(""),
                       score: int = Form(...), verdict: str = Form(...)):
    """G7 (§18) — viral share: mint a signed, short-lived guest link showing
    ONLY score + verdict (no birth data, no locations, no names beyond what
    the sharer typed). Guest page carries a signup CTA."""
    if not 0 <= score <= 100 or len(verdict) > 400:
        raise HTTPException(400, "[ZAY-PAY-001] درخواست نامعتبر")
    payload = f"{name_a[:40]}|{name_b[:40]}|{score}|{verdict[:400]}"
    import hmac as _hmac, hashlib
    from app.auth import _AUTH_SECRET
    tok = _hmac.new(_AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return {"url": f"/s/{tok}?p={payload.replace('|', '%7C')}"}


@app.get("/s/{token}", response_class=HTMLResponse)
def synastry_share_page(request: Request, token: str, p: str = Query("")):
    """Guest preview for a shared synastry result (rate-limited, no data leak)."""
    if not _rate_limit(f"share:{_rl_client(request)}", 30, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    import hmac as _hmac, hashlib
    from app.auth import _AUTH_SECRET
    parts = p.split("|")
    if len(parts) != 4:
        raise HTTPException(404, "not found")
    name_a, name_b, score_s, verdict = parts
    payload = f"{name_a}|{name_b}|{score_s}|{verdict}"
    expect = _hmac.new(_AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    if not _hmac.compare_digest(expect.encode(), token.encode()):
        raise HTTPException(404, "not found")
    try:
        score = int(score_s)
    except ValueError:
        raise HTTPException(404, "not found")
    return templates.TemplateResponse(request, "synastry_share.html", {
        "title": "نتیجه سازگاری — زایچه",
        "name_a": name_a or "شخص اول", "name_b": name_b or "شخص دوم",
        "score": score, "verdict": verdict,
    })


@app.post("/api/synastry/order")
def api_synastry_order(request: Request, session: Session = Depends(get_session),
                       name_a: str = Form(""), year_a: int = Form(...), month_a: int = Form(...),
                       day_a: int = Form(...), hour_a: int = Form(12), minute_a: int = Form(0),
                       city_a: str = Form(None), calendar_a: str = Form("jalali"),
                       zodiac_a: str = Form("tropical"),
                       name_b: str = Form(""), year_b: int = Form(...), month_b: int = Form(...),
                       day_b: int = Form(...), hour_b: int = Form(12), minute_b: int = Form(0),
                       city_b: str = Form(None), calendar_b: str = Form("jalali"),
                       zodiac_b: str = Form("tropical")):
    """Save both charts + create the paid synastry order (plan §8, ~499k toman).

    H1.6: Person B is a GUEST profile (user_id=NULL, no account required) —
    only the buyer's chart A lands in their account; B's birth data is stored
    as an anonymous profile reachable solely via its capability token."""
    from app.payment.orders import create_order
    chart_a, profile_a = _compute_and_save_chart(
        session, request, calendar=calendar_a, year=year_a, month=month_a, day=day_a,
        time_known=True, hour=hour_a, minute=minute_a, city_fa=city_a,
        province_fa=None, lat=None, lon=None, name=name_a, zodiac=zodiac_a)
    chart_b, profile_b = _compute_and_save_chart(
        session, request, calendar=calendar_b, year=year_b, month=month_b, day=day_b,
        time_known=True, hour=hour_b, minute=minute_b, city_fa=city_b,
        province_fa=None, lat=None, lon=None, name=name_b, zodiac=zodiac_b,
        guest=True)  # H1.6: guest — anonymous BirthProfile + capability token
    session.add(chart_a); session.add(chart_b)
    session.commit(); session.refresh(chart_a); session.refresh(chart_b)
    user = get_current_user(request)
    try:
        order, pay_url = create_order(
            session, "synastry", chart_a.id, secondary_chart_id=chart_b.id,
            coupon=None, ref_code="", new_user_id=user.id if user else None,
        )
    except (LookupError, ValueError, RuntimeError) as e:
        # F-19 (audit v8 P1): failure compensation — the payment order could
        # not be created, so the JUST-CREATED charts/profiles (including the
        # anonymous Person B, which has NO user owner and therefore NO other
        # deletion path) must not be left orphaned in the DB.
        try:
            session.rollback()  # drop the uncommitted order first (it holds an FK to chart A)
            session.delete(chart_a)
            session.delete(chart_b)
            session.flush()
            session.delete(profile_a)
            session.delete(profile_b)
            session.commit()
        except Exception as _e:  # noqa: BLE001
            # F-19 residual (audit v9 P1): cleanup MUST be fail-closed — if
            # the compensation itself fails, the guest Person B data may be
            # orphaned with NO deletion path. Surface a 5xx (NOT the original
            # 400) so the operator sees the incomplete state instead of the
            # user silently walking away with leftover private data.
            try:
                session.rollback()
                from app.security import audit
                audit(session.bind, "system", "synastry.cleanup_failed",
                      chart_a.id, f"compensation failed: {_e!r} — charts/profiles may be orphaned")
            except Exception:
                pass
            raise HTTPException(502, "خطای داخلی: دادههای سیناستری پاک نشد — با پشتیبانی تماس بگیرید")
        raise HTTPException(400, str(e))
    return {"order_id": order.id, "payment_url": pay_url,
            "chart_a": chart_a.id, "chart_b": chart_b.id,
            "token_b": chart_b.access_token}  # H1.6: guest capability token


@app.post("/api/synastry/full")
def api_synastry_full(request: Request, session: Session = Depends(get_session),
                      chart_a: str = Form(...), chart_b: str = Form(...)):
    """Full synastry report — requires OWNING both charts AND a paid synastry order (audit r4 A4)."""
    from app.astrology.synastry import synastry
    ca = session.get(Chart, chart_a)
    cb = session.get(Chart, chart_b)
    if not ca or not cb:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(ca, session, request) or not _owns_chart(cb, session, request):
        raise HTTPException(403, "not authorized")
    paid = session.exec(
        select(Order).where(
            Order.plan_key == "synastry", Order.status == "paid",
            Order.chart_id == chart_a, Order.secondary_chart_id == chart_b,
        )
    ).first()
    if not paid:
        raise HTTPException(403, "[ZAY-PAY-001] برای مشاهدهی تحلیل کامل، ابتدا سیناستری را خریداری کنید")
    return synastry(ca.chart_json, cb.chart_json)


@app.get("/api/synastry/access")
def api_synastry_access(chart_a: str, chart_b: str, request: Request, session: Session = Depends(get_session)):
    ca = session.get(Chart, chart_a)
    cb = session.get(Chart, chart_b)
    if not ca or not cb:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(ca, session, request) or not _owns_chart(cb, session, request):
        raise HTTPException(403, "not authorized")
    u = get_current_user(request)
    uid = u.id if u else None
    if uid and ent_has(session, uid, "synastry", chart_id=chart_a):
        return {"full": True}
    paid = session.exec(
        select(Order).where(
            Order.plan_key == "synastry", Order.status == "paid",
            Order.chart_id == chart_a, Order.secondary_chart_id == chart_b,
        )
    ).first()
    return {"full": bool(paid)}


@app.get("/rectify", response_class=HTMLResponse)
def rectify_page(request: Request):
    return templates.TemplateResponse(request, "rectify.html", {"title": "یافتن ساعت تولد"})


@app.post("/api/rectify")
def api_rectify(request: Request, city_fa: str = Form(...), year: int = Form(...), month: int = Form(...),
                day: int = Form(...), calendar: str = Form("jalali"),
                events_json: str = Form(...)):  # [["marriage",2019,6,12], ...]
    if not _rate_limit(f"rectify:{_rl_client(request)}", 6, 300):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    import json as _json
    from app.astrology.rectify import rectify_birth_time
    city = search_cities(city_fa, 1)
    if not city:
        raise HTTPException(400, "شهر پیدا نشد")
    try:
        events = [_json.loads(x) if isinstance(x, str) else x for x in _json.loads(events_json)]
        events = [(e[0], int(e[1]), int(e[2]), int(e[3])) for e in events if len(e) >= 4]
    except Exception:
        raise HTTPException(400, "فرمت رویدادها نامعتبر است")
    if not events:
        raise HTTPException(400, "حداقل یک رویداد لازم است")
    r = rectify_birth_time(city[0]["lat"], city[0]["lon"], year, month, day, events,
                           jalali=calendar == "jalali")
    return {"best_time": r.best_time, "score": r.score, "candidates": r.candidates,
            "events_used": r.events_used, "details": r.details}


@app.get("/api/reports/{report_id}/audio")
def api_report_audio(report_id: str, request: Request,
                     session: Session = Depends(get_session)):
    """H1.5: audio download — ready → 302 presigned; generating/failed → 409
    with the status so the client polls /audio-status instead of hanging."""
    rep = session.get(Report, report_id)
    if not rep or rep.status not in ("done", "degraded"):
        raise HTTPException(404, "report not ready")
    # gate: paid order + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "[ZAY-REPORT-003] برای دریافت فایل صوتی، ابتدا خرید کنید")
    from app.storage import audio_key, presigned_url
    if rep.audio_status == "ready" and rep.audio_r2_key:
        cached = presigned_url(audio_key(report_id))
        if cached:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(cached, status_code=302)
    raise HTTPException(409, f"audio {rep.audio_status or 'none'}")


@app.post("/api/reports/{report_id}/audio")
def api_report_audio_request(report_id: str, request: Request,
                             session: Session = Depends(get_session)):
    """H1.5: request (queued) audio — enqueue an ARQ job when not already
    generating/ready. Returns {status} — 200 when ready (with url), 202 when
    generating, 409 when failed (retry allowed by re-POSTing)."""
    rep = session.get(Report, report_id)
    if not rep or rep.status not in ("done", "degraded"):
        raise HTTPException(404, "report not ready")
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "[ZAY-REPORT-003] برای دریافت فایل صوتی، ابتدا خرید کنید")
    from app.storage import audio_key, presigned_url
    if rep.audio_status == "ready" and rep.audio_r2_key:
        cached = presigned_url(audio_key(report_id))
        if cached:
            return {"status": "ready", "url": cached}
    if rep.audio_status == "generating":
        return {"status": "generating"}
    if rep.audio_status == "failed":
        # allow one retry — flip back to none so the worker re-generates
        rep.audio_status = "none"
        session.commit()
    # enqueue (redis path; failure surfaces as 503 — never inline TTS)
    try:
        import asyncio as _a
        _a.run(_enqueue_audio(report_id))
    except Exception:  # noqa: BLE001 — redis down → surface 503, allow retry
        rep.audio_status = "failed"
        session.commit()
        raise HTTPException(503, "صف تولید صوت در دسترس نیست؛ دوباره تلاش کنید")
    rep.audio_status = "generating"
    session.commit()
    return {"status": "generating"}


def _enqueue_audio(report_id: str) -> object:
    """Synchronous bridge to enqueue the audio job (no async endpoint)."""
    import asyncio

    async def _do():
        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
        try:
            await pool.enqueue_job("generate_report_audio", report_id)
        finally:
            await pool.aclose()

    return asyncio.run(_do())


@app.get("/api/reports/{report_id}/audio-status")
def api_report_audio_status(report_id: str, request: Request,
                            session: Session = Depends(get_session)):
    """H1.5: lightweight poll target for the client (no 409 semantics)."""
    rep = session.get(Report, report_id)
    if not rep:
        raise HTTPException(404, "not found")
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "forbidden")
    from app.storage import audio_key, presigned_url
    if rep.audio_status == "ready" and rep.audio_r2_key:
        url = presigned_url(audio_key(report_id))
        return {"status": "ready", "url": url}
    return {"status": rep.audio_status or "none"}


# ── learn/sign/articles — H1.9 → app/routes/seo.py ───────────────────────────


# ─────────────────────────── SEO (Phase 8) ───────────────────────────


@app.get("/chat/{chart_id}", response_class=HTMLResponse)
def chat_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):
        # audit P0 (round 3): chat exposes a private conversation — same gate as /chart
        return RedirectResponse("/birth-form?e=private", status_code=303)
    # G6 (§16): dynamically relevant quick chips from the canonical chart
    presets = [
        "الگوی روابط من چیست؟",
        "نقاط قوت شخصیتی من چیست؟",
        "در مسیر شغلی چه چیزهایی برجسته است؟",
        "چطور بهتر خودم را بشناسم؟",
        "این ترانزیت برای من چه معنای تأملی دارد؟",
    ]
    dynamic = []
    try:
        bt = big_three(chart.chart_json)
        for label, key in (("خورشید", "Sun"), ("ماه", "Moon"), ("طالع", "ASC")):
            val = (bt.get(key) or {}).get("sign_en") if isinstance(bt.get(key), dict) else None
            if val:
                dynamic.append(f"{label} من در {val} است؛ این برای من چه معنایی دارد؟")
    except Exception:
        dynamic = []
    return templates.TemplateResponse(request, "chat.html", {
        "title": "گفت‌وگو با چارت", "chart_id": chart_id,
        "presets": presets + dynamic[:2],
    })


def _chat_account_key(chart, order, request) -> str:
    """Per-ACCOUNT quota scope (audit r4 A8 — marketing/product decision):
    registered users share one daily pool across ALL their charts; bot
    identities share per chat; anonymous fall back to the chart capability."""
    user = get_current_user(request)
    if user:
        return f"u:{user.id}"
    if order and order.chat_id:
        return f"b:{order.platform or 'telegram'}:{order.chat_id}"
    return f"c:{chart.id}"


def _chat_daily_limit(order) -> int:
    """Gold=5/day, monthly=15/day (admin-overridable via secrets table)."""
    limit_key = "chat_daily_limit_gold" if order.plan_key == "gold" else "chat_daily_limit_monthly"
    default = "5" if order.plan_key == "gold" else "15"
    try:
        return int(secret_store.get_secret(limit_key, limit_key.upper(), default))
    except ValueError:
        return int(default)


def _chat_quota_info(session: Session, chart_id: str, order, account_key: str | None = None) -> dict:
    """Daily quota display for a chart's AI chat (gold vs monthly)."""
    daily_limit = _chat_daily_limit(order)
    if account_key:
        used = chat_quota_used(account_key)
        if used is not None:
            return {"used": used, "limit": daily_limit, "remaining": max(0, daily_limit - used)}
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used = len(session.exec(
        select(ChatMessage.id).where(
            ChatMessage.chart_id == chart_id,
            ChatMessage.role == "user",
            ChatMessage.created_at >= today_start,
        )
    ).all())
    return {"used": used, "limit": daily_limit, "remaining": max(0, daily_limit - used)}


def _monthly_sub_active(session: Session, order, chart_id: str) -> bool:
    """audit r4 A9: a paid monthly ORDER is not forever — chat requires an
    UNEXPIRED Subscription row. Web (chat_id None) and bot flows both covered."""
    from app.timeutil import ensure_utc, utcnow
    if not order or order.plan_key != "monthly":
        return True  # non-monthly gates handled by the caller
    q = select(Subscription).where(Subscription.chart_id == chart_id)
    if order.chat_id:
        q = q.where(Subscription.chat_id == order.chat_id)
    else:
        q = q.where(Subscription.chat_id == None)  # noqa: E711
    sub = session.exec(q).first()
    return bool(sub and sub.active and sub.expires_at
                and ensure_utc(sub.expires_at) > utcnow())


@app.get("/api/chat/access/{chart_id}")
def api_chat_access(chart_id: str, request: Request, session: Session = Depends(get_session)):
    # audit P0 (round 3): ownership BEFORE paid/quota info — bare UUID must not leak
    if not _owns_chart(session.get(Chart, chart_id), session, request):
        raise HTTPException(403, "دسترسی به این گفتگو ندارید")
    # A3: credit chat pack (quantity bucket) entitlement path
    u = get_current_user(request)
    uid = u.id if u else None
    if uid:
        ent = ent_has(session, uid, "chat", chart_id=chart_id)
        if ent:
            return {"allowed": True, "used": ent.used, "limit": ent.quantity,
                    "remaining": ent.quantity - ent.used, "source": "chat_pack"}
    # audit P0-4: AI chat is a GOLD/monthly feature (plan §7) — basic/full don't include it
    order = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    allowed = bool(order and order.plan_key in ("gold", "monthly"))
    if not allowed:
        return {"allowed": False, "used": 0, "limit": 0, "remaining": 0}
    if not _monthly_sub_active(session, order, chart_id):  # A9: expired monthly
        return {"allowed": False, "used": 0, "limit": 0, "remaining": 0,
                "reason": "subscription_expired"}
    quota = _chat_quota_info(session, chart_id, order,
                             _chat_account_key(session.get(Chart, chart_id), order, request))
    return {"allowed": True, **quota}


@app.get("/api/chat/history/{chart_id}")
def api_chat_history(chart_id: str, request: Request, session: Session = Depends(get_session)):
    # audit P0 (round 3): chat history is private personal data — ownership required
    if not _owns_chart(session.get(Chart, chart_id), session, request):
        raise HTTPException(403, "دسترسی به این گفتگو ندارید")
    msgs = session.exec(
        select(ChatMessage).where(ChatMessage.chart_id == chart_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return {"messages": [
        {"role": m.role, "content": m.content,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in msgs
    ]}


def _chat_guarded_context(request: Request, chart_id: str,
                          session: Session) -> tuple:
    """Shared guards for /api/chat and /api/chat/stream (D4): rate limit,
    ownership, paid plan, subscription expiry, atomic daily quota claim.
    Returns (chart, order, acct, profile, report) — raises HTTPException."""
    if not _rate_limit(f"chat:{_rl_client(request)}", 20, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    # audit P0 (round 3): ownership before any spend — bare UUID must not consume
    # another chart's paid quota or answer questions about someone else's birth chart
    if not _owns_chart(chart, session, request):
        raise HTTPException(403, "دسترسی به این گفتگو ندارید")
    # paid check: chat requires GOLD/monthly (audit P0-4 — plan §7)
    order = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    if not order or order.plan_key not in ("gold", "monthly"):
        raise HTTPException(403, "گفت‌وگو با هوش مصنوعی مخصوص پلن طلایی است")
    # audit r4 A9: monthly subscriptions EXPIRE — a paid order alone is not enough
    if not _monthly_sub_active(session, order, chart_id):
        raise HTTPException(403, "اشتراک ماهانه‌ات منقضی شده؛ برای ادامه گفت‌وگو آن را تمدید کن")

    # daily quota — ATOMIC per-account claim (audit r4 A8): Redis INCR+TTL so
    # concurrent requests can't both pass the last slot; DB count as degraded fallback
    daily_limit = _chat_daily_limit(order)
    acct = _chat_account_key(chart, order, request)
    used = chat_quota_claim(acct, daily_limit)
    if used is None:  # Redis down → degraded DB-count check
        quota = _chat_quota_info(session, chart_id, order, acct)
        if quota["used"] >= quota["limit"]:
            raise HTTPException(429, f"سهمیه امروزت تمام شد ({quota['limit']} سوال در روز). فردا دوباره بیا")
    elif used > daily_limit:
        raise HTTPException(429, f"سهمیه امروزت تمام شد ({daily_limit} سوال در روز). فردا دوباره بیا")

    profile = session.get(BirthProfile, chart.profile_id) if chart.profile_id else None
    report = session.exec(
        select(Report).where(Report.chart_id == chart_id).order_by(Report.created_at.desc())
    ).first()
    return chart, order, acct, profile, report


@app.post("/api/chat")
def api_chat(
    request: Request,
    chart_id: str = Form(...),
    question: str = Form(..., max_length=500),
    session: Session = Depends(get_session),
):
    # G11 (§108): ops can halt the AI chat instantly via the feature flag
    from app.feature_flags import flag
    if not flag("chat", "on"):
        raise HTTPException(503, "گفت‌وگو با چارت موقتاً غیرفعال است؛ بعداً تلاش کن [ZAY-AI-002]")
    chart, order, acct, profile, report = _chat_guarded_context(request, chart_id, session)

    try:
        result = chat_answer(
            question, chart.chart_json,
            report_sections=(report.sections if report and report.sections else None),
            focus_areas=(profile.focus_areas if profile else None),
            report_id=(report.id if report else None),
        )
    except Exception:
        chat_quota_release(acct)  # don't burn the daily quota on a failed call
        raise

    # persist history (user + assistant) — doubles as admin usage metering
    try:
        session.add(ChatMessage(chart_id=chart_id, role="user", content=question))
        session.add(ChatMessage(
            chart_id=chart_id, role="assistant", content=result.get("answer", ""),
            intent=result.get("intent"), domains=result.get("domains") or [],
            provider=result.get("provider"), model=result.get("model"),
            completion_tokens=result.get("tokens", 0),
            cost_usd=result.get("cost_usd", 0.0), ok=bool(result.get("ok")),
        ))
        # H1.3: cost metering — every chat call lands in llm_runs (user-scoped)
        try:
            session.add(LLMRun(
                user_id=(profile.user_id if profile else None), kind="chat",
                provider=result.get("provider", ""), model=result.get("model", ""),
                gateway=result.get("provider"),
                prompt_tokens=result.get("prompt_tokens", 0),
                completion_tokens=result.get("tokens", 0),
                cost_usd=result.get("cost_usd", 0.0), ok=bool(result.get("ok")),
            ))
        except Exception:  # noqa: BLE001 — metering must never break the answer
            session.rollback()
        session.commit()
    except Exception:  # noqa: BLE001 — history must never break the answer
        session.rollback()

    # reflect the atomic counter (or best-known used) in the response
    shown = chat_quota_used(acct)
    daily_limit = _chat_daily_limit(order)
    if shown is None:
        shown = _chat_quota_info(session, chart_id, order, acct)["used"]
    result["quota"] = {"used": shown, "limit": daily_limit,
                       "remaining": max(0, daily_limit - shown)}
    return result


@app.post("/api/chat/stream")
async def api_chat_stream(
    request: Request,
    chart_id: str = Form(...),
    question: str = Form(..., max_length=500),
    session: Session = Depends(get_session),
):
    """D4: real SSE token streaming (text/event-stream). Same guards as
    /api/chat; quota is claimed ONCE up front and released if the stream dies
    before any token. History is persisted on completion."""
    from fastapi.responses import StreamingResponse
    chart, order, acct, profile, report = _chat_guarded_context(request, chart_id, session)

    async def event_stream():
        from app.chat.service import chat_stream
        produced = False
        try:
            async for ev in chat_stream(
                question, chart.chart_json,
                report_sections=(report.sections if report and report.sections else None),
                focus_areas=(profile.focus_areas if profile else None),
                report_id=(report.id if report else None),
            ):
                if ev["type"] == "token":
                    produced = True
                # SSE: one `event:` line + `data:` json per frame
                data = json.dumps(ev, ensure_ascii=False)
                yield f"event: {ev['type']}\ndata: {data}\n\n"
                if ev["type"] == "done":
                    answer = ev.get("answer", "")
                    try:
                        with Session(engine) as s2:
                            s2.add(ChatMessage(chart_id=chart_id, role="user", content=question))
                            s2.add(ChatMessage(
                                chart_id=chart_id, role="assistant", content=answer,
                                intent=ev.get("intent"), domains=ev.get("domains") or [],
                                provider=ev.get("provider"), model=ev.get("model"),
                                completion_tokens=ev.get("tokens", 0),
                                cost_usd=ev.get("cost_usd", 0.0), ok=True,
                            ))
                            # H1.3: streamed chat calls also land in llm_runs
                            try:
                                s2.add(LLMRun(
                                    user_id=(profile.user_id if profile else None),
                                    kind="chat",
                                    provider=ev.get("provider", ""),
                                    model=ev.get("model", ""),
                                    gateway=ev.get("provider"),
                                    prompt_tokens=ev.get("prompt_tokens", 0),
                                    completion_tokens=ev.get("tokens", 0),
                                    cost_usd=ev.get("cost_usd", 0.0), ok=True,
                                ))
                            except Exception:  # noqa: BLE001
                                pass
                            s2.commit()
                    except Exception:  # noqa: BLE001 — history must never break the stream
                        pass
                if ev["type"] == "error":
                    yield f"event: quota\ndata: {json.dumps({'used': 0, 'limit': 0, 'remaining': 0}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001 — never leave the client hanging
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(e)[:200]}, ensure_ascii=False)}\n\n"
        finally:
            if not produced:
                chat_quota_release(acct)  # stream died before any token — refund

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/charts/{chart_id}/transits")
def api_chart_transits(chart_id: str, request: Request, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):  # audit r4 A3: transit IDOR
        raise HTTPException(403, "not authorized")
    from app.astrology.transits import compute_transits
    return {"events": compute_transits(chart.chart_json)}


@app.get("/transit/{chart_id}", response_class=HTMLResponse)
def transit_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):  # audit r4 A3: transit IDOR
        raise HTTPException(403, "not authorized")
    from app.astrology.transits import compute_transits
    return templates.TemplateResponse(request, "transit.html", {
        "title": "گذرهای کنونی", "chart_id": chart_id,
        "events": compute_transits(chart.chart_json),
    })


# ─────────────────────────── bots (Phase 6) ───────────────────────────

_seen_update_ids: set = set()
_MAX_SEEN = 10_000
_DEDUPE_TTL = 300  # F-05: replay window (seconds) — Redis-backed across workers


def _dedupe_update(update: dict) -> bool:
    """audit P0-5: return True if this update_id was already processed (retry).

    F-05 (audit v5 P1): the dedupe store is REDIS-backed (SET NX EX) so the
    two web workers share it — a process-local set let the same update_id be
    processed twice when a retry landed on the other worker. The local set is
    only a fallback when Redis is down, and it never clears wholesale (the old
    clear() at _MAX_SEEN re-opened the dedupe window for every past update).
    """
    uid = update.get("update_id")
    if uid is None:
        return False
    try:
        from app.security import _rl_redis
        r = _rl_redis()
        if r is not None:
            claimed = r.set(f"botup:{uid}", "1", nx=True, ex=_DEDUPE_TTL)
            if claimed is not None:
                return not claimed
    except Exception:  # noqa: BLE001 — Redis down → local fallback
        pass
    if uid in _seen_update_ids:
        return True
    if len(_seen_update_ids) >= _MAX_SEEN:      # bounded memory — drop oldest, never clear all
        _seen_update_ids.pop()
    _seen_update_ids.add(uid)
    return False

# ── audit P1-8: lightweight per-IP rate limit for expensive endpoints ──
_RL: dict = {}  # legacy; kept for reference — limits now live in security.check_rate_limit


def _rate_limit(key: str, limit: int, window: float = 60.0) -> bool:
    # audit P1 (round 3): delegate to the centralized limiter (Redis in prod,
    # in-memory fallback) so limits are shared across workers.
    from app.security import RateLimitExceeded, check_rate_limit
    try:
        check_rate_limit(key, limit, int(window))
        return True
    except RateLimitExceeded:
        return False


def _rl_client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.post("/api/v1/telegram/webhook")
async def telegram_webhook(request: Request):
    # audit P0: fail-closed — without a configured secret the route refuses
    if not TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403, "telegram webhook not configured (fail-closed)")
    if not _hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "", TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(403, "bad secret")
    update = await request.json()
    if _dedupe_update(update):
        return {"ok": True}
    try:
        await handle_update(update, "telegram")
    except Exception:  # noqa: BLE001 — a bot error must never cause endless TG retries
        pass
    return {"ok": True}


@app.post("/api/v1/bale/webhook/{secret}")
async def bale_webhook(secret: str, request: Request):
    # audit P0: Bale has no secret_token header support (v140 pitfall), so the
    # shared secret lives in the URL path — the webhook must be registered as
    # https://chart.negar.io/api/v1/bale/webhook/<BALE_WEBHOOK_SECRET>
    if not BALE_WEBHOOK_SECRET or not _hmac.compare_digest(secret, BALE_WEBHOOK_SECRET):
        raise HTTPException(403, "bad webhook secret")
    update = await request.json()
    if _dedupe_update(update):
        return {"ok": True}
    try:
        await handle_update(update, "bale")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


# ─────────────────────────── auth (H1.9 → app/routes/auth.py) ───────────────────────────


# ── Wallet (D3) — H1.9 → app/routes/wallet.py ─────────────────────────────────


# ── Web Push (D1) — H1.9 → app/routes/push.py ────────────────────────────────


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, session: Session = Depends(get_session)):
    """G15 (§22) — dashboard as the primary product: hero «امروز در چارت تو
    چه خبر است؟» + 8 retention cards. Login-gated; chart-less users get a CTA."""
    u = get_current_user(request)
    if not u:
        return RedirectResponse("/account/login?next=/dashboard", status_code=303)
    profiles = session.exec(select(BirthProfile).where(BirthProfile.user_id == u.id)).all()
    profile_ids = [p.id for p in profiles]
    charts = (session.exec(select(Chart).where(Chart.profile_id.in_(profile_ids))
                           .order_by(Chart.created_at.desc())).all() if profile_ids else [])
    chart_ids = [c.id for c in charts]
    reports = (session.exec(select(Report).where(Report.chart_id.in_(chart_ids))
                            .order_by(Report.created_at.desc())).all() if chart_ids else [])
    done = [r for r in reports if r.status == "done"]
    # daily insight for the newest chart (deterministic per Tehran day)
    daily = None
    if charts:
        from app.today.service import today_status
        try:
            st = today_status(session, charts[0])
            daily = {"date": st.get("date_fa") if st else None,
                     "headline": (st.get("daily") or {}).get("headline") if st else None}
        except Exception:  # noqa: BLE001 — dashboard must never 500 on a service hiccup
            daily = None
    cards = [
        {"key": "today", "title": "امروز در چارت تو", "desc": "بینش روزانه بر اساس چارت تولدت",
         "url": "/today", "icon": "sun"},
        {"key": "weekly", "title": "نگاهی به آسمان هفته", "desc": "تأمل هفتگی و گذرهای پیش رو",
         "url": "/today?view=week", "icon": "moon"},
        {"key": "chat", "title": "گفت‌وگو با چارت", "desc": "سؤال بپرس؛ پاسخ از گزارش و چارت تو",
         "url": f"/chat/{charts[0].id}" if charts else "/birth-form", "icon": "chat"},
        {"key": "explore", "title": "خودت را کشف کن", "desc": "کاوش تعاملی شخصیت و مسیر زندگی",
         "url": "/explore", "icon": "compass"},
        {"key": "reports", "title": "گزارش‌ها", "desc": f"{len(done)} گزارش آماده — دانلود PDF",
         "url": "/account", "icon": "book"},
        {"key": "synastry", "title": "سازگاری دو چارت", "desc": "سیناستری با شریک زندگی‌ات",
         "url": "/synastry", "icon": "heart"},
        {"key": "wallet", "title": "کیف پول", "desc": f"{u.credits} اعتبار — دعوت دوستان",
         "url": "/account", "icon": "wallet"},
        {"key": "plans", "title": "پلن‌ها", "desc": "گزارش کامل، طلایی و اشتراک",
         "url": "/plans", "icon": "sparkles"},
    ]
    return templates.TemplateResponse(request, "dashboard.html", {
        "title": "داشبورد — زایچه", "user": u, "charts": charts,
        "daily": daily, "cards": cards, "reports_done": len(done),
    })


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request, session: Session = Depends(get_session)):
    u = get_current_user(request)
    if not u:
        return RedirectResponse("/account/login", status_code=303)
    profiles = session.exec(select(BirthProfile).where(BirthProfile.user_id == u.id)).all()
    profile_ids = [p.id for p in profiles]
    charts = session.exec(
        select(Chart).where(Chart.profile_id.in_(profile_ids)).order_by(Chart.created_at.desc())
    ).all() if profile_ids else []
    chart_ids = [c.id for c in charts]
    reports = session.exec(
        select(Report).where(Report.chart_id.in_(chart_ids)).order_by(Report.created_at.desc())
    ).all() if chart_ids else []
    orders = session.exec(
        select(Order).where(
            (Order.profile_id.in_(profile_ids)) | (Order.user_id == u.id)
        ).order_by(Order.created_at.desc())
    ).all() if profile_ids else session.exec(
        select(Order).where(Order.user_id == u.id).order_by(Order.created_at.desc())
    ).all()
    # P6 — credit ledger history for the wallet card
    from app.models import CreditTransaction
    ledger = session.exec(
        select(CreditTransaction).where(CreditTransaction.user_id == u.id)
        .order_by(CreditTransaction.created_at.desc()).limit(20)
    ).all() if u.id else []
    # latest weekly reflections for the user's charts («نگاهی به آسمان هفته»)
    weekly = {}
    if chart_ids:
        from app.models import WeeklyReflection
        rows = session.exec(
            select(WeeklyReflection).where(WeeklyReflection.chart_id.in_(chart_ids))
            .order_by(WeeklyReflection.created_at.desc())
        ).all()
        for w in rows:
            weekly.setdefault(w.chart_id, w)
    from app.payment.orders import get_or_create_referral_code
    ref_code = get_or_create_referral_code(session, u.id)
    # G10 (§90): dashboard search index (labels only — no sensitive fields)
    search_items = []
    for p in profiles:
        cid = next((c.id for c in charts if c.profile_id == p.id), None)
        search_items.append({
            "k": "پروفایل", "id": p.id,
            "label": f"{p.name or 'بدون نام'} — {p.raw_year}/{p.raw_month}/{p.raw_day} {p.city_fa or ''}",
            "url": f"/chart/{cid}" if cid else "/birth-form",
        })
    for r in reports:
        search_items.append({
            "k": "گزارش", "id": r.id,
            "label": f"گزارش #{r.id[:8]} ({r.plan_key}) — {r.status}",
            "url": f"/api/reports/{r.id}/pdf" if r.status == "done" else f"/chart/{r.chart_id}",
        })
    for o in orders:
        search_items.append({
            "k": "سفارش", "id": o.id,
            "label": f"{o.plan_key} — {o.status}", "url": "/plans",
        })
    from app.security import CSRF_COOKIE, new_csrf_token
    csrf = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
    resp = templates.TemplateResponse(request, "account.html", {
        "title": "حساب کاربری", "user": u, "profiles": profiles,
        "charts": charts, "reports": reports, "orders": orders,
        "ledger": ledger, "search_items": search_items,
        "ref_url": f"{os.getenv('PUBLIC_BASE_URL', 'https://chart.negar.io')}/?ref={ref_code}",
        "csrf_token": csrf, "weekly": weekly,
    })
    resp.set_cookie(CSRF_COOKIE, csrf, httponly=True, samesite="lax", secure=True,
                    max_age=24 * 3600)
    return resp


# ───────────── G1 — funnel tracking + admin funnel dashboard ─────────────
FUNNEL_EVENTS = {"page_view_landing","birth_form_start","birth_form_submit","chart_created","chart_view_scroll_50","preview_insight_viewed","explore_card_click","explore_free_used","signup_started","signup_completed","chart_claimed","credit_cta_shown","credit_cta_click","pack_selected","checkout_started","payment_success","payment_failed","credit_spent","report_started","report_completed","report_pdf_download","transit_forecast_view","transit_analyze_purchase","chat_first_message","share_clicked","referral_link_copied"}
FUNNEL_STEPS = ["page_view_landing","birth_form_start","birth_form_submit","chart_created","signup_started","checkout_started","payment_success"]


class TrackPayload(BaseModel):
    event: str
    session_id: str = ""


@app.post("/api/track")
async def api_track(payload: TrackPayload, session: Session = Depends(get_session)):
    """G1 — anonymous funnel event beacon (fire-and-forget from track.js)."""
    ev = payload.event
    if ev not in FUNNEL_EVENTS:
        raise HTTPException(400, "unknown event")
    if len(ev) > 64 or len(payload.session_id) > 64:
        raise HTTPException(400, "field too long")
    session.add(FunnelEvent(event=ev, session_id=payload.session_id[:64]))
    session.commit()
    return {"ok": True}


@app.get("/api/admin/funnel")
def api_admin_funnel(request: Request, session: Session = Depends(get_session)):
    """G1 — conversion funnel: per-step counts + conversion rate + drop-off."""
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    counts: dict[str, int] = {}
    for ev in session.exec(select(FunnelEvent.event)).all():
        counts[ev] = counts.get(ev, 0) + 1
    steps = []
    prev = None
    for name in FUNNEL_STEPS:
        c = counts.get(name, 0)
        rate = (c / prev) if prev else None
        drop = (1 - rate) if rate is not None else None
        steps.append({
            "step": name, "count": c,
            "conversion_vs_prev": (round(rate, 4) if rate is not None else None),
            "dropoff": (round(drop, 4) if drop is not None else None),
        })
        prev = c
    return {"steps": steps, "total_events": sum(counts.values()), "distinct": counts}


@app.get("/api/consent")
def get_consent(request: Request, session: Session = Depends(get_session)):
    """G9 (§85) — list this user's consent records (privacy transparency)."""
    u = get_current_user(request)
    if not u:
        raise HTTPException(401, "not authorized")
    from app.models import ConsentLog
    rows = session.exec(select(ConsentLog).where(ConsentLog.user_id == u.id)
                        .order_by(ConsentLog.created_at)).all()
    return {"consents": [{"purpose": r.purpose, "version": r.version,
                          "accepted": r.accepted,
                          "at": r.created_at.isoformat()} for r in rows]}


@app.get("/api/notifications/prefs")
def get_notif_prefs(request: Request, session: Session = Depends(get_session)):
    """G8 (§57) — current notification preferences (defaults if unset)."""
    u = get_current_user(request)
    if not u:
        raise HTTPException(401, "not authorized")
    from app.models import NotificationPrefs
    p = session.get(NotificationPrefs, u.id)
    if not p:
        return {"daily_insight": True, "weekly_reflection": True, "report_ready": True,
                "quiet_start": 23, "quiet_end": 7}
    return {"daily_insight": p.daily_insight, "weekly_reflection": p.weekly_reflection,
            "report_ready": p.report_ready, "quiet_start": p.quiet_start,
            "quiet_end": p.quiet_end}


@app.post("/api/notifications/prefs")
def set_notif_prefs(request: Request, session: Session = Depends(get_session),
                    daily_insight: str = Form("true"), weekly_reflection: str = Form("true"),
                    report_ready: str = Form("true"),
                    quiet_start: int = Form(23), quiet_end: int = Form(7)):
    """G8 — update prefs (CSRF-guarded; validated ranges)."""
    u = get_current_user(request)
    if not u:
        raise HTTPException(401, "not authorized")
    if not (0 <= quiet_start <= 23 and 0 <= quiet_end <= 23):
        raise HTTPException(400, "[ZAY-AUTH-003] مقدار ساعت نامعتبر")
    from app.models import NotificationPrefs
    p = session.get(NotificationPrefs, u.id)
    if not p:
        p = NotificationPrefs(user_id=u.id)
        session.add(p)
    p.daily_insight = daily_insight == "true"
    p.weekly_reflection = weekly_reflection == "true"
    p.report_ready = report_ready == "true"
    p.quiet_start, p.quiet_end = quiet_start, quiet_end
    p.updated_at = datetime.now(timezone.utc)
    session.commit()
    return {"ok": True}


@app.get("/account/login", response_class=HTMLResponse)
def account_login_page(request: Request):
    return templates.TemplateResponse(request, "account_login.html", {"title": "ورود"})


# ── B3 — transit forecast: deterministic data (free) + paid analysis ─────────────
@app.get("/api/charts/{chart_id}/forecast")
def api_chart_forecast(chart_id: str, request: Request, session: Session = Depends(get_session),
                       months: int = 3):
    """B3 — deterministic transit forecast timeline (FREE). Ownership-checked."""
    from app.models import Chart, TransitForecast
    from app.astrology.transit_cache import cached_forecast
    chart = session.get(Chart, chart_id)
    if not chart or not _owns_chart(chart, session, request):
        raise HTTPException(403, "دسترسی به این چارت ندارید")
    months = 3 if months not in (3, 12) else months
    events = cached_forecast(session, chart_id, months, chart.chart_json)
    analysis = []
    try:
        import json as _json
        payload = _json.loads(
            session.exec(select(TransitForecast).where(
                TransitForecast.chart_id == chart_id, TransitForecast.months == months)).first().payload_json)
        analysis = payload.get("narratives") or []
    except Exception:  # noqa: BLE001
        analysis = []
    return {"months": months, "events": events, "analysis": analysis}


@app.post("/api/charts/{chart_id}/forecast/analyze")
def api_chart_forecast_analyze(chart_id: str, request: Request, session: Session = Depends(get_session),
                               months: int = Form(3)):
    """B3 — spend transit_3m / transit_12m credit → produce the analysis via the
    B2 layer (QA gate + auto-retry; double-QA-fail events are refunded)."""
    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"login_required": True})
    from app.models import Chart
    chart = session.get(Chart, chart_id)
    if not chart or not _owns_chart(chart, session, request):
        raise HTTPException(403, "دسترسی به این چارت ندارید")
    months = 3 if months not in (3, 12) else months
    action = f"transit_{months}m"
    from app.credits import InsufficientCredits, refund as _refund, spend
    try:
        tx = spend(session, user.id, action, idempotency_key=f"transit:{chart_id}:{months}", chart_id=chart_id)
    except InsufficientCredits as e:
        return JSONResponse(status_code=402, content={
            "code": "ZAY-AI-002", "message": "اعتبار کافی نیست",
            "need": e.needed, "balance": e.have, "credit_packs": True})

    from app.astrology.transit_cache import cached_forecast, store_transit_analysis
    from app.astrology.transit_forecast import forecast
    from app.core.llm import build_router
    from app.report.transit_narrative import narrate_transit
    events = cached_forecast(session, chart_id, months, chart.chart_json)
    if isinstance(events, dict):
        events = events.get("events") or []
    refunded = {"n": 0}

    def _on_fail(ev):
        nonlocal_refunded = refunded
        nonlocal_refunded["n"] += 1
        try:
            _refund(session, tx.id, reason=f"{action} QA refund")
        except Exception:  # noqa: BLE001
            pass

    narratives, m = narrate_transit(events, chart.chart_json, router=build_router("transit"),
                                    plan_key=action, on_event_failed=_on_fail)
    store_transit_analysis(session, chart_id, months, {"narratives": narratives})
    session.commit()  # persist the credit spend + stored analysis (get_session does not autoc...[truncated]
    return {"months": months, "events": events, "narratives": narratives,
            "metrics": {k: v for k, v in m.items() if k != "provider" and not isinstance(v, (set,))},
            "refunded": refunded["n"]}


@app.get("/transits/{chart_id}")
def transits_page(chart_id: str, request: Request, session: Session = Depends(get_session)):
    """B3 — transit timeline page (free deterministic data + paid analysis if owned)."""
    user = get_current_user(request)
    from app.models import Chart, TransitForecast
    chart = session.get(Chart, chart_id)
    if not chart or not _owns_chart(chart, session, request):
        return RedirectResponse("/account/login", status_code=303) if not user \
            else RedirectResponse("/", status_code=303)
    from app.astrology.transit_cache import cached_forecast
    try:
        import json as _json
        ev12 = cached_forecast(session, chart_id, 12, chart.chart_json)
        payload = session.exec(select(TransitForecast).where(
            TransitForecast.chart_id == chart_id, TransitForecast.months == 12)).first()
        analysis = _json.loads(payload.payload_json or "{}").get("narratives") or [] if payload else []
    except Exception:  # noqa: BLE001
        ev12, analysis = [], []
    return templates.TemplateResponse(request, "transits_forecast.html", {
        "title": "گذرهای پیشِ رو",
        "chart_id": chart_id,
        "events": ev12,
        "analysis": analysis,
        "chart": chart,
    })


@app.get("/account/export")
def account_export(request: Request, session: Session = Depends(get_session)):
    """G1 (§138) — personal data export (JSON + signed URLs for artifacts).

    Owner-only. Never includes secrets: password_hash, payment keys,
    push auth secrets, OTP hashes.
    """
    u = get_current_user(request)
    if not u:
        return RedirectResponse("/account/login", status_code=303)

    from app.models import (
        BirthProfile, Chart, ChatMessage, CreditTransaction, Exploration,
        Order, PushSubscription, Report, WeeklyReflection,
    )
    from app.payment.orders import get_or_create_referral_code
    from app.storage import presigned_url

    profiles = session.exec(
        select(BirthProfile).where(BirthProfile.user_id == u.id)
    ).all()
    profile_ids = [p.id for p in profiles]
    charts = session.exec(
        select(Chart).where(Chart.profile_id.in_(profile_ids)).order_by(Chart.created_at)
    ).all() if profile_ids else []
    chart_ids = [c.id for c in charts]

    def _presign(r2_key: str | None) -> str | None:
        if not r2_key:
            return None
        return presigned_url(r2_key, expires=1800)

    reports = []
    if chart_ids:
        rows = session.exec(
            select(Report).where(Report.chart_id.in_(chart_ids)).order_by(Report.created_at)
        ).all()
        reports = [{
            "id": r.id, "chart_id": r.chart_id, "plan_key": r.plan_key,
            "status": r.status, "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(), "retry_count": r.retry_count,
            "pdf_download_url": _presign(r.r2_key),
            "audio_download_url": _presign(r.audio_r2_key) if r.audio_status == "ready" else None,
        } for r in rows]

    orders = []
    if profile_ids:
        rows = session.exec(
            select(Order).where(
                (Order.profile_id.in_(profile_ids)) | (Order.user_id == u.id)
            ).order_by(Order.created_at)
        ).all()
    else:
        rows = session.exec(
            select(Order).where(Order.user_id == u.id).order_by(Order.created_at)
        ).all()
    orders = [{
        "id": o.id, "plan_key": o.plan_key, "amount_rial": o.amount_rial,
        "status": o.status, "payment_ref": getattr(o, "ref_id", None),
        "created_at": o.created_at.isoformat(), "note": o.note,
    } for o in rows]

    chat = []
    if chart_ids:
        msgs = session.exec(
            select(ChatMessage).where(ChatMessage.chart_id.in_(chart_ids))
            .order_by(ChatMessage.created_at).limit(500)
        ).all()
        chat = [{
            "chart_id": m.chart_id, "role": m.role, "content": m.content,
            "created_at": m.created_at.isoformat(),
        } for m in msgs]

    ledger = session.exec(
        select(CreditTransaction).where(CreditTransaction.user_id == u.id)
        .order_by(CreditTransaction.created_at)
    ).all()

    explorations = session.exec(
        select(Exploration).where(Exploration.user_id == u.id)
        .order_by(Exploration.created_at)
    ).all() if u.id else []

    weekly = []
    if chart_ids:
        rows = session.exec(
            select(WeeklyReflection).where(WeeklyReflection.chart_id.in_(chart_ids))
            .order_by(WeeklyReflection.created_at)
        ).all()
        weekly = [{
            "chart_id": w.chart_id, "week_start": w.week_start, "text": w.text,
            "created_at": w.created_at.isoformat(),
        } for w in rows]

    pushes = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == u.id)
    ).all()
    push = [{
        "endpoint": p.endpoint, "created_at": p.created_at.isoformat(),
    } for p in pushes]

    ref_code = get_or_create_referral_code(session, u.id)

    payload = {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "product": "zayche",
        "user": {
            "id": u.id, "phone": u.phone, "role": u.role, "status": u.status,
            "credits": u.credits, "balance_rial": u.balance_rial,
            "created_at": u.created_at.isoformat(),
        },
        "referral_code": ref_code,
        "profiles": [{
            "id": p.id, "name": p.name, "calendar_system": p.calendar_system,
            "raw_year": p.raw_year, "raw_month": p.raw_month, "raw_day": p.raw_day,
            "time_known": p.time_known, "hour": p.hour, "minute": p.minute,
            "city_fa": p.city_fa, "province_fa": p.province_fa,
            "lat": p.lat, "lon": p.lon, "tz_name": p.tz_name,
            "utc_datetime": p.utc_datetime.isoformat() if p.utc_datetime else None,
            "zodiac": p.zodiac, "focus_areas": p.focus_areas,
            "personal_question": p.personal_question,
            "created_at": p.created_at.isoformat(),
        } for p in profiles],
        "charts": [{
            "id": c.id, "profile_id": c.profile_id,
            "chart_json": c.chart_json, "created_at": c.created_at.isoformat(),
        } for c in charts],
        "reports": reports,
        "orders": orders,
        "chat_messages": chat,
        "credit_ledger": [{
            "id": t.id, "amount": t.amount, "reason": t.reason,
            "ref_id": t.ref_id, "created_at": t.created_at.isoformat(),
        } for t in ledger],
        "explorations": [{
            "id": e.id, "chart_id": e.chart_id, "card_key": e.card_key,
            "status": e.status, "result": e.result, "credits_cost": e.credits_cost,
            "created_at": e.created_at.isoformat(),
        } for e in explorations],
        "weekly_reflections": weekly,
        "push_subscriptions": push,
    }

    body = json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="zayche-export-{u.id[:8]}.json"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/account/delete", response_class=HTMLResponse)
def account_delete(request: Request, csrf_token: str = Form(""),
                   session: Session = Depends(get_session)):
    u = get_current_user(request)
    if not u:
        return RedirectResponse("/account/login", status_code=303)
    from app.security import verify_csrf
    if not verify_csrf(request, csrf_token):
        raise HTTPException(403, "درخواست نامعتبر (CSRF)")
    from app.security import audit
    audit(session.bind, u.phone or u.id, "account.delete", u.id)

    profiles = session.exec(select(BirthProfile).where(BirthProfile.user_id == u.id)).all()
    charts = []
    for p in profiles:
        charts += session.exec(select(Chart).where(Chart.profile_id == p.id)).all()
    chart_ids = [c.id for c in charts]

    # cascade (audit P2-2): everything tied to these charts/profiles must go,
    # otherwise orphans keep piling up (subscriptions would keep messaging a
    # deleted user; R2 PDFs would leak private birth data).
    # audit r4 C6: two real bugs fixed here — (1) chat_messages were NEVER
    # deleted (orphans + FK violation), (2) SQLAlchemy's unitofwork does not
    # topologically order these deletes, so an explicit flush() per FK level
    # is required (Chart→BirthProfile, Message→Chart). Before this fix,
    # account deletion 500'd for ANY user with charts/chats.
    from app.storage import delete_object_checked
    for cid in chart_ids:
        # chat messages (FK → chart) — was missing entirely (audit r4 C6)
        for msg in session.exec(select(ChatMessage).where(ChatMessage.chart_id == cid)).all():
            session.delete(msg)
        # reports (+ their R2 objects + LLM runs + RAG chunks)
        for rep in session.exec(select(Report).where(Report.chart_id == cid)).all():
            # F-08 (audit v5 P1): audio object + local PDF artifact too — the
            # old code only deleted rep.r2_key and leaked both of these.
            # F-13 (audit v6 P1): R2 deletion is now FAIL-CLOSED — a leaked
            # private artifact is worse than a failed deletion, so any R2 error
            # rolls the whole account deletion back (user retries later).
            try:
                for key in (rep.r2_key, rep.audio_r2_key):
                    if key:
                        delete_object_checked(key)
            except Exception as e:  # noqa: BLE001 — artifact cleanup failed
                audit(session.bind, u.phone or u.id, "account.delete_r2_failed",
                      rep.id, str(e)[:200])
                session.rollback()
                raise HTTPException(502, "حذف حساب کامل نشد؛ چند دقیقه بعد دوباره تلاش کنید")
            if rep.pdf_path:
                try:
                    os.remove(rep.pdf_path)
                except OSError:
                    pass  # missing file is fine
            for run in session.exec(select(LLMRun).where(LLMRun.report_id == rep.id)).all():
                session.delete(run)
            # H0.2: RAG embeddings (report_chunks) — missing before; deleting a
            # report that was RAG-indexed raised IntegrityError → account
            # deletion 500'd (proved with a real delete on the test DB).
            # No SQLModel relationship exists between Report/ReportChunk, so
            # unitofwork cannot order these — explicit flush is required.
            for ch in session.exec(select(ReportChunk).where(ReportChunk.report_id == rep.id)).all():
                session.delete(ch)
            session.flush()
            session.delete(rep)
        # orders (as primary chart, or as synastry secondary)
        for o in session.exec(select(Order).where(
            (Order.chart_id == cid) | (Order.secondary_chart_id == cid)
        )).all():
            session.delete(o)
        # subscriptions + weekly reflections
        for sub in session.exec(select(Subscription).where(Subscription.chart_id == cid)).all():
            session.delete(sub)
        for w in session.exec(select(WeeklyReflection).where(WeeklyReflection.chart_id == cid)).all():
            session.delete(w)
    session.flush()  # children gone before charts
    # referrals (this user as referrer or referred)
    for e in session.exec(select(ReferralEvent).where(
        (ReferralEvent.referrer_user_id == u.id) | (ReferralEvent.new_user_id == u.id)
    )).all():
        session.delete(e)
    for rc in session.exec(select(ReferralCode).where(ReferralCode.user_id == u.id)).all():
        session.delete(rc)
    # H0.2: wallet withdrawal requests (FK → users) — missing before; a user
    # with any withdrawal request could not delete their account.
    for wd in session.exec(select(WithdrawalRequest).where(WithdrawalRequest.user_id == u.id)).all():
        session.delete(wd)
    session.flush()

    for c in charts:
        session.delete(c)
    session.flush()  # charts gone before profiles (unitofwork won't order this)
    for p in profiles:
        session.delete(p)
    session.delete(u)
    session.commit()
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("chart_user")
    return resp


# ── static pages & articles — H1.9 → app/routes/seo.py ───────────────────────


# ─── admin auth (login / logout / dashboard) — pages stay here (H1.9) ───

def _load_pages() -> dict:
    """P0-4: pages source of truth is PostgreSQL; JSON is the historical fallback."""
    import json as _json
    from pathlib import Path as _P

    base: dict = {}
    p = _P("/root/chart-platform/app/content/pages.json")
    if p.exists():
        base = _json.loads(p.read_text("utf-8"))
    try:
        from app.models_cms import Page
        with Session(engine) as s:
            rows = s.exec(select(Page)).all()
        for pg in rows:
            extra = dict(pg.extra or {})
            entry = {"title": pg.title, "meta": extra.get("meta", ""),
                     "sections": extra.get("sections") or ([{"h2": pg.title, "text": pg.content}] if pg.content else []),
                     "categories": extra.get("categories"), "items": extra.get("items")}
            # defensive: only override JSON when the row actually carries the
            # rich structure the templates need (v1 seed lost extra → keep JSON)
            if entry["categories"] is None and entry["items"] is None and not extra.get("sections"):
                if pg.key in base:
                    continue
            base[pg.key] = entry
    except Exception:  # noqa: BLE001 — table may not exist before migration
        pass
    return base


def _load_articles() -> list[dict]:
    """P0-4: CMS source of truth is PostgreSQL; JSON is the historical fallback."""
    try:
        from app.models_cms import Article
        with Session(engine) as s:
            rows = s.exec(select(Article)
                          .where(Article.status == "published")
                          .order_by(Article.updated_at.desc())).all()
        if rows:
            out = []
            for a in rows:
                body = a.body or ""
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, list) and parsed:
                        body = parsed
                    elif isinstance(parsed, dict):
                        body = [parsed]
                    else:
                        body = [{"p": body}]
                except Exception:  # noqa: BLE001
                    body = [{"p": body}] if body.strip() else []
                out.append({
                    "slug": a.slug, "title": a.title, "category": a.category,
                    "excerpt": a.excerpt, "keywords": a.keywords,
                    "meta_title": a.meta_title, "meta_description": a.meta_description,
                    "canonical": a.canonical, "image": a.featured_image,
                    "author": a.author,
                    "body": body,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else "",
                })
            return out
    except Exception:  # noqa: BLE001 — table may not exist before migration
        pass
    import json as _json
    from pathlib import Path as _P
    p = _P("/root/chart-platform/app/content/articles.json")
    return _json.loads(p.read_text("utf-8")) if p.exists() else []


# ── guide/about/faq/articles/sky — H1.9 → app/routes/seo.py ──────────────────


# ─────────────────────────── admin dashboard (Phase 5) ───────────────────────────

import hashlib
import hmac as _hmac
import secrets as _secrets

_ADMIN_PIN: str = os.getenv("ADMIN_PIN") or ""
if not _ADMIN_PIN:
    raise RuntimeError("ADMIN_PIN is required (audit P0: no default admin PIN)")
_ADMIN_COOKIE = "chart_admin"
_ADMIN_SECRET: str = os.getenv("ADMIN_SECRET") or ""
if not _ADMIN_SECRET:
    if IS_PROD:
        raise RuntimeError("ADMIN_SECRET is required in production (APP_ENV=prod|production)")
    _ADMIN_SECRET = _secrets.token_hex(16)


def _admin_cookie_value() -> str:
    return _hmac.new(_ADMIN_SECRET.encode(), _ADMIN_PIN.encode(), hashlib.sha256).hexdigest()


def _is_admin(request: Request) -> bool:
    """Shared admin gate (imported by routes to avoid main↔route cycles)."""
    return _hmac.compare_digest(request.cookies.get(_ADMIN_COOKIE, ""), _admin_cookie_value())


def is_admin_request(request: Request) -> bool:
    return _is_admin(request)


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"title": "ورود مدیریت"})


@app.post("/admin/login")
def admin_login(request: Request, pin: str = Form(...), session: Session = Depends(get_session)):
    # audit P1: brute-force throttle — 5 tries / 5 min per IP
    if not _rate_limit(f"admin-login:{_rl_client(request)}", 5, 300):
        return templates.TemplateResponse(request, "admin_login.html", {
            "title": "ورود مدیریت", "error": "تلاش‌های زیاد؛ ۵ دقیقه بعد دوباره امتحان کنید",
        }, status_code=429)
    if not _hmac.compare_digest(pin, _ADMIN_PIN):
        return templates.TemplateResponse(request, "admin_login.html", {
            "title": "ورود مدیریت", "error": "رمز نادرست است",
        }, status_code=401)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(_ADMIN_COOKIE, _admin_cookie_value(), httponly=True, max_age=12 * 3600,
                    samesite="lax", secure=True)
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(_ADMIN_COOKIE)
    return resp


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    orders = session.exec(select(Order).order_by(Order.created_at.desc()).limit(100)).all()
    reports = session.exec(select(Report).order_by(Report.created_at.desc()).limit(20)).all()
    # B1: DLQ health — failed reports awaiting the retry cron
    dlq = session.exec(select(Report).where(Report.status == "failed")).all()
    dlq_count = len(dlq)
    users = session.exec(select(User).order_by(User.created_at.desc()).limit(50)).all()
    plans = session.exec(select(Plan).order_by(Plan.sort)).all()
    audit = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(30)).all()
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    llm = session.exec(select(LLMRun).where(LLMRun.created_at >= week_ago)).all()
    llm_cost = round(sum(r.cost_usd for r in llm), 4)
    paid = [o for o in orders if o.status == "paid"]
    revenue = sum(o.amount_rial for o in paid) / 10  # toman
    by_status: dict[str, int] = {}
    for o in orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1
    # AI chat status: active model per part + provider health + chat usage
    from app.core.llm import build_router
    ai_status: dict[str, str] = {}
    ai_provider: dict[str, str] = {}
    for part, default in (("report", "antigravity/gemini-3.6-flash-high"),
                          ("chat", "antigravity/gemini-3.6-flash-high"),
                          ("preview", "deepseek-v4-flash"),
                          ("section_model_default", "deepseek-v4-pro")):
        ai_status[part] = secret_store.get_secret(f"{part}_llm_model", f"{part.upper()}_LLM_MODEL", default)
        p = secret_store.get_secret(f"{part}_llm_provider", f"{part.upper()}_LLM_PROVIDER", "auto")
        ai_provider[part] = (p.strip().lower() or "auto")
    ai_health = build_router("report").health_report()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    chat_today = len(session.exec(select(ChatMessage.id).where(ChatMessage.created_at >= today_start)).all())
    chat_total = len(session.exec(select(ChatMessage.id)).all())
    # D3: withdrawal queue for admin (pending first)
    withdrawals = session.exec(
        select(WithdrawalRequest).order_by(
            WithdrawalRequest.status.asc(), WithdrawalRequest.created_at.desc()).limit(30)
    ).all()
    return templates.TemplateResponse(request, "admin.html", {
        "title": "دشبورد مدیریت", "orders": orders, "reports": reports,
        "revenue_toman": revenue, "by_status": by_status,
        "users": users, "plans": plans, "audit": audit,
        "llm_cost_7d": llm_cost, "llm_runs_7d": len(llm),
        "ai_status": ai_status, "ai_health": ai_health, "ai_provider": ai_provider,
        "chat_today": chat_today, "chat_total": chat_total,
        "dlq_count": dlq_count,  # B1 — used by admin.html KPI
        "withdrawals": withdrawals,  # D3 — wallet cash-out queue
        "secrets": secret_store.secret_status(),
        # H1.9: prompt management moved to app/routes/admin.py
        "prompt_keys": _admin_routes.PROMPT_KEYS,
        "prompt_overrides": [{"key": o["key"], "version": o["version"],
                              "is_active": o["is_active"], "content": o["content"]}
                             for o in _admin_routes.admin_prompts_list(request, session)["overrides"]],
    })


# ── H1.9: extracted routers (auth / wallet / push / admin / seo) ──────────────
from app.routes import admin as _admin_routes
from app.routes import auth as _auth_routes
from app.routes import cms_admin as _cms_routes
from app.routes import push as _push_routes
from app.routes import seo as _seo_routes
from app.routes import wallet as _wallet_routes

# Flatten into app.router.routes: newer FastAPI keeps include_router lazy
# (_IncludedRouter), which would hide these from app.routes (authz-matrix test,
# middleware, route enumeration). Appending APIRoutes keeps full visibility.
for _rt in (_auth_routes.router, _wallet_routes.router, _push_routes.router,
            _seo_routes.router, _admin_routes.router, _cms_routes.router):
    for _r in _rt.routes:
        app.router.routes.append(_r)

# api/admin/plans + api/admin/llm-cost → app/routes/admin.py (H1.9)


@app.get("/api/admin/stats")
def api_admin_stats(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    orders = session.exec(select(Order)).all()
    paid = [o for o in orders if o.status == "paid"]
    return {
        "orders_total": len(orders),
        "orders_paid": len(paid),
        "revenue_toman": sum(o.amount_rial for o in paid) / 10,
        "reports_done": len(session.exec(select(Report).where(Report.status == "done")).all()),
    }


# ─────────────────────────── admin secrets (server-move) ───────────────────────────
@app.get("/api/admin/secrets", response_class=JSONResponse)
def admin_secrets_list(request: Request):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from app import secret_store
    return {"secrets": secret_store.secret_status()}


@app.post("/api/admin/secrets/{key}", response_class=JSONResponse)
def admin_secret_set(key: str, request: Request, value: str = Form("")):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from app import secret_store
    from app.security import audit
    if key not in secret_store._CATALOG_BY_KEY:
        raise HTTPException(404, "unknown secret key")
    cleared = (value or "").strip() == ""
    secret_store.set_secret(key, value, admin="admin")
    audit(engine, "admin", "secret.update", key, "cleared" if cleared else "set")
    return {"ok": True, "key": key, "set": not cleared, "restart_required": True}


@app.post("/api/admin/secrets/{key}/reveal", response_class=JSONResponse)
def admin_secret_reveal(key: str, request: Request):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from app import secret_store
    if key not in secret_store._CATALOG_BY_KEY:
        raise HTTPException(404, "unknown secret key")
    return {"key": key, "value": secret_store.reveal_secret(key)}


@app.post("/api/admin/llm/test", response_class=JSONResponse)
async def admin_llm_test(request: Request):
    """Ping each configured LLM provider so the admin can verify keys live."""
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from app.core.llm import GoProvider, DeepSeekProvider
    results: dict[str, dict] = {}
    go = GoProvider()
    if go.api_key:
        r = await go.complete("فقط یک کلمه بگو: سلام", max_tokens=64, temperature=0)
        results["go"] = {"ok": r.ok, "model": r.model, "latency_ms": r.latency_ms,
                         "error": r.error or ""}
    else:
        results["go"] = {"ok": False, "error": "کلید OpenCode (GO_API_KEY) تنظیم نشده است"}
    ds = DeepSeekProvider()
    if ds.api_key:
        r = await ds.complete("فقط یک کلمه بگو: سلام", max_tokens=64, temperature=0)
        results["deepseek"] = {"ok": r.ok, "model": r.model, "latency_ms": r.latency_ms,
                               "error": r.error or ""}
    else:
        results["deepseek"] = {"ok": False, "error": "کلید مستقیم DeepSeek تنظیم نشده است (اختیاری)"}
    return results


# ── P3: Self-discovery catalog («خودت را کشف کن») ───────────────────────────

@app.get("/explore", response_class=HTMLResponse)
def page_explore(request: Request, chart: str = "", session: Session = Depends(get_session)):
    """D2 — catalog page. Requires an owned chart (self-discovery runs on it)."""
    from app.explore.cards import CARD_CATALOG
    user = get_current_user(request)
    charts = []
    if user:
        rows = session.exec(
            select(Chart, BirthProfile).join(BirthProfile, Chart.profile_id == BirthProfile.id)
            .where(BirthProfile.user_id == user.id)
            .order_by(Chart.created_at.desc()).limit(10)
        ).all()
        charts = [c for c, _p in rows]
    if chart:
        ch = session.get(Chart, chart)
        if not ch or not _owns_chart(ch, session, request):
            raise HTTPException(403, "دسترسی به این چارت ندارید")
        active_chart = chart
    else:
        active_chart = charts[0].id if charts else ""
    return templates.TemplateResponse(
        request, "explore.html",
        {"cards": CARD_CATALOG, "cards_json": _safe_json(
            [{"key": c.key, "title_fa": c.title_fa, "benefit_fa": c.benefit_fa}
             for c in CARD_CATALOG], ensure_ascii=False),
         "charts": charts,
         "charts_json": _safe_json([{"id": c.id, "label": f"چارت {i + 1} — {c.created_at:%Y-%m-%d}"} for i, c in enumerate(charts)]),
         "active_chart_json": _safe_json(active_chart),
         "credits": user.credits if user else 0,
         "free_available": bool(user and user.credits <= 0 and not user.free_exploration_used)},
    )


@app.get("/api/explore/cards")
def api_explore_cards():
    """D2 — public catalog: every card with title + one-line benefit."""
    from app.explore.cards import CARD_CATALOG
    return {"cards": [
        {"key": c.key, "title_fa": c.title_fa, "benefit_fa": c.benefit_fa}
        for c in CARD_CATALOG
    ]}


@app.post("/api/explore/{card_key}", response_class=StreamingResponse)
async def api_explore_start(
    request: Request,
    card_key: str,
    chart_id: str = Form(...),
    session: Session = Depends(get_session),
):
    """D3/D5 — run one card on an owned chart. Costs 1 credit, ATOMIC.
    SSE: status → done(result) | error. Failed generation → auto refund."""
    from fastapi.responses import StreamingResponse
    from app.explore.cards import CARD_MAP
    from app.explore.service import generate_exploration, spend_credit, refund_credit, mark_free_exploration
    from app.models import Exploration

    card = CARD_MAP.get(card_key)
    if not card:
        raise HTTPException(404, "کارت نامعتبر است")
    if not _rate_limit(f"explore:{_rl_client(request)}", 10, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "ابتدا وارد شوید")
    chart = session.get(Chart, chart_id)
    if not chart or not _owns_chart(chart, session, request):
        raise HTTPException(403, "دسترسی به این چارت ندارید")
    # D5/F5: atomic spend — credits >= cost, else first-ever exploration is
    # FREE (loss-aversion copy «اولین کاوش رایگان»), else 402.
    exp = Exploration(user_id=user.id, chart_id=chart_id, card_key=card_key,
                      title_fa=card.title_fa)
    session.add(exp)
    session.commit()
    session.refresh(exp)
    cost = exp.credits_cost
    charged = cost
    if not spend_credit(session, user.id, exp.id, cost):
        if user.credits <= 0 and not user.free_exploration_used:
            mark_free_exploration(session, user, exp.id)
            exp.status = "running"
            session.commit()
            charged = 0  # free — nothing to refund on failure
        else:
            exp.status = "failed"
            exp.error = "اعتبار کافی نیست"
            session.commit()
            raise HTTPException(402, "[ZAY-AI-002] اعتبار کافی نیست")

    async def event_stream():
        try:
            from app.core.llm import build_chat_router
            yield "event: status\ndata: {\"status\":\"analysing\"}\n\n"
            result, metrics = await generate_exploration(
                build_chat_router(), chart.chart_json, card,
                exploration_id=exp.id, user_id=user.id)
            if result is None:
                refund_credit(session, user.id, exp.id, charged)
                with Session(engine) as s2:
                    e = s2.get(Exploration, exp.id)
                    e.status = "failed"
                    e.refunded = True
                    e.metrics = metrics
                    e.error = "تولید ناموفق بود؛ اعتبار برگشت داده شد"
                    s2.commit()
                yield "event: error\ndata: {\"detail\":\"تولید ناموفق بود؛ اعتبار برگشت داده شد\"}\n\n"
                return
            with Session(engine) as s2:
                e = s2.get(Exploration, exp.id)
                e.status = "done"
                e.result = result
                e.metrics = metrics
                s2.commit()
            yield f"event: done\ndata: {json.dumps({'exploration_id': exp.id, 'result': result, 'metrics': {k: v for k, v in metrics.items() if k != 'provider'}}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001 — stream must not hang the client
            try:
                refund_credit(session, user.id, exp.id, charged)
                with Session(engine) as s2:
                    e2 = s2.get(Exploration, exp.id)
                    e2.status = "failed"
                    e2.refunded = True
                    e2.error = str(e)[:300]
                    s2.commit()
            except Exception:  # noqa: BLE001
                pass
            yield f"event: error\ndata: {json.dumps({'detail': 'خطای غیرمنتظره — اعتبار برگشت داده شد'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/explore/history")
def api_explore_history(request: Request, session: Session = Depends(get_session)):
    """D3 — user's exploration history (latest first)."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "ابتدا وارد شوید")
    rows = session.exec(
        select(Exploration).where(Exploration.user_id == user.id)
        .order_by(Exploration.created_at.desc()).limit(50)
    ).all()
    return {"items": [
        {"id": r.id, "card_key": r.card_key, "title_fa": r.title_fa,
         "status": r.status, "created_at": r.created_at.isoformat(),
         "error": r.error}
        for r in rows
    ]}


@app.delete("/api/explore/{exploration_id}")
def api_explore_delete(exploration_id: str, request: Request,
                       session: Session = Depends(get_session)):
    """D3 — remove an exploration from history (own rows only)."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "ابتدا وارد شوید")
    row = session.get(Exploration, exploration_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


# ── P4: Today + daily reflection + streak ────────────────────────────────────

def _today_plan_access(session: Session, chart: Chart) -> str:
    """E3 — 'full' for gold/monthly subscribers, else 'preview'."""
    order = session.exec(
        select(Order).where(Order.chart_id == chart.id, Order.status == "paid")
    ).first()
    if order and order.plan_key in ("gold", "monthly") and _monthly_sub_active(session, order, chart.id):
        return "full"
    return "preview"


@app.get("/today", response_class=HTMLResponse)
def page_today(request: Request, chart: str = "", session: Session = Depends(get_session)):
    from app.today.service import today_status
    user = get_current_user(request)
    charts = []
    if user:
        rows = session.exec(
            select(Chart, BirthProfile).join(BirthProfile, Chart.profile_id == BirthProfile.id)
            .where(BirthProfile.user_id == user.id)
            .order_by(Chart.created_at.desc()).limit(10)
        ).all()
        charts = [c for c, _p in rows]
    if chart:
        ch = session.get(Chart, chart)
        if not ch or not _owns_chart(ch, session, request):
            raise HTTPException(403, "دسترسی به این چارت ندارید")
        active_chart = chart
    else:
        active_chart = charts[0].id if charts else ""
    status = today_status(session, ch) if charts and (ch := next((c for c in charts if c.id == active_chart), None)) else None
    access = _today_plan_access(session, next((c for c in charts if c.id == active_chart), None)) if charts else "preview"
    if status:
        status["access"] = access
    charts_meta = [{"id": c.id, "label": f"چارت {i + 1} — {c.created_at:%Y-%m-%d}"} for i, c in enumerate(charts)]
    return templates.TemplateResponse(request, "today.html", {
        "charts": charts, "charts_json": _safe_json(charts_meta),
        "active_chart": active_chart,
        "active_chart_json": _safe_json(active_chart),
        "status": status,
        "status_json": _safe_json(status) if status else "null",
        "access": access,
    })


@app.get("/api/today")
def api_today(chart_id: str, request: Request, session: Session = Depends(get_session)):
    """E2 — status for the today page: facts, question, streak, done-flag."""
    from app.today.service import today_status
    chart = session.get(Chart, chart_id)
    if not chart or not _owns_chart(chart, session, request):
        raise HTTPException(403, "دسترسی به این چارت ندارید")
    return {**today_status(session, chart), "access": _today_plan_access(session, chart)}


@app.post("/api/today/reflection")
def api_today_reflection(request: Request, chart_id: str = Form(...),
                         answer: str = Form(...), session: Session = Depends(get_session)):
    """E2/E3/E5 — save today's reflection (full access only) with streak."""
    from app.today.service import submit_reflection, compute_streak, _chart_tz
    chart = session.get(Chart, chart_id)
    if not chart or not _owns_chart(chart, session, request):
        raise HTTPException(403, "دسترسی به این چارت ندارید")
    if _today_plan_access(session, chart) != "full":
        raise HTTPException(403, "[ZAY-AI-002] تأمل روزانه مخصوص پلن طلایی و اشتراک است")
    if not _rate_limit(f"today:{_rl_client(request)}", 10, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    tz = _chart_tz(session, chart)
    status, err = submit_reflection(session, chart_id, answer, tz)
    if err:
        raise HTTPException(400, err)
    return {**status, "streak": compute_streak(session, chart_id, tz)}

