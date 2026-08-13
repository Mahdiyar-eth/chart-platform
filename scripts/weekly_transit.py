#!/usr/bin/env python3
"""Weekly transit delivery — «نگاهی به آسمان هفته» (audit P0-2).

Run every Saturday 07:00 Tehran via system crontab:  `0 7 * * 6`
Usage: venv/bin/python scripts/weekly_transit.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report.weekly import run_weekly_delivery  # noqa: E402


if __name__ == "__main__":
    result = asyncio.run(run_weekly_delivery())
    print(result)
