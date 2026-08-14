"""Chart Platform — FastAPI app (Phase 2: free product).

Routes: landing, birth form, chart compute (sync), chart page, city search.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from hmac import compare_digest
from pathlib import Path

import redis.asyncio as redis_async

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

import app.config  # noqa: F401 — load .env FIRST
from app.auth import get_current_user, request_otp, set_user_cookie, verify_otp
from app.security import security_guard
from app.astrology.big_three import big_three
from app.astrology.cities_ir import search_cities
from app.astrology.engine import compute_from_fields
from app.astrology.svg_wheel import render_chart_svg
from app.bots.handler import TELEGRAM_WEBHOOK_SECRET, handle_update
from app.chat.service import chat_answer
from app.db import engine, get_session, init_db
from app.models import (AuditLog, BirthProfile, Chart, ChatMessage, Coupon, LLMRun, Order, Plan,
                        PromptVersion, ReferralCode, ReferralEvent, Report, Subscription,
                        User, WeeklyReflection)
from app import secret_store

BALE_WEBHOOK_SECRET = secret_store.get_secret("bale_webhook_secret", "BALE_WEBHOOK_SECRET", "")
from datetime import datetime, timezone
from app.payment.zarinpal import ZarinpalClient, ZarinpalError

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

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
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as s:
        for p in PLANS_SEED:
            if s.get(Plan, p.key) is None:
                s.add(p)
        s.commit()
    yield
    await _close_arq_pool()


app = FastAPI(title="چارت تولد", lifespan=lifespan)
app.middleware("http")(security_guard)   # security.py: CSRF origin check + rate limits
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/sw.js")
def sw_file():
    """Service worker at ROOT scope (PWA — plan §13.9)."""
    from fastapi.responses import FileResponse
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@app.get("/health")
def health_check():
    """Liveness/readiness (audit P2-7): DB + Redis + basic app heartbeat."""
    from sqlalchemy import text
    out = {"status": "ok", "db": "ok", "redis": "ok"}
    code = 200
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        out["db"] = "down"
        out["status"] = "degraded"
        code = 503
    try:
        import redis as _r
        if not _r.Redis.from_url(_REDIS_URL, decode_responses=True).ping():
            raise RuntimeError("no pong")
    except Exception:  # noqa: BLE001
        out["redis"] = "down"
        out["status"] = "degraded"
        code = 503
    return JSONResponse(out, status_code=code)


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
    return templates.TemplateResponse(request, "chart.html", {
        "title": "چارت تولد", "chart": chart, "big_three": bt, "svg": svg,
        "aspect_grid": aspect_grid_svg(planets),
        "element_donut": element_donut_svg(sign_counts),
        "house_bar": house_bar_svg(houses),
        "access_token": chart.access_token or "",
    })


# ─────────────────────────── api ───────────────────────────

@app.get("/api/cities")
def api_cities(q: str = Query(default="", max_length=50), limit: int = 10):
    return {"results": search_cities(q, limit)}


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
    user_id: str | None = None,
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
        user_id=user_id or (get_current_user(request).id if get_current_user(request) else None),
    )
    assert lat is not None and lon is not None
    try:
        result = compute_from_fields(
            lat=lat, lon=lon, year=year, month=month, day=day,
            hour=hour if time_known else 12,
            minute=minute if time_known else 0,
            time_known=time_known, jalali=(calendar == "jalali"),
            tz_name="Asia/Tehran", zodiac=zodiac,
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
    """Paid-order gate + ownership (audit P0-1/P0-3): paid order AND the
    requester must own the chart (user_id or capability token)."""
    paid = session.exec(
        select(Order).where(Order.chart_id == rep.chart_id, Order.status == "paid")
    ).first()
    if not paid:
        return False
    return _owns_chart(session.get(Chart, rep.chart_id), session, request)


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
    pool = await _arq_pool()
    await pool.enqueue_job("generate_report", report_id)


@app.post("/api/charts/{chart_id}/report")
def api_create_report(chart_id: str, request: Request,
                      session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    # ownership (P0-1): only the owner (user_id or capability token) may trigger
    if not _owns_chart(chart, session, request):
        raise HTTPException(403, "برای تولید گزارش، ابتدا پلن را خریداری کنید")
    # plan v3.0 §8/§12: report generation happens AFTER payment — plan_key drives section set
    paid = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    if not paid:
        raise HTTPException(403, "برای تولید گزارش، ابتدا پلن را خریداری کنید")
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
        raise HTTPException(403, "برای دانلود گزارش، ابتدا خرید کنید")
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
        raise HTTPException(403, "برای دانلود گزارش، ابتدا خرید کنید")
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
    return templates.TemplateResponse(request, "payment_result.html", {
        "title": "نتیجه‌ی پرداخت", "order": order, "plan": plan,
    })


@app.get("/api/plans")
def api_plans(session: Session = Depends(get_session)):
    plans = session.exec(select(Plan).where(Plan.active).order_by(Plan.sort)).all()
    return [{"key": p.key, "name_fa": p.name_fa, "subtitle_fa": p.subtitle_fa,
             "price_toman": p.price_toman, "features": p.features} for p in plans]


@app.post("/api/orders")
def api_create_order(
    request: Request,
    plan_key: str = Form(...),
    chart_id: str = Form(...),
    coupon: str | None = Form(None),
    secondary_chart_id: str | None = Form(None),
    chat_id: str | None = Form(None),
    platform: str | None = Form(None),
    session: Session = Depends(get_session),
):
    """Create order + payment URL (shared helper — also used by bots)."""
    from app.payment.orders import create_order
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    user = get_current_user(request)
    try:
        order, pay_url = create_order(
            session, plan_key, chart_id,
            secondary_chart_id=secondary_chart_id, chat_id=chat_id, platform=platform,
            coupon=coupon, ref_code=request.cookies.get("chart_ref", ""),
            new_user_id=user.id if user else None,
        )
    except LookupError:
        raise HTTPException(404, "plan not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"order_id": order.id, "payment_url": pay_url, "authority": order.authority}


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
        # duplicate callbacks may transition pending→paid; the losers redirect.
        # Without this, two callbacks could double-activate a subscription
        # (+60 days) or enqueue two reports for the same order.
        from sqlalchemy import text as _text
        claimed = session.exec(_text(
            "UPDATE orders SET status = 'paid' WHERE id = :oid AND status = 'pending' RETURNING id"
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
            # consume coupon (idempotent — only once per order; atomic against
            # concurrent verifies so max_uses can never be exceeded — audit P1 r3)
            if order.coupon_id:
                from sqlalchemy import text
                consumed = session.exec(text(
                    "UPDATE coupons SET used_count = used_count + 1 "
                    "WHERE id = :cid AND used_count < max_uses RETURNING id"
                ), params={"cid": order.coupon_id}).first()
                if not consumed:
                    order.status = "failed"
                    session.commit()
                    return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)
            # monthly subscription: activate + extend 30 days (plan §7)
            from app.payment.orders import REPORT_PLANS, activate_subscription
            if order.plan_key == "monthly":
                activate_subscription(session, order)
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
        except ZarinpalError:
            order.status = "failed"
            session.commit()
    else:
        order.status = "failed"
        session.commit()

    return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)


@app.get("/sitemap.xml")
def sitemap_xml():
    import os
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.example.com").rstrip("/")
    urls = ["/", "/plans", "/birth-form", "/synastry", "/rectify", "/learn", "/privacy",
            "/terms", "/refund", "/disclaimer", "/contact",
            "/guide", "/about", "/faq", "/articles"]
    # dynamic learn pages — guides + planets + houses at /learn/, signs at /signs/
    try:
        from app.seo.content import GUIDES, PLANETS, HOUSES, SIGNS
        urls += [f"/learn/{k}" for k in GUIDES]
        urls += [f"/learn/{k}" for k in PLANETS]
        urls += [f"/learn/{k}" for k in HOUSES]
        urls += [f"/signs/{s['slug']}" for s in SIGNS.values()]
    except Exception:
        pass
    try:
        urls += [f"/articles/{a['slug']}" for a in _load_articles()]
    except Exception:
        pass
    # de-dupe preserving order
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in out:
        body += f'  <url><loc>{base}{u}</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>\n'
    body += "</urlset>\n"
    from fastapi.responses import Response
    return Response(content=body, media_type="application/xml")


@app.get("/robots.txt")
def robots_txt():
    import os
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.example.com").rstrip("/")
    from fastapi.responses import Response
    return Response(content=f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n",
                    media_type="text/plain")


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


@app.post("/api/admin/coupons")
def admin_coupon_create(request: Request, session: Session = Depends(get_session),
                        code: str = Form(...), percent: int = Form(...), max_uses: int = Form(1)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if not (0 < percent <= 100):
        raise HTTPException(400, "percent must be 1-100")
    c = Coupon(code=code.strip().upper(), percent=percent, max_uses=max_uses)
    session.add(c)
    session.commit()
    from app.security import audit
    audit(session.bind, "admin", "coupon.create", c.code, f"{percent}%")
    return {"ok": True, "id": c.id, "code": c.code}


# ── prompt overrides (plan v3.0 §8 — مدیریت پرامپتها) ─────────────────────────
PROMPT_KEYS = ["identity", "mind", "emotions", "career", "money", "love", "health",
               "family", "social", "spirit", "life_path", "strength", "karma", "cultural"]


@app.get("/api/admin/prompts")
def admin_prompts_list(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from app.report.prompt_overrides import get_overrides
    active = get_overrides()
    rows = session.exec(select(PromptVersion).order_by(
        PromptVersion.prompt_key, PromptVersion.version.desc())).all()
    seen: set[str] = set()
    out = []
    for r in rows:  # latest version per key (rows are desc by version)
        if r.prompt_key in seen:
            continue
        seen.add(r.prompt_key)
        out.append({"key": r.prompt_key, "version": r.version,
                    "is_active": r.is_active,
                    "content": r.content if r.is_active else None})
    # keys without any override yet
    missing = [k for k in PROMPT_KEYS if k not in seen]
    return {"keys": [o["key"] for o in out] + missing,
            "overrides": out, "active": active}


@app.post("/api/admin/prompts/{prompt_key}")
def admin_prompt_save(request: Request, prompt_key: str, session: Session = Depends(get_session),
                      content: str = Form(...)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if prompt_key not in PROMPT_KEYS:
        raise HTTPException(400, "unknown prompt key")
    from app.report.prompt_overrides import set_override
    row = set_override(session, prompt_key, content)
    from app.security import audit
    audit(session.bind, "admin", "prompt.update", prompt_key, f"v{row.version} ({len(content)} chars)")
    return {"ok": True, "key": prompt_key, "version": row.version}


@app.post("/api/admin/orders/{order_id}/refund")
def admin_refund(order_id: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if order.status != "paid":
        raise HTTPException(400, "فقط سفارش پرداخت‌شده ریفاند می‌شود")
    order.status = "refunded"
    if order.coupon_id:
        c = session.get(Coupon, order.coupon_id)
        if c and c.used_count > 0:
            c.used_count -= 1
    session.commit()
    from app.security import audit
    audit(session.bind, "admin", "order.refund", order.id, order.ref_id or "")
    return {"ok": True, "status": "refunded"}


@app.post("/api/admin/orders/{order_id}/regenerate")
def admin_regenerate(order_id: str, request: Request, session: Session = Depends(get_session)):
    """Re-run a failed report from admin (plan v3.0 §8 — بازتولید گزارش)."""
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if order.status != "paid":
        raise HTTPException(400, "فقط سفارش پرداخت‌شده بازتولید می‌شود")
    chart = session.get(Chart, order.chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    rep = session.exec(select(Report).where(Report.chart_id == order.chart_id).order_by(
        Report.created_at.desc())).first()
    if not rep:
        raise HTTPException(404, "report not found")
    if rep.status == "done":
        raise HTTPException(400, "گزارش آماده است — برای اجرای مجدد اول حذفش کنید")
    rep.status = "queued"
    rep.error = None
    session.add(rep)
    session.commit()
    ok = _enqueue_report(rep.id)
    if not ok:
        rep.status = "failed"
        rep.error = "queue unavailable (worker not running)"
        session.commit()
        raise HTTPException(503, "worker در دسترس نیست — بعداً دوباره تلاش کنید")
    from app.security import audit
    audit(session.bind, "admin", "report.regenerate", rep.id, f"order={order.id} chart={chart.id}")
    return {"ok": True, "report_id": rep.id, "status": "queued"}


@app.get("/api/admin/coupons", response_class=JSONResponse)
def admin_coupons(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    return [{"id": c.id, "code": c.code, "percent": c.percent, "max_uses": c.max_uses,
             "used_count": c.used_count, "active": c.active} for c in session.exec(select(Coupon)).all()]


# ─────────────────────────── synastry / rectify / audio (Phases 8-9) ───────────────

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
    city_a = search_cities(city_a or "", 1)
    city_b = search_cities(city_b or "", 1)
    if not city_a or not city_b:
        raise HTTPException(400, "شهرها را انتخاب کنید")
    ca = compute_from_fields(city_a[0]["lat"], city_a[0]["lon"], year_a, month_a, day_a,
                             hour_a, minute_a, True, calendar_a == "jalali", "Asia/Tehran", zodiac=zodiac_a)
    cb = compute_from_fields(city_b[0]["lat"], city_b[0]["lon"], year_b, month_b, day_b,
                             hour_b, minute_b, True, calendar_b == "jalali", "Asia/Tehran", zodiac=zodiac_b)
    r = synastry(ca.chart_json, cb.chart_json)
    return {
        "a": name_a or "شخص اول", "b": name_b or "شخص دوم",
        "score": r["overall"], "verdict": r["verdict"], "free": True, "full_locked": True,
    }


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
    """Save both charts + create the paid synastry order (plan §8, ~499k toman)."""
    from app.payment.orders import create_order
    chart_a, _ = _compute_and_save_chart(
        session, request, calendar=calendar_a, year=year_a, month=month_a, day=day_a,
        time_known=True, hour=hour_a, minute=minute_a, city_fa=city_a,
        province_fa=None, lat=None, lon=None, name=name_a, zodiac=zodiac_a)
    chart_b, _ = _compute_and_save_chart(
        session, request, calendar=calendar_b, year=year_b, month=month_b, day=day_b,
        time_known=True, hour=hour_b, minute=minute_b, city_fa=city_b,
        province_fa=None, lat=None, lon=None, name=name_b, zodiac=zodiac_b)
    session.add(chart_a); session.add(chart_b)
    session.commit(); session.refresh(chart_a); session.refresh(chart_b)
    user = get_current_user(request)
    try:
        order, pay_url = create_order(
            session, "synastry", chart_a.id, secondary_chart_id=chart_b.id,
            coupon=None, ref_code="", new_user_id=user.id if user else None,
        )
    except (LookupError, ValueError) as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"order_id": order.id, "payment_url": pay_url,
            "chart_a": chart_a.id, "chart_b": chart_b.id}


@app.post("/api/synastry/full")
def api_synastry_full(chart_a: str = Form(...), chart_b: str = Form(...),
                      session: Session = Depends(get_session)):
    """Full synastry report — requires a paid synastry order for the pair."""
    from app.astrology.synastry import synastry
    ca = session.get(Chart, chart_a)
    cb = session.get(Chart, chart_b)
    if not ca or not cb:
        raise HTTPException(404, "chart not found")
    paid = session.exec(
        select(Order).where(
            Order.plan_key == "synastry", Order.status == "paid",
            Order.chart_id == chart_a, Order.secondary_chart_id == chart_b,
        )
    ).first()
    if not paid:
        raise HTTPException(403, "برای مشاهدهی تحلیل کامل، ابتدا سیناستری را خریداری کنید")
    return synastry(ca.chart_json, cb.chart_json)


@app.get("/api/synastry/access")
def api_synastry_access(chart_a: str, chart_b: str, session: Session = Depends(get_session)):
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
    rep = session.get(Report, report_id)
    if not rep or rep.status not in ("done", "degraded"):
        raise HTTPException(404, "report not ready")
    # gate: paid order + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "برای دریافت فایل صوتی، ابتدا خرید کنید")
    import asyncio
    import time as _time
    from pathlib import Path as _P
    # audit P1: /tmp hygiene — drop audio cache files older than 24h
    try:
        _cut = _time.time() - 86400
        for _f in _P("/tmp").glob("report-audio-*.mp3"):
            if _f.stat().st_mtime < _cut:
                _f.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    out = _P("/tmp") / f"report-audio-{report_id[:8]}.mp3"
    if not out.exists():
        text = "گزارش اختصاصی چارت تولد. "
        for k, v in (rep.sections or {}).items():
            t = (v or {}).get("title", k)
            c = (v or {}).get("content", "")
            text += f"بخش {t}. {' '.join(str(c).split())[:800]} "
            if len(text) > 9000:
                break
        try:
            import edge_tts
            async def _gen():
                tts = edge_tts.Communicate(text, "fa-IR-DilaraNeural", rate="+0%")
                await tts.save(str(out))
            asyncio.run(_gen())
        except Exception as e:
            raise HTTPException(502, f"تولید صوت ممکن نیست: {e}")
    from fastapi.responses import FileResponse
    return FileResponse(str(out), media_type="audio/mpeg",
                        filename=f"chart-report-{report_id[:8]}.mp3")


@app.get("/learn", response_class=HTMLResponse)
def learn_index(request: Request):
    from app.seo.content import GUIDES, PLANETS, HOUSES
    return templates.TemplateResponse(request, "seo_index.html", {
        "title": "آموزش چارت تولد — مقالات نجومی",
        "guides": GUIDES, "planets": PLANETS, "houses": HOUSES,
    })


@app.get("/learn/{slug}", response_class=HTMLResponse)
def learn_page(request: Request, slug: str):
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


@app.get("/signs/{slug}", response_class=HTMLResponse)
def sign_page(request: Request, slug: str):
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


# ─────────────────────────── SEO (Phase 8) ───────────────────────────


@app.get("/chat/{chart_id}", response_class=HTMLResponse)
def chat_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    if not _owns_chart(chart, session, request):
        # audit P0 (round 3): chat exposes a private conversation — same gate as /chart
        return RedirectResponse("/birth-form?e=private", status_code=303)
    return templates.TemplateResponse(request, "chat.html", {
        "title": "گفت‌وگو با چارت", "chart_id": chart_id,
    })


def _chat_quota_info(session: Session, chart_id: str, order) -> dict:
    """Daily quota for a chart's AI chat (gold vs monthly, admin-overridable)."""
    limit_key = "chat_daily_limit_gold" if order.plan_key == "gold" else "chat_daily_limit_monthly"
    default = "5" if order.plan_key == "gold" else "15"
    try:
        daily_limit = int(secret_store.get_secret(limit_key, limit_key.upper(), default))
    except ValueError:
        daily_limit = int(default)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used = len(session.exec(
        select(ChatMessage.id).where(
            ChatMessage.chart_id == chart_id,
            ChatMessage.role == "user",
            ChatMessage.created_at >= today_start,
        )
    ).all())
    return {"used": used, "limit": daily_limit, "remaining": max(0, daily_limit - used)}


