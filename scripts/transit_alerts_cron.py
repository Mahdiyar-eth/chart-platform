#!/usr/bin/env python3
"""B4 — weekly transit alerts cron (Saturday 07:10 Tehran → `10 7 * * 6`).

Usage: venv/bin/python scripts/transit_alerts_cron.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.transit_alerts import run_transit_alerts  # noqa: E402


if __name__ == "__main__":
    result = asyncio.run(run_transit_alerts())
    print(result)
