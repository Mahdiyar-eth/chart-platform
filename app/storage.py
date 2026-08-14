"""Cloudflare R2 object storage for report PDFs (plan §11 R2).

Credentials come from chart-platform/.env (R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
R2_ENDPOINT, R2_BUCKET, R2_REGION). Bucket: zayche-storage (own bucket since
2026-08-14 — audit r3: decoupled from voice-clone's shared bucket). R2 buckets
are private: downloads go through 30-min presigned URLs (audit r4 B3).

FAIL-CLOSED (audit r4 B4): in production R2 is mandatory — a misconfigured
deploy must refuse to boot instead of silently serving from ephemeral local
disk. In dev/tests missing creds still degrade gracefully.
"""
import os

import app.config  # noqa: F401 — ensure .env loaded
from app.env import IS_PROD
from app.secret_store import get_secret

R2_ENDPOINT = get_secret("r2_endpoint", "R2_ENDPOINT", "").strip()
R2_BUCKET = get_secret("r2_bucket", "R2_BUCKET", "hermes-voice-clone").strip()
R2_REGION = get_secret("r2_region", "R2_REGION", "auto").strip()
R2_ACCESS = get_secret("r2_access_key_id", "R2_ACCESS_KEY_ID", "").strip()
R2_SECRET = get_secret("r2_secret_access_key", "R2_SECRET_ACCESS_KEY", "").strip()

PREFIX = "chart-reports"  # keep chart-platform objects namespaced in the shared bucket

if IS_PROD and not (R2_ACCESS and R2_SECRET and R2_ENDPOINT):
    raise RuntimeError(
        "R2 storage is REQUIRED in production (audit r4 B4 fail-closed). "
        "Set R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ENDPOINT in .env."
    )


def configured() -> bool:
    return bool(R2_ACCESS and R2_SECRET and R2_ENDPOINT)


def _client():
    if not configured():
        return None
    import boto3
    endpoint = R2_ENDPOINT if R2_ENDPOINT.startswith("http") else f"https://{R2_ENDPOINT}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS,
        aws_secret_access_key=R2_SECRET,
        region_name=R2_REGION or "auto",
    )


def report_key(report_id: str) -> str:
    return f"{PREFIX}/{report_id}.pdf"


def upload_report(report_id: str, local_path: str) -> str | None:
    """Upload a generated PDF to R2. Returns the object key or None."""
    if not configured() or not os.path.exists(local_path):
        return None
    try:
        client = _client()
        client.upload_file(local_path, R2_BUCKET, report_key(report_id))
        return report_key(report_id)
    except Exception:  # noqa: BLE001 — storage must never break the report
        return None


def presigned_url(key: str, expires: int = 1800) -> str | None:
    """30-min presigned GET URL (audit r4 B3 — was 7 days). Every consumer
    (report PDF endpoint) generates a FRESH url per request, so the short TTL
    only limits leaked-link windows, never breaks downloads."""
    if not configured() or not key:
        return None
    try:
        client = _client()
        return client.generate_presigned_url(
            "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=expires
        )
    except Exception:  # noqa: BLE001
        return None


def delete_object(key: str) -> bool:
    """Delete an object from R2 (best-effort). True on success, False otherwise."""
    if not configured() or not key:
        return False
    try:
        client = _client()
        client.delete_object(Bucket=R2_BUCKET, Key=key)
        return True
    except Exception:  # noqa: BLE001 — never raise on cleanup
        return False