@app.get("/api/chat/access/{chart_id}")
def api_chat_access(chart_id: str, request: Request, session: Session = Depends(get_session)):
    # audit P0 (round 3): ownership BEFORE paid/quota info — bare UUID must not leak
    if not _owns_chart(session.get(Chart, chart_id), session, request):
        raise HTTPException(403, "دسترسی به این گفتگو ندارید")
    # audit P0-4: AI chat is a GOLD/monthly feature (plan §7) — basic/full don't include it
    order = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    allowed = bool(order and order.plan_key in ("gold", "monthly"))
    if not allowed:
        return {"allowed": False, "used": 0, "limit": 0, "remaining": 0}
    quota = _chat_quota_info(session, chart_id, order)
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


@app.post("/api/chat")
def api_chat(
    request: Request,
    chart_id: str = Form(...),
    question: str = Form(..., max_length=500),
    session: Session = Depends(get_session),
):
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

    # daily quota (per chart)
    quota = _chat_quota_info(session, chart_id, order)
    if quota["used"] >= quota["limit"]:
        raise HTTPException(429, f"سهمیه امروزت تمام شد ({quota['limit']} سوال در روز). فردا دوباره بیا")

    profile = session.get(BirthProfile, chart.profile_id) if chart.profile_id else None
    report = session.exec(
        select(Report).where(Report.chart_id == chart_id).order_by(Report.created_at.desc())
    ).first()

    result = chat_answer(
        question, chart.chart_json,
        report_sections=(report.sections if report and report.sections else None),
        focus_areas=(profile.focus_areas if profile else None),
    )

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
        session.commit()
    except Exception:  # noqa: BLE001 — history must never break the answer
        session.rollback()

    result["quota"] = {"used": quota["used"] + 1, "limit": quota["limit"],
                       "remaining": max(0, quota["limit"] - (quota["used"] + 1))}
    return result


