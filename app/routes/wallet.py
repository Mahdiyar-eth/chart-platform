"""H1.9 — wallet routes extracted from main.py (balance, withdraw, admin resolve).

Module-level imports from app.main are SAFE here: main.py includes this
router at the very END of its module body, after every helper is defined.
"""
from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.main import _is_admin, get_session
from app.models import AuditLog, User, WithdrawalRequest

router = APIRouter()


@router.get("/api/wallet")
def wallet_balance(request: Request, session: Session = Depends(get_session)):
    """Wallet status: balance + referral code + pending withdrawal."""
    from fastapi import HTTPException
    from app.auth import get_current_user
    from app.payment.orders import get_or_create_referral_code
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "login required")
    u = session.get(User, user.id)
    code = get_or_create_referral_code(session, u.id)
    pending = session.exec(select(WithdrawalRequest).where(
        WithdrawalRequest.user_id == u.id,
        WithdrawalRequest.status == "pending")).all()
    return {
        "balance_rial": u.balance_rial or 0,
        "referral_code": code,
        "pending_withdrawals": len(pending),
    }


@router.post("/api/wallet/withdraw")
def wallet_withdraw(request: Request, amount_rial: int = Form(...),
                    session: Session = Depends(get_session)):
    """Request a cash-out; admin pays out manually (status=paid)."""
    from fastapi import HTTPException
    from app.auth import get_current_user
    from app.payment.orders import withdraw_request
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "login required")
    if not withdraw_request(session, user.id, amount_rial):
        raise HTTPException(400, "درخواست نامعتبر (موجودی کافی نیست یا درخواست در انتظار بررسی دارید)")
    return {"ok": True}


@router.post("/api/admin/withdrawals/{wid}/resolve")
def admin_resolve_withdrawal(wid: str, request: Request, status: str = Form("paid"),
                             note: str = Form(""),
                             session: Session = Depends(get_session)):
    """Admin resolves a withdrawal: paid (money sent) or rejected (balance kept)."""
    from fastapi import HTTPException
    from app.payment.orders import resolve_withdrawal
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if not resolve_withdrawal(session, wid, status, note):
        raise HTTPException(400, "invalid withdrawal or state")
    session.add(AuditLog(admin=request.cookies.get("chart_user", ""), action="withdrawal_resolve",
                         entity=wid, details=status))
    session.commit()
    return {"ok": True}
