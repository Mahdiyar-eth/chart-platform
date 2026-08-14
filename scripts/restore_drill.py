#!/usr/bin/env python3
"""Restore drill (audit r4 B2) — proves a backup can actually be restored.

Flow: pick the LATEST age-encrypted backup → decrypt → pg_restore into a
SCRATCH database (never prod) → sanity checks → drop the scratch DB.

Usage:
  scripts/restore_drill.sh [backup_file]      # default: newest .zip.age
Exit 0 on full success; non-zero with a message otherwise.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/root/chart-platform")
import app.config  # noqa: F401 — load .env FIRST (real creds, not hardcoded)

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/root/backups/chart-platform"))
SCRATCH_DB = "chart_platform_drill"


def _scratch_url() -> str:
    """Same host/user as prod DATABASE_URL, scratch DB name.

    Reads the .env FILE directly (never the shell environment) — a stale shell
    DATABASE_URL already broke a restore drill once (2026-08-14, empty-scratch
    backup wiped prod). This drill must be immune to that class of bug.
    """
    from dotenv import dotenv_values
    db = dotenv_values("/root/chart-platform/.env").get("DATABASE_URL", "")
    if not db:
        raise SystemExit("FAIL: DATABASE_URL not set in .env")
    # postgresql://user:pass@host:port/db → swap the db name
    head, _, _rest = db.rpartition("/")
    return f"{head}/{SCRATCH_DB}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("backup", nargs="?", help="path to .zip.age backup")
    args = p.parse_args()

    if args.backup:
        enc = Path(args.backup)
    else:
        candidates = sorted(BACKUP_DIR.glob("chart_backup_*.zip.age"))
        if not candidates:
            print("FAIL: no backups found")
            return 1
        enc = candidates[-1]
    if not enc.exists():
        print(f"FAIL: {enc} not found")
        return 1

    plain = enc.with_suffix("")  # .zip
    dump_out = enc.parent / "drill_latest.dump"
    try:
        subprocess.run(["age", "-d", "-i", "/root/.hermes/keys/chart-platform-age.txt",
                        "-o", str(plain), str(enc)], check=True, capture_output=True, text=True)
        import zipfile
        with zipfile.ZipFile(plain) as z:
            names = [n for n in z.namelist() if n.endswith(".dump")]
            if not names:
                print("FAIL: no .dump inside backup zip")
                return 1
            with z.open(names[0]) as src, open(dump_out, "wb") as dst:
                dst.write(src.read())
    except subprocess.CalledProcessError as e:
        print(f"FAIL: age decrypt: {e.stderr[:300]}")
        return 1

    # drop + recreate the scratch DB (safe: scratch only)
    SCRATCH_URL = _scratch_url()
    try:
        subprocess.run(["sudo", "-u", "postgres", "psql", "-c",
                        f"DROP DATABASE IF EXISTS {SCRATCH_DB}"], check=True, capture_output=True)
        subprocess.run(["sudo", "-u", "postgres", "psql", "-c",
                        f"CREATE DATABASE {SCRATCH_DB} OWNER chart_app"], check=True, capture_output=True)
        subprocess.run(["sudo", "-u", "postgres", "psql", "-d", SCRATCH_DB, "-c",
                        "ALTER SCHEMA public OWNER TO chart_app"], check=True, capture_output=True)
        subprocess.run(["pg_restore", "-d", SCRATCH_URL, "--no-owner", "--no-privileges",
                        str(dump_out)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"FAIL: restore into scratch: {e.stderr[:400]}")
        return 1
    finally:
        plain.unlink(missing_ok=True)
        dump_out.unlink(missing_ok=True)

    # sanity: the scratch DB must actually contain live data
    try:
        plans = subprocess.run(
            ["psql", SCRATCH_URL, "-Atc", "SELECT count(*) FROM plans"],
            check=True, capture_output=True, text=True).stdout.strip()
        users = subprocess.run(
            ["psql", SCRATCH_URL, "-Atc", "SELECT count(*) FROM users"],
            check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"FAIL: sanity query: {e.stderr[:300]}")
        return 1
    if not plans or int(plans or 0) < 5:
        print(f"FAIL: restored DB looks empty (plans={plans!r})")
        return 1
    print(f"OK: restored {enc.name} → {SCRATCH_DB} (plans={plans}, users={users})")

    # cleanup scratch
    subprocess.run(["sudo", "-u", "postgres", "psql", "-c",
                    f"DROP DATABASE IF EXISTS {SCRATCH_DB}"], check=True, capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