@app.get("/api/charts/{chart_id}/transits")
def api_chart_transits(chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.astrology.transits import compute_transits
    return {"events": compute_transits(chart.chart_json)}


@app.get("/transit/{chart_id}", response_class=HTMLResponse)
def transit_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.astrology.transits import compute_transits
    return templates.TemplateResponse(request, "transit.html", {
        "title": "گذرهای کنونی", "chart_id": chart_id,
        "events": compute_transits(chart.chart_json),
    })


# ─────────────────────────── bots (Phase 6) ───────────────────────────

_seen_update_ids: set = set()
_MAX_SEEN = 10_000

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


def _dedupe_update(update: dict) -> bool:
    """audit P0-5: return True if this update_id was already processed (retry)."""
    uid = update.get("update_id")
    if uid is None:
        return False
    if uid in _seen_update_ids:
        return True
    _seen_update_ids.add(uid)
    if len(_seen_update_ids) > _MAX_SEEN:      # bounded memory
        _seen_update_ids.clear()
    return False


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


# ─────────────────────────── auth (lazy OTP — plan §4) ───────────────────────────

@app.post("/api/auth/otp/request")
def auth_otp_request(request: Request, phone: str = Form(...)):
    # combined rate limit: IP (here) + phone (inside request_otp via Redis)
    if not _rate_limit(f"otp-ip:{_rl_client(request)}", 5, 600):
        raise HTTPException(429, "تعداد درخواست زیاد است؛ کمی بعد تلاش کن")
    if not phone or len(phone) < 10:
        raise HTTPException(400, "شماره موبایل معتبر نیست")
    try:
        return request_otp(phone)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.post("/api/auth/otp/verify")
def auth_otp_verify(request: Request, phone: str = Form(...), code: str = Form(...)):
    u = verify_otp(phone, code)
    if not u:
        raise HTTPException(401, "کد نادرست یا منقضی شده")
    return set_user_cookie(request, u.id)


@app.get("/api/auth/me")
def auth_me(request: Request):
    u = get_current_user(request)
    if not u:
        return {"user": None}
    return {"user": {"id": u.id, "phone": u.phone, "role": u.role}}


@app.post("/api/auth/logout")
def auth_logout():
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("chart_user")
    return resp


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
        select(Order).where(Order.profile_id.in_(profile_ids)).order_by(Order.created_at.desc())
    ).all() if profile_ids else []
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
    from app.security import CSRF_COOKIE, new_csrf_token
    csrf = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
    resp = templates.TemplateResponse(request, "account.html", {
        "title": "حساب کاربری", "user": u, "profiles": profiles,
        "charts": charts, "reports": reports, "orders": orders,
        "ref_url": f"{os.getenv('PUBLIC_BASE_URL', 'https://chart.negar.io')}/?ref={ref_code}",
        "csrf_token": csrf, "weekly": weekly,
    })
    resp.set_cookie(CSRF_COOKIE, csrf, httponly=True, samesite="lax", secure=True,
                    max_age=24 * 3600)
    return resp


