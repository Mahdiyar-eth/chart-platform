#!/usr/bin/env python3
"""Umami v3 bootstrap: login (admin/umami), set a strong digits-only password,
register the website, and print the tracker snippet.

Credentials are written to /opt/umami-admin.txt (chmod 600) — OUTSIDE the repo.
Idempotent: logs in, rotates the password, creates the website only if absent.
"""
from __future__ import annotations

import json
import secrets
import sys
import urllib.request
import urllib.error

BASE = "https://analytics.negar.io"
# OUTSIDE the repo — never write secrets into the git working tree
ADMIN_FILE = "/opt/umami-admin.txt"


def _post(path: str, body: dict, token: str | None = None) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:300]}


def _get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        BASE + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def main() -> int:
    # 1) login with the shipped default
    tok = _post("/api/auth/login", {"username": "admin", "password": "umami"}).get("token")
    if not tok:
        # maybe password already rotated — read saved creds and retry
        try:
            saved = json.load(open(ADMIN_FILE))
            tok = _post("/api/auth/login", {"username": saved["username"],
                                            "password": saved["password"]}).get("token")
        except Exception:
            pass
    if not tok:
        print("login failed:", _post("/api/auth/login", {"username": "admin", "password": "umami"}))
        return 1

    # 2) digits-only password (MaHDi types on a phone)
    new_pass = f"{secrets.randbelow(10**8):08d}"

    # change password via /api/me/password, then RE-LOGIN (old token is invalidated)
    _post("/api/me/password", {"currentPassword": "umami", "newPassword": new_pass}, token=tok)
    tok = _post("/api/auth/login", {"username": "admin", "password": new_pass}).get("token")
    if not tok:
        print("re-login after password rotation failed")
        return 1

    # 3) register the website if absent
    sites = _get("/api/websites", tok)
    rows = sites.get("data", sites) if isinstance(sites, dict) else sites
    existing = [w for w in rows if isinstance(w, dict) and
                (w.get("domain") == "chart.negar.io" or w.get("name") == "زایچه")]
    if existing:
        wid = existing[0].get("id") or existing[0].get("websiteId")
    else:
        created = _post("/api/websites", {"name": "زایچه", "domain": "chart.negar.io"}, token=tok)
        wid = created.get("id") or created.get("websiteId")
        if not wid:
            print("create website failed:", created)
            return 1

    # 4) persist creds
    with open(ADMIN_FILE, "w") as f:
        f.write(json.dumps({"username": "admin", "password": new_pass,
                            "website_id": wid, "url": BASE}, ensure_ascii=False, indent=2))
    import os
    os.chmod(ADMIN_FILE, 0o600)

    print(f"OK  username=admin  password={new_pass}  website_id={wid}")
    print("Tracker snippet:")
    print(f'<script async src="{BASE}/script.js" data-website-id="{wid}"></script>')
    return 0


if __name__ == "__main__":
    sys.exit(main())
