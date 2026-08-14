"""Reproduce the QA rejection on a real LLM call (F-27 root cause)."""
import asyncio, os, time
os.environ["APP_ENV"] = "prod"

from app.report.worker import startup
from app.report.qa import parse_section, qa_section
from app.report.prompt_builder import build_prompts_for_plan
from app.db import engine
from sqlmodel import Session
from app.models import Chart

CHART_ID = "14df4cdd-abc6-4bfc-9c7a-7db5c0883037"


async def main():
    ctx = {}
    await startup(ctx)
    router = ctx["router"]
    with Session(engine) as s:
        chart = s.get(Chart, CHART_ID).chart_json
    prompts = build_prompts_for_plan(chart, "basic")
    for domain in ["career", "identity", "emotions"]:
        prompt, _ = prompts[domain]
        for attempt in range(3):
            t0 = time.time()
            res = await router.complete(prompt, max_tokens=8192, temperature=0.6, json_mode=True)
            dt = time.time() - t0
            section = parse_section(res.text)
            errs = qa_section(section, chart, domain) if section else ["invalid JSON"]
            print(f"[{domain}] attempt{attempt+1} ok={res.ok} {dt:.0f}s "
                  f"errs={errs[:3] if errs else 'PASS'} "
                  f"raw_len={len(res.text or '')}")
            if not errs:
                break


asyncio.run(main())