@app.get("/account/login", response_class=HTMLResponse)
def account_login_page(request: Request):
    return templates.TemplateResponse(request, "account_login.html", {"title": "ورود"})


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
    from app.storage import delete_object
    for cid in chart_ids:
        # reports (+ their R2 objects + LLM runs)
        for rep in session.exec(select(Report).where(Report.chart_id == cid)).all():
            if rep.r2_key:
                delete_object(rep.r2_key)
            for run in session.exec(select(LLMRun).where(LLMRun.report_id == rep.id)).all():
                session.delete(run)
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
    # referrals (this user as referrer or referred)
    for e in session.exec(select(ReferralEvent).where(
        (ReferralEvent.referrer_user_id == u.id) | (ReferralEvent.new_user_id == u.id)
    )).all():
        session.delete(e)
    for rc in session.exec(select(ReferralCode).where(ReferralCode.user_id == u.id)).all():
        session.delete(rc)

    for c in charts:
        session.delete(c)
    for p in profiles:
        session.delete(p)
    session.delete(u)
    session.commit()
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("chart_user")
    return resp


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {"title": "حریم خصوصی"})


@app.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html", {"title": "قوانین استفاده"})


@app.get("/refund", response_class=HTMLResponse)
def refund_page(request: Request):
    return templates.TemplateResponse(request, "refund.html", {"title": "شرایط استرداد"})


