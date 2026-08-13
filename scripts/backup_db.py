#!/usr/bin/env python3
"""chart-platform DB + config backup → Cloudflare R2.

Independent of the app (cron-friendly). Captures:
  - pg_dump -Fc of chart_platform (full DB)
  - .env (config — includes SECRETS_MASTER_KEY, DATABASE_URL)
Zips them together and uploads to R2 under `backups/chart-platform/`.

Retention: local 7 days, R2 30 days.
Output: prints NOTHING on success (cron no_agent = silent); prints errors on failure.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/root/chart-platform")
ENV_FILE = BASE / ".env"
BACKUP_DIR = Path("/root/backups/chart-platform")
R2_PREFIX = "backups/chart-platform"
LOCAL_RETENTION_DAYS = 7
R2_RETENTION_DAYS = 30


def _load_env() -> None:
    """Load .env into os.environ (matches app.config behaviour)."""
    if ENV_FILE.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE)
        except Exception:  # noqa: BLE001
            pass


def _r2_client():
    import boto3
    endpoint = os.getenv("R2_ENDPOINT", "")
    if endpoint and not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
        region_name=os.getenv("R2_REGION", "auto") or "auto",
    )


def main() -> int:
    _load_env()
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("FAIL: DATABASE_URL not set")
        return 1
    if not ENV_FILE.exists():
        print("FAIL: .env not found (config backup impossible)")
        return 1

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_path = BACKUP_DIR / f"chart_platform_{ts}.dump"
    zip_path = BACKUP_DIR / f"chart_backup_{ts}.zip"

    # 1) pg_dump
    try:
        subprocess.run(
            ["pg_dump", db_url, "-Fc", "-f", str(dump_path)],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"FAIL: pg_dump error: {e.stderr[:500]}")
        return 1

    # 2) zip dump + .env
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(dump_path, arcname=dump_path.name)
            z.write(ENV_FILE, arcname=".env")
        dump_path.unlink()  # dump kept only inside the zip
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: zip error: {e}")
        return 1

    # 3) upload to R2
    bucket = os.getenv("R2_BUCKET", "hermes-voice-clone")
    try:
        client = _r2_client()
        client.upload_file(str(zip_path), bucket, f"{R2_PREFIX}/{zip_path.name}")
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: R2 upload error: {e}")
        return 1

    # 4) retention — local
    cutoff = time.time() - LOCAL_RETENTION_DAYS * 86400
    for f in BACKUP_DIR.glob("chart_backup_*.zip"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass

    # 5) retention — R2 (best-effort)
    try:
        r2_cutoff = datetime.now(timezone.utc).timestamp() - R2_RETENTION_DAYS * 86400
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=R2_PREFIX):
            for obj in page.get("Contents", []):
                if obj["LastModified"].timestamp() < r2_cutoff:
                    client.delete_object(Bucket=bucket, Key=obj["Key"])
    except Exception:  # noqa: BLE001 — retention must not fail the backup
        pass

    return 0  # silent on success


if __name__ == "__main__":
    sys.exit(main())
