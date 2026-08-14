#!/usr/bin/env python3
"""C3: replace per-request cookies= (deprecated by starlette) with
client.cookies.update() — the recommended API."""
import pathlib
import re

FILES = [
    "tests/test_chat_quota_atomic.py",
    "tests/test_coupon_reservation.py",
    "tests/test_ownership_r4.py",
    "tests/test_payment_state_machine.py",
    "tests/test_refund_lifecycle.py",
    "tests/test_report_audio_r2.py",
    "tests/test_report_idempotent.py",
    "tests/test_subscription_expiry.py",
]

for f in FILES:
    p = pathlib.Path(f)
    src = p.read_text()
    orig = src

    # 1) find all cookie expressions: cookies=ck / cookies=ck2 / cookies=_admin_cookies()
    exprs = sorted(set(re.findall(r"cookies=([A-Za-z_]\w*)(?=[),])", src)), reverse=True)

    # 2) strip the arg from requests
    for e in exprs:
        src = src.replace(f", cookies={e})", ")")
        src = src.replace(f", cookies={e})", ")")
        src = src.replace(f"cookies={e})", ")")

    # 3) inject client.cookies.update(...) right after the cookie var definition
    #    or right after the TestClient(...) line for function-style cookies
    lines = src.split("\n")
    out = []
    client_name = None
    for ln in lines:
        m = re.match(r"^(\s*)(\w+) = TestClient\(", ln)
        if m:
            client_name = m.group(2)
            out.append(ln)
            # function-style cookie source (e.g. _admin_cookies()) — set on client
            for e in exprs:
                if e.endswith("()"):
                    out.append(f"{m.group(1)}{client_name}.cookies.update({e})")
            continue
        m2 = re.match(r"^(\s*)(\w+) = (?:_cookies\(|\{)", ln)
        if m2 and client_name and m2.group(2) in exprs:
            out.append(ln)
            out.append(f"{m2.group(1)}{client_name}.cookies.update({m2.group(2)})")
            continue
        out.append(ln)
    src = "\n".join(out)

    if src != orig:
        p.write_text(src)
        print(f"UPDATED {f}")
    else:
        print(f"no-change {f}")