@app.get("/disclaimer", response_class=HTMLResponse)
def disclaimer_page(request: Request):
    return templates.TemplateResponse(request, "disclaimer.html", {"title": "سلب مسئولیت"})


@app.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse(request, "contact.html", {"title": "تماس با ما"})


# ─── content pages (guide / about / faq) + articles ───

def _load_pages() -> dict:
    import json as _json
    from pathlib import Path as _P
    return _json.loads(_P("/root/chart-platform/app/content/pages.json").read_text("utf-8"))


def _load_articles() -> list[dict]:
    import json as _json
    from pathlib import Path as _P
    p = _P("/root/chart-platform/app/content/articles.json")
    return _json.loads(p.read_text("utf-8")) if p.exists() else []


@app.get("/guide", response_class=HTMLResponse)
def page_guide(request: Request):
    data = _load_pages()["guide"]
    return templates.TemplateResponse(request, "page.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "sections": data["sections"], "hero": data["title"],
    })


@app.get("/about", response_class=HTMLResponse)
def page_about(request: Request):
    data = _load_pages()["about"]
    return templates.TemplateResponse(request, "page.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "sections": data["sections"], "hero": data["title"],
    })


@app.get("/faq", response_class=HTMLResponse)
def page_faq(request: Request):
    data = _load_pages()["faq"]
    cats = data.get("categories") or [{"name": "عمومی", "items": data.get("items", [])}]
    return templates.TemplateResponse(request, "faq.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "categories": cats,
    })


