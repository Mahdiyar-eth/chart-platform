"""Secret store — encrypted, DB-backed secrets editable from the admin panel.

Design (per user requirement «ساز و کار رازها از پنل ادمین»):
- Secrets are stored in the `secrets` table, AES-encrypted (Fernet) at rest.
- Master key resolution order:
    1. env `SECRETS_MASTER_KEY` (any string — derived to a Fernet key via SHA256).
    2. persisted key file `data/secrets.key` (chmod 600, auto-created in dev).
- `get_secret(key, env, default)`: DB value (if set) → env var → default.
  So on the NEW server the admin enters keys in the admin panel (→ DB), and
  on the current server env vars keep working. Clearing a DB row reverts to env.
- Values are cached in-process; `invalidate_cache()` is called by the admin
  save endpoint. Module-level constants read at import still need a restart.

SECURITY: values are never logged; admin UI shows masked values only.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets as _secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

import app.config  # noqa: F401  — load .env first

# ─────────────────────────── catalog ───────────────────────────
# Each entry: key (db id), env (env var name), label (fa), group (fa), sensitive.
SECRET_CATALOG: list[dict] = [
    # پرداخت
    dict(key="zarinpal_merchant_id", env="ZARINPAL_MERCHANT_ID",
         label="کد مرچنت زرین‌پال", group="پرداخت", sensitive=True),
    dict(key="zarinpal_sandbox", env="ZARINPAL_SANDBOX",
         label="حالت آزمایشی (sandbox)", group="پرداخت", sensitive=False),
    # ربات‌ها
    dict(key="telegram_bot_token", env="TELEGRAM_BOT_TOKEN",
         label="توکن ربات تلگرام", group="ربات‌ها", sensitive=True),
    dict(key="telegram_webhook_secret", env="TELEGRAM_WEBHOOK_SECRET",
         label="سکرت وب‌هوک تلگرام", group="ربات‌ها", sensitive=True),
    dict(key="bale_bot_token", env="BALE_BOT_TOKEN",
         label="توکن ربات بله", group="ربات‌ها", sensitive=True),
    dict(key="bale_webhook_secret", env="BALE_WEBHOOK_SECRET",
         label="سکرت وب‌هوک بله", group="ربات‌ها", sensitive=True),
    # هوش مصنوعی
    dict(key="go_api_key", env="GO_API_KEY",
         label="کلید OpenCode (Go)", group="هوش مصنوعی", sensitive=True),
    dict(key="go_api_base", env="GO_API_BASE",
         label="آدرس پایه OpenCode", group="هوش مصنوعی", sensitive=False),
    dict(key="deepseek_api_key", env="DEEPSEEK_API_KEY",
         label="کلید مستقیم DeepSeek (اختیاری)", group="هوش مصنوعی", sensitive=True),
    dict(key="report_llm_model", env="REPORT_LLM_MODEL",
         label="مدل گزارش کامل (pro/flash)", group="هوش مصنوعی", sensitive=False),
    dict(key="chat_llm_model", env="CHAT_LLM_MODEL",
         label="مدل گفتگو با چارت (pro/flash)", group="هوش مصنوعی", sensitive=False),
    dict(key="preview_llm_model", env="PREVIEW_LLM_MODEL",
         label="مدل پیش‌نمایش رایگان (pro/flash)", group="هوش مصنوعی", sensitive=False),
    dict(key="report_llm_provider", env="REPORT_LLM_PROVIDER",
         label="پروایدر گزارش کامل (go/deepseek/auto)", group="هوش مصنوعی", sensitive=False),
    dict(key="chat_llm_provider", env="CHAT_LLM_PROVIDER",
         label="پروایدر گفتگو با چارت (go/deepseek/auto)", group="هوش مصنوعی", sensitive=False),
    dict(key="preview_llm_provider", env="PREVIEW_LLM_PROVIDER",
         label="پروایدر پیش‌نمایش رایگان (go/deepseek/auto)", group="هوش مصنوعی", sensitive=False),
    dict(key="llm_order", env="LLM_ORDER",
         label="ترتیب پروایدرها (مثلاً go,deepseek)", group="هوش مصنوعی", sensitive=False),
    dict(key="chat_daily_limit_gold", env="CHAT_DAILY_LIMIT_GOLD",
         label="سهمیه روزانه گفتگو — طلایی", group="هوش مصنوعی", sensitive=False),
    dict(key="chat_daily_limit_monthly", env="CHAT_DAILY_LIMIT_MONTHLY",
         label="سهمیه روزانه گفتگو — ماهانه", group="هوش مصنوعی", sensitive=False),
    # پیامک (OTP)
    dict(key="otp_sms_api_key", env="OTP_SMS_API_KEY",
         label="کلید سرویس پیامک (OTP)", group="پیامک", sensitive=True),
    dict(key="otp_sms_template", env="OTP_SMS_TEMPLATE",
         label="قالب متن پیامک", group="پیامک", sensitive=False),
    # ذخیره‌سازی R2
    dict(key="r2_access_key_id", env="R2_ACCESS_KEY_ID",
         label="کلید دسترسی R2", group="ذخیره‌سازی", sensitive=True),
    dict(key="r2_secret_access_key", env="R2_SECRET_ACCESS_KEY",
         label="کلید مخفی R2", group="ذخیره‌سازی", sensitive=True),
    dict(key="r2_bucket", env="R2_BUCKET",
         label="نام باکت R2", group="ذخیره‌سازی", sensitive=False),
    dict(key="r2_endpoint", env="R2_ENDPOINT",
         label="Endpoint ی R2", group="ذخیره‌سازی", sensitive=False),
    dict(key="r2_region", env="R2_REGION",
         label="منطقه‌ی R2", group="ذخیره‌سازی", sensitive=False),
]

_CATALOG_BY_KEY = {e["key"]: e for e in SECRET_CATALOG}

# ─────────────────────────── master key ───────────────────────────
_KEY_FILE = Path(__file__).resolve().parent.parent / "data" / "secrets.key"


def _derive_fernet_key(master: str) -> bytes:
    """Derive a 32-byte urlsafe-base64 Fernet key from any master string."""
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _load_or_create_master() -> str:
    env_key = os.getenv("SECRETS_MASTER_KEY", "").strip()
    if env_key:
        return env_key
    if _KEY_FILE.exists():
        return _KEY_FILE.read_text().strip()
    # auto-generate + persist (dev / first boot); prod must set env var explicitly
    generated = _secrets.token_urlsafe(32)
    if os.getenv("APP_ENV", "dev") == "prod" and not _KEY_FILE.exists():
        raise RuntimeError(
            "SECRETS_MASTER_KEY is required in prod (secrets encryption key). "
            "Set it in the systemd env file before first boot."
        )
    try:
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _KEY_FILE.write_text(generated)
        _KEY_FILE.chmod(0o600)
    except OSError:
        # read-only FS — fall back to ephemeral (secrets won't survive restart)
        pass
    return generated


_MASTER = _load_or_create_master()
_fernet = Fernet(_derive_fernet_key(_MASTER))

# ─────────────────────────── cache ───────────────────────────
_cache: dict[str, str] = {}


def invalidate_cache() -> None:
    _cache.clear()


# ─────────────────────────── core API ───────────────────────────
def _encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> str | None:
    try:
        return _fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return None


def _db_secret(key: str) -> str | None:
    """Decrypted value from DB, or None if absent/decryption fails/DB down."""
    try:
        from sqlmodel import Session, select

        from app.db import engine
        from app.models import Secret

        with Session(engine) as s:
            row = s.exec(select(Secret).where(Secret.key == key)).first()
        if not row or not row.value_encrypted:
            return None
        return _decrypt(row.value_encrypted)
    except Exception:
        # table missing / DB down / connection refused → treat as "not set"
        return None


def get_secret(key: str, env: str, default: str = "") -> str:
    """DB-backed secret (if set) → env var → default. Cached in-process."""
    if key in _cache:
        return _cache[key]
    val = _db_secret(key)
    if val is None or val == "":
        val = os.getenv(env, default)
    _cache[key] = val or default
    return _cache[key]


def set_secret(key: str, value: str, admin: str = "admin") -> None:
    """Encrypt + upsert. Empty value clears the row (revert to env)."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Secret

    value = (value or "").strip()
    with Session(engine) as s:
        row = s.exec(select(Secret).where(Secret.key == key)).first()
        if value == "":
            if row:
                s.delete(row)
        else:
            if row:
                row.value_encrypted = _encrypt(value)
                row.updated_by = admin
                s.add(row)
            else:
                s.add(Secret(key=key, value_encrypted=_encrypt(value), updated_by=admin))
        s.commit()
    invalidate_cache()


def secret_status() -> list[dict]:
    """Per-catalog status (masked, no raw values) for the admin UI."""
    out: list[dict] = []
    for e in SECRET_CATALOG:
        db_val = _db_secret(e["key"])
        env_val = os.getenv(e["env"], "")
        source = "db" if (db_val is not None and db_val != "") else ("env" if env_val else "unset")
        active = db_val if (db_val is not None and db_val != "") else env_val
        out.append({
            "key": e["key"],
            "env": e["env"],
            "label": e["label"],
            "group": e["group"],
            "sensitive": e["sensitive"],
            "source": source,
            "set": bool(active),
            "masked": _mask(active) if active else "",
        })
    return out


def reveal_secret(key: str) -> str:
    """Admin-only: decrypted current value (DB first, else env)."""
    val = _db_secret(key)
    if val is None or val == "":
        e = _CATALOG_BY_KEY.get(key, {})
        val = os.getenv(e.get("env", ""), "")
    return val or ""


def _mask(value: str) -> str:
    if len(value) <= 6:
        return "•" * len(value)
    return f"{value[:3]}…{value[-3:]}"
