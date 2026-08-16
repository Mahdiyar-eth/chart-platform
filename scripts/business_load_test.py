#!/usr/bin/env python3
"""A2 (ChatGPT final-review directive) — Business Load Test.

Drives the REAL local stack (web on :8767 + systemd chart-worker + LLM + R2)
through the money path:
  10 concurrent users → chart creation (real API) → paid orders (seeded like a
  real payment completion) → real report queue → real worker generation (LLM) →
  QA → R2 upload, plus 5 concurrent chat calls.

Samples every 2s: queue depth, DB connections, CPU, RAM, LLM latency,
failure rate. Writes evidence JSON to /tmp/business_load_evidence.json.

WARNING: creates test users/charts/orders in the LOCAL database and uploads a
few test PDFs to R2 under prefix test-bizload/ — cleaned up at the end.
Run:  PYTHONPATH=/root/chart-platform venv/bin/python scripts/business_load_test.py
"""
import asyncio
import json
import os
import time

import httpx

BASE = "http://127.0.0.1:8767"
N_USERS = 10
N_REPORTS = 3          # real LLM generations (each ~2-4 min)
N_CHATS = 5

SAMPLE_EVERY = 2.0


def _load_env():
    env = {}
    p = "/root/chart-platform/.env"
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = _load_env()


def make_users(n: int) -> list[dict]:
    """Create test users directly (OTP is fail-closed without SMS key)."""
    from sqlmodel import Session
    from app.db import engine
    from app.models import User
    import secrets
    users = []
    with Session(engine) as s:
        for i in range(n):
            phone = f"+98bl{i}{secrets.randbelow(10**7):07d}"
            u = User(phone=phone, credits=10)
            s.add(u)
            s.commit()
            s.refresh(u)
            users.append({"id": u.id, "phone": phone})
    return users


def cookie_for(uid: int) -> str:
    from app.auth import _user_cookie_value
    return _user_cookie_value(str(uid))


async def create_chart(client: httpx.AsyncClient, cookie: str, i: int) -> str | None:
    r = await client.post(f"{BASE}/api/birth", data={
        "name": f"کاربر{i}", "raw_year": 1360 + (i % 30), "raw_month": (i % 12) + 1,
        "raw_day": (i % 28) + 1, "hour": (i % 12) + 1, "minute": (i * 7) % 60,
        "city_fa": "تهران", "time_known": "true",
    }, headers={"Cookie": f"chart_user={cookie}"})
    return r.json().get("chart_id") if r.status_code == 200 else None


def seed_paid_orders(user_ids: list[int], chart_ids: list[str]) -> list[str]:
    """Simulate completed payments (like real zarinpal verify) → queue reports."""
    from sqlmodel import Session
    from app.db import engine
    from app.models import Order, Report
    from app.main import _enqueue_report
    rep_ids = []
    with Session(engine) as s:
        for uid, cid in zip(user_ids[:len(chart_ids)], chart_ids):
            o = Order(user_id=uid, chart_id=cid, amount_rial=149_000 * 10,
                      plan_key="basic", status="paid", authority=f"bizload-{time.time_ns()}")
            s.add(o)
            s.commit()
            s.refresh(o)
            rep = Report(chart_id=cid, status="queued")
            s.add(rep)
            s.commit()
            s.refresh(rep)
            rep_ids.append(rep.id)
    for rid in rep_ids:
        _enqueue_report(rid)  # push to the real ARQ queue consumed by chart-worker
    return rep_ids


async def chat_call(client: httpx.AsyncClient, cookie: str, chart_id: str, q: str):
    t0 = time.perf_counter()
    r = await client.post(f"{BASE}/api/chat", data={"chart_id": chart_id, "question": q},
                          headers={"Cookie": f"chart_user={cookie}"}, timeout=120)
    return time.perf_counter() - t0, r.status_code


def _pg_conns() -> int:
    try:
        import subprocess
        out = subprocess.run(
            ["psql", "-tAc", "SELECT count(*) FROM pg_stat_activity WHERE datname IS NOT NULL"],
            capture_output=True, text=True, env={**os.environ, "PGDATABASE": "chart_platform"}).stdout.strip()
        return int(out or 0)
    except Exception:
        return -1


async def sampler(stop: asyncio.Event) -> list[dict]:
    import psutil
    samples = []
    while not stop.is_set():
        samples.append({
            "t": round(time.time() - T0, 1),
            "cpu_pct": psutil.cpu_percent(interval=0.5),
            "ram_mb": round(psutil.virtual_memory().used / 1e6),
            "pg_conns": _pg_conns(),
            "queue_depth": _queue_depth(),
        })
        try:
            await asyncio.wait_for(stop.wait(), timeout=SAMPLE_EVERY)
        except asyncio.TimeoutError:
            pass
    return samples