@app.get("/articles", response_class=HTMLResponse)
def page_articles(request: Request):
    arts = _load_articles()
    categories = sorted({a.get("category", "عمومی") for a in arts})
    return templates.TemplateResponse(request, "articles_index.html", {
        "title": "مقالات نجوم و چارت تولد",
        "meta": "مجموعه مقالات آموزشی نجوم، چارت تولد، سیارات، برج‌ها و تحلیل شخصیت — به زبان ساده",
        "articles": arts,
        "categories": categories,
    })


@app.get("/sky", response_class=HTMLResponse)
def page_sky(request: Request):
    from app.astrology.sky import sky_today
    return templates.TemplateResponse(request, "sky.html", {
        "title": "آسمان امروز — فاز ماه، موقعیت سیارات و جنبه‌های آسمانی",
        "meta": "موقعیت امروز سیارات، فاز ماه، جنبه‌های آسمانی و رجوعی‌ها — با توضیح ساده و تخصصی برای خودشناسی و تأمل",
        "sky": sky_today(),
    })


@app.get("/articles/{slug}", response_class=HTMLResponse)
def page_article(slug: str, request: Request):
    arts = _load_articles()
    art = next((a for a in arts if a["slug"] == slug), None)
    if not art:
        raise HTTPException(404, "article not found")
    from app.seo.article_banner import article_banner_svg
    return templates.TemplateResponse(request, "article.html", {
        "title": art["title"], "meta": art.get("meta", ""), "art": art,
        "banner_svg": article_banner_svg(art.get("category", ""), art["title"]),
        "others": [a for a in arts if a["slug"] != slug][:6],
    })


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
    if os.getenv("APP_ENV", "dev") == "prod":
        raise RuntimeError("ADMIN_SECRET is required (set APP_ENV=prod)")
    _ADMIN_SECRET = _secrets.token_hex(16)


