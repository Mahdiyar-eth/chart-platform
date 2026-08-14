"""H1.9 — admin API routes extracted from main.py (coupons, prompts, refund,
regenerate, plans, llm-cost, withdrawals). Pages (login/logout/dashboard)
stay in main.py.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.main import _is_admin, _enqueue_report, _release_coupon, get_session
from app.models import Coupon, LLMRun, Order, Plan, PromptVersion, Subscription

router = APIRouter()

PROMPT_KEYS = ["identity", "mind", "emotions", "career", "money", "love", "health",
               "family", "social", "spirit", "life_path", "strength", "karma", "cultural"]


@router.post("/api/admin/coupons")
def admin_coupon_create(request: Request, session: Session = Depends(get_session),
                        code: str = Form(...), percent: int = Form(...), max_uses: int = Form(1)):
    from fastapi import HTTPException
    from app.security import audit
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if not (0 < percent <= 100):
        raise HTTPException(400, "percent must be 1-100")
    c = Coupon(code=code.strip().upper(), percent=percent, max_uses=max_uses)
    session.add(c)
    session.commit()
    audit(session.bind, "admin", "coupon.create", c.code, f"{percent}%")
    return {"ok": True, "id": c.id, "code": c.code}


@router.get("/api/admin/prompts")
def admin_prompts_list(request: Request, session: Session = Depends(get_session)):
    from fastapi import HTTPException
    from app.report.prompt_overrides import get_overrides
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
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
    missing = [k for k in PROMPT_KEYS if k not in seen]
    return {"keys": [o["key"] for o in out] + missing,
            "overrides": out, "active": active}


@router.post("/api/admin/prompts/{prompt_key}")
def admin_prompt_save(request: Request, prompt_key: str, session: Session = Depends(get_session),
                      content: str = Form(...)):
    from fastapi import HTTPException
    from app.report.prompt_overrides import set_override
    from app.security import audit
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if prompt_key not in PROMPT_KEYS:
        raise HTTPException(400, "unknown prompt key")
    row = set_override(session, prompt_key, content)
    audit(session.bind, "admin", "prompt.update", prompt_key, f"v{row.version} ({len(content)} chars)")
    return {"ok": True, "key": prompt_key, "version": row.version}


@router.post("/api/admin/orders/{order_id}/refund")
def admin_refund(order_id: str, request: Request, session: Session = Depends(get_session)):
    """audit r4 B6: REAL refund lifecycle — calls Zarinpal, closes the chat
    subscription if this order originated one, returns the coupon slot.
    States: paid → refunding → refunded | refund_failed (admin retries)."""
    from fastapi import HTTPException
    from app.security import audit
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    # F-04 (audit v5 P1): 'refunding' is retryable too — if the local commit
    # failed after the gateway succeeded, the admin can re-issue and the
    # gateway's already-refunded answer lands in the refunded branch below.
    if order.status not in ("paid", "refund_failed", "refunding"):
        raise HTTPException(400, "فقط سفارش پرداخت‌شده ریفاند می‌شود")
    order.status = "refunding"
    session.commit()
    try:
        from app.payment.zarinpal import ZarinpalClient
        res = ZarinpalClient().refund(order.authority or "", order.amount_rial)
    except Exception as e:  # noqa: BLE001 — gateway/network error
        err = str(e)
        # F-04: an already-refunded authority is SUCCESS, not failure — the
        # money already moved back on an earlier attempt whose commit died.
        if any(k in err.lower() for k in ("already", "duplicate", "refunded", "66", "67")):
            order.status = "refunded"
            order.error = None
            _release_coupon(session, order)
            if order.chart_id:
                subs = session.exec(select(Subscription).where(Subscription.order_id == order.id)).all()
                for sub in subs:
                    sub.active = False
                    sub.expires_at = datetime.now(timezone.utc)
            session.commit()
            audit(session.bind, "admin", "order.refund", order.id, "already-refunded (idempotent)")
            return {"ok": True, "status": "refunded", "ref_id": order.ref_id or ""}
        order.status = "refund_failed"
        order.error = f"ریفاند ناموفق: {err[:300]}"
        session.commit()
        audit(session.bind, "admin", "order.refund_failed", order.id, err[:200])
        raise HTTPException(502, f"ریفاند در درگاه ناموفق بود: {err[:200]} — بعداً دوباره تلاش کنید")

    order.status = "refunded"
    order.ref_id = res.get("ref_id", order.ref_id or "")
    order.error = None
    _release_coupon(session, order)  # audit r4 A10 — return the slot

    # close the subscription this order originated (audit r4 B6)
    if order.chart_id:
        subs = session.exec(select(Subscription).where(Subscription.order_id == order.id)).all()
        for sub in subs:
            sub.active = False
            sub.expires_at = datetime.now(timezone.utc)

    session.commit()
    audit(session.bind, "admin", "order.refund", order.id, order.ref_id or "")
    return {"ok": True, "status": "refunded", "ref_id": res.get("ref_id", "")}


@router.post("/api/admin/orders/{order_id}/regenerate")
def admin_regenerate(order_id: str, request: Request, session: Session = Depends(get_session)):
    """Re-run a failed report from admin (plan v3.0 §8 — بازتولید گزارش)."""
    from fastapi import HTTPException
    from app.models import Chart, Report
    from app.security import audit
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
    audit(session.bind, "admin", "report.regenerate", rep.id, f"order={order.id} chart={chart.id}")
    return {"ok": True, "report_id": rep.id, "status": "queued"}


@router.get("/api/admin/coupons", response_class=JSONResponse)
def admin_coupons(request: Request, session: Session = Depends(get_session)):
    from fastapi import HTTPException
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    return [{"id": c.id, "code": c.code, "percent": c.percent, "max_uses": c.max_uses,
             "used_count": c.used_count, "active": c.active} for c in session.exec(select(Coupon)).all()]


@router.put("/api/admin/plans/{plan_key}")
def api_admin_plan_update(plan_key: str, request: Request, session: Session = Depends(get_session),
                          price_toman: int | None = Form(None), active: bool | None = Form(None)):
    from fastapi import HTTPException
    from app.security import audit
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
    audit(session.bind, "admin", "plan.update", plan.key, f"{plan.price_toman} toman active={plan.active}")
    return {"ok": True}


@router.get("/api/admin/llm-cost")
def api_admin_llm_cost(request: Request, session: Session = Depends(get_session)):
    """H1.3: rich LLM cost dashboard — 24h/7d/30d totals, per-model,
    per-user (top 5), per-kind, fail rate."""
    from fastapi import HTTPException
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    now = datetime.now(timezone.utc)

    def _agg(minutes: int | None) -> dict:
        q = select(LLMRun)
        if minutes:
            q = q.where(LLMRun.created_at >= now - timedelta(minutes=minutes))
        rows = session.exec(q).all()
        by_model: dict[str, float] = {}
        by_kind: dict[str, int] = {}
        by_user: dict[str, float] = {}
        fails = 0
        tokens = 0
        for r in rows:
            by_model[r.model] = by_model.get(r.model, 0) + r.cost_usd
            by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
            if r.user_id:
                by_user[r.user_id] = by_user.get(r.user_id, 0) + r.cost_usd
            if not r.ok:
                fails += 1
            tokens += r.prompt_tokens + r.completion_tokens
        top_users = sorted(by_user.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {
            "cost_usd": round(sum(r.cost_usd for r in rows), 4),
            "runs": len(rows),
            "fail_rate": round(fails / len(rows), 3) if rows else 0.0,
            "total_tokens": tokens,
            "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
            "by_kind": by_kind,
            "top_users": [{"user_id": u, "cost_usd": round(c, 4)} for u, c in top_users],
        }

    return {"24h": _agg(60 * 24), "7d": _agg(60 * 24 * 7), "30d": _agg(60 * 24 * 30)}
