"""H1.9 — push (Web Push VAPID) routes extracted from main.py.

Module-level imports from app.main are SAFE here: main.py includes this
router at the very END of its module body, after every helper is defined.
"""
from fastapi import APIRouter, Body, Depends, Request
from sqlmodel import Session

from app.main import get_session

router = APIRouter()


@router.get("/api/push/vapid-public-key")
def push_vapid_public_key():
    """VAPID public key for the browser's pushManager.subscribe()."""
    from fastapi import HTTPException
    from app.push import VAPID_PUBLIC_KEY
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(503, "push not configured")
    return {"key": VAPID_PUBLIC_KEY}


@router.post("/api/push/subscribe")
def push_subscribe(payload: dict | None = Body(default=None),
                   request: Request = None,
                   session: Session = Depends(get_session)):
    """Register a browser push subscription (endpoint + p256dh + auth)."""
    from app.push import subscribe as _subscribe
    from app.auth import get_current_user
    u = get_current_user(request)
    body = payload or {}
    ok = _subscribe(body.get("endpoint", ""), body.get("p256dh", ""),
                    body.get("auth", ""), u.id if u else None, session)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(400, "invalid subscription")
    return {"ok": True}


@router.post("/api/push/unsubscribe")
def push_unsubscribe(payload: dict | None = Body(default=None),
                     session: Session = Depends(get_session)):
    from app.push import unsubscribe as _unsubscribe
    _unsubscribe((payload or {}).get("endpoint", ""), session)
    return {"ok": True}
