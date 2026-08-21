#!/usr/bin/env python3
"""Release stale coupon reservations (audit r4 A10 / C-05).

Orders that were created (reserving a coupon slot) but never paid within the
payment window must give the slot back, otherwise max_uses coupons silently
lock up. Also releases slots of orders stuck in "failed" that somehow skipped
release (defensive sweep — release is idempotent via used_count>0 guard).

Run hourly from cron:  30 * * * *  cd /srv/zayche && venv/bin/python scripts/release_stale_coupons.py >> /var/log/zayche/coupon_sweep.log 2>&1
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config  # noqa: F401 — loads .env
from app.db import engine
from app.payment.orders import sweep_stale_orders
from sqlmodel import Session


def main() -> int:
    with Session(engine) as s:
        released = sweep_stale_orders(s)
    print(f"coupon-sweep: {released} slot(s) released")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
