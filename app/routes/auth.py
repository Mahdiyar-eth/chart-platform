"""H1.9 — auth routes extracted from main.py (OTP request/verify, me, logout).

Lazy imports inside handlers avoid the main<->routes circular import at
module load; main.py includes this router at the END of its module body.
"""
from fastapi import APIRouter, Form, Request

router = APIRouter()


@router.post("/api/auth/otp/request")
def auth_otp_request(request: Request, phone: str = Form(...)):
    from app.auth import request_otp
    from app.main import _rate_limit, _rl_client
    if not _rate_limit(f"otp:{_rl_client(request)}", 5, 300):
        from fastapi import HTTPException
        raise HTTPException(429, "[ZAY-AUTH-002] تعداد درخواست کد زیاد است؛ کمی بعد دوباره تلاش کن")
    try:
        return request_otp(phone)
    except RuntimeError as e:
        from fastapi import HTTPException
        code = "ZAY-SMS-001" if "SMS" in str(e) else "ZAY-AUTH-004"
        raise HTTPException(429, f"[{code}] {e}")


@router.post("/api/auth/otp/verify")
def auth_otp_verify(request: Request, phone: str = Form(...), code: str = Form(...),
                    cap: str | None = Form(None)):
    from app.auth import set_user_cookie, verify_otp
    from app.db import get_session
    from app.main import _chart_tokens, claim_anonymous_charts
    from fastapi import HTTPException
    u = verify_otp(phone, code)
    if not u:
        raise HTTPException(401, "[ZAY-AUTH-001] کد نادرست یا منقضی شده")
    # The `cap` form field never actually arrives: chart_access is httpOnly,
    # so the login page is structurally unable to read it. The cookie is the
    # only reliable source, hence the claim happens server-side here.
    # A5 (F-37): link guest chart(s) to the freshly-logged-in user.
    # BUGFIX 2026-08-27: claim from the chart_access COOKIE (all guest charts)
    # as well as the legacy `cap` form field — the login page never sent `cap`,
    # so the guest chart vanished from the dashboard after login.
    tokens = _chart_tokens(request) or {}
    if cap:
        tokens = {**tokens, "_cap": cap}
    if tokens:
        session = next(get_session())
        try:
            for tok in set(tokens.values()):
                claim_anonymous_charts(session, u, tok)  # idempotent per chart
        finally:
            session.close()
    return set_user_cookie(request, u.id)


@router.get("/api/auth/me")
def auth_me(request: Request):
    from app.auth import get_current_user
    u = get_current_user(request)
    if not u:
        return {"user": None}
    return {"user": {"id": u.id, "phone": u.phone, "role": u.role}}


@router.post("/api/auth/logout")
def auth_logout():
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("chart_user")
    return resp
