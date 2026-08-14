#!/usr/bin/env python3
"""H0.4 (HARDENING) — stale job recovery.

A report stuck in `running` for longer than STALE_AFTER minutes (worker crash,
OOM kill, redis restart mid-job) never completes on its own: ARQ re-queues the
*arq job*, but the DB row stays `running` forever and the next enqueue of the
same report is blocked (report pipeline refuses duplicate running reports).

This cron re-enqueues stale `running` reports (heartbeat = reports.updated_at)
and flips them back to `queued` so the worker picks them up again.

Usage:
  scripts/recover_stale_reports.py                 # recover all stale (≤ limit)
  scripts/recover_stale_reports.py --dry-run       # list only
  scripts/recover_stale_reports.py --limit 10      # cap recoveries per run
  scripts/recover_stale_reports.py --minutes 90    # stale threshold override
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/chart-platform")

import app.config  # noqa: F401 — load .env FIRST
from sqlmodel import Session, select

from app.db import engine
from app.models import Report

STALE_AFTER_MIN = 60
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--minutes", type=int, default=STALE_AFTER_MIN)
    args = ap.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    with Session(engine) as s:
        stale = s.exec(select(Report).where(
            Report.status == "running",
            Report.updated_at < cutoff,
            Report.retry_count < MAX_RETRIES,
        ).order_by(Report.updated_at.asc()).limit(args.limit)).all()
        if not stale:
            print(f"OK: no stale reports (threshold {args.minutes}m, cutoff {cutoff:%H:%M})")
            return 0
        print(f"STALE: {len(stale)} report(s) stuck in running: "
              + ", ".join(r.id[:8] for r in stale))
        if args.dry_run:
            return 0
        ok = 0
        for r in stale:
            if asyncio.run(_enqueue(r.id)):  # pragma: no cover — real redis path
                r.status = "queued"
                r.retry_count += 1
                s.add(r)
                ok += 1
        s.commit()
        print(f"RECOVERED: {ok}/{len(stale)} re-enqueued (queued + retry_count+1)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
