"""Secret store tests — encryption, DB-over-env precedence, admin auth."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.config  # noqa: F401 — load .env (ADMIN_PIN etc.)
from fastapi.testclient import TestClient

from app.secret_store import _decrypt, _encrypt, get_secret, invalidate_cache, secret_status, set_secret

TEST_KEY = "test_probe_secret"  # not in catalog — safe to create/delete
ENV_NAME = "TEST_SECRET_ENV_PROBE"


def test_encrypt_decrypt_roundtrip():
    tok = _encrypt("s3cret-مقدار-۱۲۳")
    assert tok != "s3cret-مقدار-۱۲۳"
    assert _decrypt(tok) == "s3cret-مقدار-۱۲۳"


def test_decrypt_garbage_returns_none():
    assert _decrypt("not-a-valid-fernet-token") is None


def test_get_secret_env_fallback_when_db_empty():
    invalidate_cache()
    os.environ[ENV_NAME] = "env-value"
    try:
        assert get_secret("test_unset_key_xyz", ENV_NAME, "dflt") == "env-value"
    finally:
        os.environ.pop(ENV_NAME, None)
        invalidate_cache()


def test_set_secret_db_wins_over_env():
    os.environ[ENV_NAME] = "env-value"
    try:
        set_secret(TEST_KEY, "db-value")
        assert get_secret(TEST_KEY, ENV_NAME, "dflt") == "db-value"
    finally:
        set_secret(TEST_KEY, "")  # cleanup
        os.environ.pop(ENV_NAME, None)


def test_clear_secret_reverts_to_env():
    set_secret(TEST_KEY, "db-value")
    set_secret(TEST_KEY, "")  # clear → row deleted
    os.environ[ENV_NAME] = "env-value"
    try:
        assert get_secret(TEST_KEY, ENV_NAME, "dflt") == "env-value"
    finally:
        os.environ.pop(ENV_NAME, None)


def test_secret_status_covers_catalog_and_masks():
    rows = secret_status()
    keys = {r["key"] for r in rows}
    for expected in ("zarinpal_merchant_id", "telegram_bot_token", "go_api_key",
                     "r2_secret_access_key", "otp_sms_api_key"):
        assert expected in keys
    # sensitive set values are masked, never raw
    for r in rows:
        if r["set"]:
            assert r["masked"]
            assert r["source"] in ("db", "env")


def test_admin_secrets_endpoints_require_auth():
    from app.main import app
    client = TestClient(app)
    assert client.get("/api/admin/secrets").status_code == 403
    assert client.post("/api/admin/secrets/zarinpal_merchant_id",
                       data={"value": "x"}).status_code == 403
    assert client.post("/api/admin/secrets/zarinpal_merchant_id/reveal").status_code == 403


def test_admin_secrets_full_flow_authenticated():
    from app.main import _admin_cookie_value, app
    client = TestClient(app)
    client.cookies.set("chart_admin", _admin_cookie_value())
    # list
    r = client.get("/api/admin/secrets")
    assert r.status_code == 200 and "secrets" in r.json()
    # set
    r2 = client.post("/api/admin/secrets/zarinpal_merchant_id", data={"value": "test-merchant"})
    assert r2.status_code == 200 and r2.json()["ok"] is True
    # reveal
    r3 = client.post("/api/admin/secrets/zarinpal_merchant_id/reveal")
    assert r3.json()["value"] == "test-merchant"
    # clear (empty value) → revert to env
    r4 = client.post("/api/admin/secrets/zarinpal_merchant_id", data={"value": ""})
    assert r4.json()["set"] is False
    # unknown key → 404
    r5 = client.post("/api/admin/secrets/no_such_key", data={"value": "x"})
    assert r5.status_code == 404