def _admin_cookie_value() -> str:
    return _hmac.new(_ADMIN_SECRET.encode(), _ADMIN_PIN.encode(), hashlib.sha256).hexdigest()


def _is_admin(request: Request) -> bool:
    return _hmac.compare_digest(request.cookies.get(_ADMIN_COOKIE, ""), _admin_cookie_value())


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
    for part, default in (("report", "deepseek-v4-pro"), ("chat", "deepseek-v4-flash"),
                          ("preview", "deepseek-v4-flash")):
        ai_status[part] = secret_store.get_secret(f"{part}_llm_model", f"{part.upper()}_LLM_MODEL", default)
        p = secret_store.get_secret(f"{part}_llm_provider", f"{part.upper()}_LLM_PROVIDER", "auto")
        ai_provider[part] = (p.strip().lower() or "auto")
    ai_health = build_router("report").health_report()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    chat_today = len(session.exec(select(ChatMessage.id).where(ChatMessage.created_at >= today_start)).all())
    chat_total = len(session.exec(select(ChatMessage.id)).all())
    return templates.TemplateResponse(request, "admin.html", {
        "title": "دشبورد مدیریت", "orders": orders, "reports": reports,
        "revenue_toman": revenue, "by_status": by_status,
        "users": users, "plans": plans, "audit": audit,
        "llm_cost_7d": llm_cost, "llm_runs_7d": len(llm),
        "ai_status": ai_status, "ai_health": ai_health, "ai_provider": ai_provider,
        "chat_today": chat_today, "chat_total": chat_total,
        "secrets": secret_store.secret_status(),
        "prompt_keys": PROMPT_KEYS,
        "prompt_overrides": [{"key": o["key"], "version": o["version"],
                              "is_active": o["is_active"], "content": o["content"]}
                             for o in admin_prompts_list(request, session)["overrides"]],
    })


