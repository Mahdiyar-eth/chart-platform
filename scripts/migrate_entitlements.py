#!/usr/bin/env python3
"""A6 — backfill entitlements from existing paid orders.

MANDATORY dry-run: without --apply this ONLY reports how many rows would be
created. It writes nothing. Set DATABASE_URL explicitly and NEVER point it at
the production database (the script refuses prod-ish URLs).
"""
import json
import os
import sys


def main() -> int:
    apply_flag = "--apply" in sys.argv
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL must be set explicitly (refusing to guess).")
        return 2
    lower = url.lower()
    if any(b in lower for b in ("prod", "production", "zayche_prod", ":5432/zayche")):
        print("REFUSING: DATABASE_URL looks like production. Use a scratch/QA DB.")
        return 2
    if apply_flag and "--yes" not in sys.argv:
        print("Apply requires --yes confirmation (idempotent but destructive to add rows).")
        return 2

    from sqlmodel import Session
    from app.entitlements import backfill_entitlements
    from app.db import engine

    with Session(engine) as s:
        rep = backfill_entitlements(s, dry_run=not apply_flag)

    rep["mode"] = "APPLY" if apply_flag else "DRY-RUN (no writes)"
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
