"""Web Push (D1): VAPID-signed push via pywebpush.

Endpoints are plain HTTP endpoints registered by the browser (push service
stores them); we only store the subscription and fire notifications through
the user's push service (FCM/Mozilla/Apple), never hold message content.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("push")

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").replace("\\n", "\n").strip()
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n").strip()
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@zayche.io")
VAPID_CLAIMS = {"sub": VAPID_SUBJECT}


def vapid_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def subscribe(endpoint: str, p256dh: str, auth: str, user_id: str | None,
              session) -> bool:
    """Insert (or refresh) a subscription. Returns False on bad input."""
    if not endpoint.startswith("https://") or not p256dh or not auth:
        return False
    from sqlmodel import select
    from app.models import PushSubscription
    existing = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).first()
    if existing:
        existing.p256dh, existing.auth, existing.user_id = p256dh, auth, user_id
    else:
        session.add(PushSubscription(endpoint=endpoint, p256dh=p256dh,
                                     auth=auth, user_id=user_id))
    session.commit()
    return True


def unsubscribe(endpoint: str, session) -> None:
    from sqlmodel import select
    from app.models import PushSubscription
    sub = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).first()
    if sub:
        session.delete(sub)
        session.commit()


def send_to_user(user_id: str, title: str, body: str, url: str, session) -> int:
    """Push to every subscription of a user. Returns number sent."""
    if not vapid_configured():
        return 0
    from sqlmodel import select
    from app.models import PushSubscription
    subs = session.exec(select(PushSubscription).where(
        PushSubscription.user_id == user_id)).all()
    sent = 0
    for sub in subs:
        try:
            _send_one(sub, title, body, url)
            sent += 1
        except Exception as e:  # noqa: BLE001 — per-subscription, don't kill batch
            log.warning("push failed %s: %s", sub.endpoint[:60], e)
    return sent


def _send_one(sub, title: str, body: str, url: str) -> None:
    from pywebpush import webpush
    webpush(
        subscription_info={
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        },
        data=json.dumps({"title": title, "body": body, "url": url}),
        vapid_private_key=VAPID_PRIVATE_KEY,
        vapid_claims=VAPID_CLAIMS,
        timeout=10,
    )
