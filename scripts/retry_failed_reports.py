#!/usr/bin/env python3
"""DLQ — retry failed reports (Phase 3 — داده).

Finds Report rows with status='failed' and retry_count < MAX_RETRIES, re-enqueues
them into ARQ, sets status='queued' (on success) and increments retry_count.

Usage:
  scripts/retry_failed_reports.py                 # retry all eligible (≤ limit)
  scripts/retry_failed_reports.py --dry-run       # list only, don't enqueue
  scripts/retry_failed_reports.py --report <id>   # retry one specific report
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, "/root/chart-platform")

import app.config  # noqa: F401 — load .env FIRST
from sqlmodel import Session, select

from app.db import engine
from app.models import Report

MAX_RETRIES = 5
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


async def _enqueue(report_id: str) -> bool:
    from arq import create_pool
    from arq.connections import RedisSettings
    pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await pool.enqueue_job("generate_report", report_id)
    await pool.aclose()
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="DLQ retry for failed reports")
    p.add_argument("--dry-run", action="store_true", help="list only, do not enqueue")
    p.add_argument("--report", help="retry one specific report id")
    p.add_argument("--limit", type=int, default=50)
    args = p.parse_args()

    with Session(engine) as s:
        q = select(Report).where(Report.status == "failed")
        if args.report:
            q = q.where(Report.id == args.report)
        else:
            q = q.where(Report.retry_count < MAX_RETRIES)
        q = q.order_by(Report.created_at).limit(args.limit)
        rows = list(s.exec(q).all())

    if not rows:
        print("no failed reports to retry")
        return 0

    for rep in rows:
        if args.dry_run:
            print(f"[dry] {rep.id[:8]} retry={rep.retry_count} err={str(rep.error)[:70]!r}")
            continue
        try:
            ok = asyncio.run(_enqueue(rep.id))
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FAIL enqueue {rep.id[:8]}: {e}")
        with Session(engine) as s:
            r = s.get(Report, rep.id)
            if r is None:
                print(f"SKIP {rep.id[:8]} (deleted)")
                continue
            r.retry_count += 1
            if ok:
                r.status = "queued"
                r.error = None
            else:
                r.error = "DLQ re-enqueue failed (Redis unavailable)"
            s.add(r)
            s.commit()
        print(f"{'OK ' if ok else 'FAIL'} {rep.id[:8]} retry_count→{rep.retry_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
