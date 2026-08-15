"""P12 gate 3 — Web Push delivery proof as a permanent test.

Starts a local TLS receiver, sends a real push through the app's own
send path (pywebpush, real VAPID keys from .env), then DECRYPTS the payload
(http_ece) to prove: VAPID JWT, AES-128-GCM encryption, HTTP transport,
and that the JSON body the client will receive is exactly what the app sent.

Skipped when VAPID is not configured (CI / fresh env).
"""
import base64
import json
import os
import ssl
import threading

import pytest

import app.config  # noqa: F401 — loads .env
import app.push as P

from cryptography.hazmat.primitives.asymmetric import ec
from http.server import BaseHTTPRequestHandler, HTTPServer

pytestmark = pytest.mark.skipif(
    not P.vapid_configured(), reason="VAPID not configured in this environment"
)

_CERT = os.path.join(os.path.dirname(__file__), "..", "data", "test-certs")
_CERT = os.path.abspath(_CERT)


@pytest.fixture(scope="module")
def _cert_files():
    os.makedirs(_CERT, exist_ok=True)
    key = os.path.join(_CERT, "push-key.pem")
    cert = os.path.join(_CERT, "push-cert.pem")
    if not os.path.exists(cert):
        import subprocess
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert, "-days", "1", "-nodes",
            "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
        ], check=True, capture_output=True)
    return key, cert


def test_webpush_real_delivery_decryptable(_cert_files):
    key, cert = _cert_files
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    pub_raw = b"\x04" + pub.x.to_bytes(32, "big") + pub.y.to_bytes(32, "big")
    auth_secret = b"\x00" * 16
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(201)
            self.end_headers()
            self.wfile.write(b'{"messageId":"proof"}')
            received["headers"] = {k.lower(): v for k, v in self.headers.items()}
            received["body"] = body

        def log_message(self, *a):  # silence
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    import requests as _req
    orig = _req.Session.send

    def _send(sess, prep, **kw):
        kw.pop("verify", None)
        return orig(sess, prep, verify=False, **kw)

    _req.Session.send = _send
    try:
        class FakeSub:
            endpoint = f"https://127.0.0.1:{port}/push"
            p256dh = base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode()
            auth = base64.urlsafe_b64encode(auth_secret).rstrip(b"=").decode()

        P._send_one(FakeSub(), "تست زایچه", "پیام push", "https://chart.negar.io/today")
    finally:
        srv.shutdown()
        _req.Session.send = orig

    h = received["headers"]
    body = received["body"]
    assert h.get("content-encoding") == "aes128gcm"
    assert h.get("authorization", "").startswith("vapid t=")  # VAPID JWT sent
    assert len(body) > 100

    from http_ece import decrypt as ece_decrypt
    plain = ece_decrypt(body, private_key=priv, auth_secret=auth_secret,
                        version="aes128gcm")
    payload = json.loads(plain)
    assert payload["title"] == "تست زایچه"
    assert payload["url"] == "https://chart.negar.io/today"
