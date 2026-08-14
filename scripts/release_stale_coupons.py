#!/usr/bin/env python3
"""Release stale coupon reservations (audit r4 A10).

Orders that were created (reserving a coupon slot) but never paid within the
payment window must give the slot back, otherwise max_uses coupons silently
lock up. Also releases slots of orders stuck in "failed" that somehow skipped
release (defensive sweep — release is idempotent via used_count>0 guard).

Run hourly from cron:  30 * * * *  cd /srv/zayche && venv/bin/python scripts/release_stale_coupons.py >> /var/log/zayche/coupon_sweep.log 2>&1
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config  # noqa: F401 — loads .env
from app.db import engine
from app.timeutil import utcnow
from sqlmodel import Session, select

STALE_MINUTES = int(os.getenv("COUPON_STALE_MINUTES", "30"))


def main() -> int:
    released = 0
    with Session(engine) as s:
        from app.models import Coupon, Order
        from sqlalchemy import text
        # pending orders older than the payment window
        stale = s.exec(select(Order).where(
            Order.status == "pending",
            Order.created_at < utcnow() - timedelta(minutes=STALE_MINUTES),
        )).all()
        for o in stale:
            if o.coupon_id:
                c = s.get(Coupon, o.coupon_id)
                if c and c.used_count > 0:
                    c.used_count -= 1
                    released += 1
            o.status = "failed"  # give the user a fresh attempt
            s.add(o)
        # defensive: failed orders still holding a slot (belt & suspenders)
        bad = s.exec(text(
            "SELECT o.id FROM orders o JOIN coupons c ON c.id = o.coupon_id "
            "WHERE o.status = 'failed' AND o.coupon_id IS NOT NULL "
            "AND c.used_count > 0"
        )).all()
        if bad:
            rows = s.exec(text(
                "UPDATE coupons SET used_count = used_count - 1 "
                "FROM orders o WHERE o.coupon_id = coupons.id "
                "AND o.status = 'failed' AND coupons.used_count > 0 RETURNING coupons.id"
            )).all()
            released += len(rows)
        s.commit()
    print(f"coupon-sweep: {released} slot(s) released")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