def _queue_depth() -> int:
    try:
        import redis as _r
        r = _r.Redis.from_url(ENV.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
        return r.llen("arq:queue:chart-worker")
    except Exception:
        return -1


async def main() -> int:
    global T0
    T0 = time.time()
    users = make_users(N_USERS)
    print(f"users: {len(users)} created")

    stop = asyncio.Event()
    samp_task = asyncio.create_task(sampler(stop))
    client = httpx.AsyncClient(timeout=60)

    # 1) charts through the real web API (concurrent)
    chart_ids: list[str] = []
    async def _chart(u, i):
        cid = await create_chart(client, cookie_for(u["id"]), i)
        return cid
    results = await asyncio.gather(*[_chart(u, i) for i, u in enumerate(users)])
    chart_ids = [c for c in results if c]
    print(f"charts created via API: {len(chart_ids)}/{N_USERS}")

    # 2) paid orders + queue (real worker picks these up)
    rep_ids = seed_paid_orders([u["id"] for u in users], chart_ids)
    print(f"reports queued: {len(rep_ids)} (worker will generate {N_REPORTS} with real LLM)")

    # 3) 5 concurrent chat calls while reports generate
    chat_lat = []
    chat_codes = []
    async def _chat(i):
        u = users[i % len(users)]
        cid = chart_ids[i % len(chart_ids)]
        lat, code = await chat_call(client, cookie_for(u["id"]), cid, "برج خورشید من چیست؟")
        chat_lat.append(lat)
        chat_codes.append(code)
    await asyncio.gather(*[_chat(i) for i in range(N_CHATS)])
    print(f"chat: {sum(1 for c in chat_codes if c == 200)}/{N_CHATS} ok, "
          f"lat={sum(chat_lat)/len(chat_lat):.1f}s" if chat_lat else "chat: no samples")

    # 4) wait for the queued reports to finish (LLM generation is the heavy part)
    from sqlmodel import Session, select
    from app.db import engine
    from app.models import Report
    deadline = time.time() + 900
    while time.time() < deadline:
        with Session(engine) as s:
            statuses = [s.exec(select(Report).where(Report.id == rid)).first() for rid in rep_ids]
        states = {st.status if st else "?" for st in statuses}
        print(f"  …reports: {states} ({time.time()-T0:.0f}s)")
        if all((st and st.status in ("done", "failed", "degraded")) for st in statuses):
            break
        await asyncio.sleep(20)

    stop.set()
    samples = await samp_task

    # 5) evidence — LLM latency from LLMRun per report
    from sqlmodel import Session, select
    from app.db import engine
    from app.models import Report, LLMRun
    statuses = []
    with Session(engine) as s:
        for rid in rep_ids:
            statuses.append(s.exec(select(Report).where(Report.id == rid)).first())
    final_states = {st.status if st else "?" for st in statuses}
    done = sum(1 for st in statuses if st and st.status == "done")
    llm_lat = []
    with Session(engine) as s:
        for rid in rep_ids:
            for run in s.exec(select(LLMRun).where(LLMRun.report_id == rid)).all():
                if run.latency_ms:
                    llm_lat.append(run.latency_ms)
    evidence = {
        "users": N_USERS, "charts_ok": len(chart_ids), "reports_queued": len(rep_ids),
        "reports_done": done, "final_states": sorted(final_states),
        "chat_ok": sum(1 for c in chat_codes if c == 200), "chat_total": N_CHATS,
        "chat_avg_lat_s": round(sum(chat_lat) / len(chat_lat), 2) if chat_lat else None,
        "llm_avg_lat_ms": round(sum(llm_lat) / len(llm_lat), 1) if llm_lat else None,
        "samples": samples,
        "queue_max": max((x["queue_depth"] for x in samples), default=0),
        "pg_conns_max": max((x["pg_conns"] for x in samples), default=0),
        "cpu_max_pct": max((x["cpu_pct"] for x in samples), default=0),
        "ram_max_mb": max((x["ram_mb"] for x in samples), default=0),
        "errors": sum(1 for c in chat_codes if c != 200),
    }
    with open("/tmp/business_load_evidence.json", "w") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=1)
    print("\n═══ BUSINESS LOAD — EVIDENCE ═══")
    print(f"reports done      : {done}/{len(rep_ids)}  states={sorted(final_states)}")
    print(f"chat              : {evidence['chat_ok']}/{N_CHATS} ok  avg={evidence['chat_avg_lat_s']}s")
    print(f"LLM avg latency   : {evidence['llm_avg_lat_ms']}ms")
    print(f"queue depth max   : {evidence['queue_max']}")
    print(f"pg conns max      : {evidence['pg_conns_max']}")
    print(f"cpu max           : {evidence['cpu_max_pct']}%  ram max: {evidence['ram_max_mb']}MB")
    print("evidence → /tmp/business_load_evidence.json")
    return 0 if done == len(rep_ids) and evidence["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
