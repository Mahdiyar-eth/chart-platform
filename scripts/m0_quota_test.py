"""M0 — Quota Experiment: prove whether 2 GO keys give independent quotas.

Run:  cd /root/chart-platform && venv/bin/python scripts/m0_quota_test.py
Reads keys from env GO_API_KEY (key1) and GO_API_KEY_2 (key2).
Prints masked stats only — never the keys.
"""
import asyncio, os, sys, time, json
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DOTENV_LOADED", "1")
import app.config  # noqa: F401 — loads .env

GO_BASE = "https://opencode.ai/zen/go/v1"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "Chrome/126.0 Safari/537.36")

K1 = os.getenv("GO_API_KEY", "")
K2 = os.getenv("GO_API_KEY_2", "")
if not K1 or not K2:
    print("FATAL: GO_API_KEY and GO_API_KEY_2 required in .env"); sys.exit(1)


async def call(client: httpx.AsyncClient, key: str, label: str, i: int, model: str = "deepseek-v4-flash") -> dict:
    t0 = time.monotonic()
    try:
        r = await client.post(
            f"{GO_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
            json={"model": model, "messages": [{"role": "user", "content": f"بگو: سلام {i}"}],
                  "max_tokens": 20, "temperature": 0.0,
                  "thinking": {"type": "disabled"}},
            timeout=60.0,
        )
        dt = round((time.monotonic() - t0) * 1000)
        if r.status_code == 200:
            j = r.json()
            text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = j.get("usage", {})
            return {"label": label, "i": i, "ok": True, "empty": not (text or "").strip(),
                    "latency_ms": dt, "prompt_t": usage.get("prompt_tokens"), "comp_t": usage.get("completion_tokens")}
        body = r.text[:120]
        return {"label": label, "i": i, "ok": False, "empty": False,
                "latency_ms": dt, "http": r.status_code, "body": body}
    except Exception as e:  # noqa: BLE001
        dt = round((time.monotonic() - t0) * 1000)
        return {"label": label, "i": i, "ok": False, "empty": False,
                "latency_ms": dt, "exc": str(e)[:120]}


async def run_batch(client, key: str, label: str, n: int) -> list[dict]:
    return await asyncio.gather(*(call(client, key, label, i) for i in range(n)))


def report(res: list[dict], title: str) -> None:
    ok = [r for r in res if r.get("ok") and not r.get("empty")]
    empty = [r for r in res if r.get("ok") and r.get("empty")]
    err = [r for r in res if not r.get("ok")]
    lat = [r["latency_ms"] for r in res if r.get("ok")]
    print(f"\n=== {title} ===")
    print(f"  ok+text: {len(ok)} | empty-200: {len(empty)} | errors: {len(err)}")
    if lat:
        print(f"  latency: min={min(lat)}ms median={sorted(lat)[len(lat)//2]}ms max={max(lat)}ms")
    for r in err[:4]:
        print(f"  ERR[{r['i']}]: http={r.get('http')} exc={r.get('exc')} body={r.get('body')}")


async def main() -> None:
    async with httpx.AsyncClient() as client:
        print(f"key1 masked: {K1[:8]}...  key2 masked: {K2[:8]}...")
        # 1) key1 alone
        r1 = await run_batch(client, K1, "K1", 5)
        report(r1, "K1 alone (5 concurrent)")
        # 2) key2 alone
        r2 = await run_batch(client, K2, "K2", 5)
        report(r2, "K2 alone (5 concurrent)")
        # 3) both keys, 10 concurrent (5+5 interleaved)
        both = await asyncio.gather(
            run_batch(client, K1, "K1", 5),
            run_batch(client, K2, "K2", 5),
        )
        report(both[0] + both[1], "BOTH keys (10 concurrent: 5+5)")
        # 4) zen free flash via key2 (zen/v1 base, not go/v1)
        t0 = time.monotonic()
        try:
            r = await client.post(
                "https://opencode.ai/zen/v1/chat/completions",
                headers={"Authorization": f"Bearer {K2}", "User-Agent": UA},
                json={"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "بگو: سلام"}],
                      "max_tokens": 20, "temperature": 0.0},
                timeout=60.0,
            )
            dt = round((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                j = r.json()
                text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
                print(f"\n=== ZEN free flash via K2 ===\n  http=200 text={text[:40]!r} latency={dt}ms")
            else:
                print(f"\n=== ZEN free flash via K2 ===\n  http={r.status_code} body={r.text[:150]}")
        except Exception as e:  # noqa: BLE001
            print(f"\n=== ZEN free flash via K2 ===\n  exc={str(e)[:150]}")


if __name__ == "__main__":
    asyncio.run(main())
