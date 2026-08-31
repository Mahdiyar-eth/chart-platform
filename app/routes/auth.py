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
    from app.main import claim_anonymous_charts
    from fastapi import HTTPException
    u = verify_otp(phone, code)
    if not u:
        raise HTTPException(401, "[ZAY-AUTH-001] کد نادرست یا منقضی شده")

    # A5 (F-37) — link the guest's charts to the account they just created.
    #
    # `cap` as a form field never actually arrives: chart_access is httpOnly,
    # so the login page cannot read it and has never posted one. Read the
    # cookie here instead, and claim every chart in it (a guest may well have
    # built more than one before signing up). The explicit `cap` parameter is
    # still honoured for callers that do have a bare token.
    from app.main import _chart_tokens
    caps = list(_chart_tokens(request).values())
    if cap and cap not in caps:
        caps.append(cap)
    if caps:
        session = next(get_session())
        try:
            for token in caps:
                # never steals: claim_anonymous_charts skips owned profiles
                claim_anonymous_charts(session, u, token)
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