@app.put("/api/admin/plans/{plan_key}")
def api_admin_plan_update(plan_key: str, request: Request, session: Session = Depends(get_session),
                          price_toman: int | None = Form(None), active: bool | None = Form(None)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    plan = session.get(Plan, plan_key)
    if not plan:
        raise HTTPException(404, "plan not found")
    if price_toman is not None and price_toman > 0:
        plan.price_toman = price_toman
    if active is not None:
        plan.active = active
    session.add(plan)
    session.commit()
    from app.security import audit
    audit(session.bind, "admin", "plan.update", plan.key, f"{plan.price_toman} toman active={plan.active}")
    return {"ok": True}


@app.get("/api/admin/llm-cost")
def api_admin_llm_cost(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    rows = session.exec(select(LLMRun).where(LLMRun.created_at >= week_ago)).all()
    by_provider: dict[str, float] = {}
    for r in rows:
        by_provider[r.provider] = by_provider.get(r.provider, 0) + r.cost_usd
    return {"cost_usd_7d": round(sum(r.cost_usd for r in rows), 4),
            "runs_7d": len(rows), "by_provider": {k: round(v, 4) for k, v in by_provider.items()}}


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
        r = await go.complete("فقط یک کلمه بگو: سلام", max_tokens=16, temperature=0)
        results["go"] = {"ok": r.ok, "model": r.model, "latency_ms": r.latency_ms,
                         "error": r.error or ""}
    else:
        results["go"] = {"ok": False, "error": "کلید OpenCode (GO_API_KEY) تنظیم نشده است"}
    ds = DeepSeekProvider()
    if ds.api_key:
        r = await ds.complete("فقط یک کلمه بگو: سلام", max_tokens=16, temperature=0)
        results["deepseek"] = {"ok": r.ok, "model": r.model, "latency_ms": r.latency_ms,
                               "error": r.error or ""}
    else:
        results["deepseek"] = {"ok": False, "error": "کلید مستقیم DeepSeek تنظیم نشده است (اختیاری)"}
    return results

