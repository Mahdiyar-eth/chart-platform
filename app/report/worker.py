"""
ARQ worker — async report generation queue (plan v3.1 §6.4, Redis required).

Run: venv/bin/arq app.report.worker.WorkerSettings
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from arq.connections import RedisSettings
from sqlmodel import Session

import app.config  # noqa: F401 — load .env FIRST
from app.core.llm import build_router
from app.db import engine as db_engine
from app.models import BirthProfile, Chart, LLMRun, Report
from app.report.generator import build_report_json
from app.report.prompt_builder import (build_all_prompts, build_personal_question_prompt,
                                       build_prompts_for_plan, order_domains_by_focus)
from app.report.qa import parse_section, qa_repetition, qa_section
from app.report.renderer import render_report_pdf

log = logging.getLogger("report.worker")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
MAX_RETRIES = 2


async def generate_sections_async(router, chart: dict, max_tokens: int = 8192,
                                   report_id: str | None = None, plan_key: str = "full",
                                   focus_areas: list[str] | None = None,
                                   personal_question: str | None = None) -> tuple[dict, dict]:
    """Plan-aware section generation (plan v3.0 §10.3): basic=5, full=13, gold=13+islamic.
    focus_areas reorders domains (focused first); personal_question adds an extra section."""
    prompts = build_prompts_for_plan(chart, plan_key)
    # reorder to fulfill the focus-area promise (focused domains first)
    if focus_areas:
        ordered = order_domains_by_focus(list(prompts.keys()), focus_areas)
        prompts = {k: prompts[k] for k in ordered if k in prompts}
    # optional personal question → extra section
    if personal_question and personal_question.strip():
        prompts["personal_question"] = build_personal_question_prompt(chart, personal_question.strip())
    # admin prompt overrides (plan v3.0 §8) — swap content, keep meta
    from app.report.prompt_overrides import get_overrides
    for key, content in get_overrides().items():
        if key in prompts:
            prompts[key] = (content, prompts[key][1])
    sections: dict[str, dict] = {}
    fallback_domains: list[str] = []
    metrics = {"calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
               "qa_failures": 0, "provider": set()}

    for domain, (prompt, ctx_info) in prompts.items():
        ok = False
        for attempt in range(MAX_RETRIES + 1):
            res = await router.complete(prompt, max_tokens=max_tokens, temperature=0.6, json_mode=True)
            metrics["calls"] += 1
            metrics["total_tokens"] += res.usage.total
            metrics["cost_usd"] += res.cost
            metrics["provider"].add(res.provider)
            try:
                with Session(db_engine) as _s:
                    _s.add(LLMRun(report_id=report_id, provider=res.provider,
                                  model=res.model, gateway=res.provider,
                                  prompt_tokens=res.usage.prompt_tokens,
                                  completion_tokens=res.usage.completion_tokens,
                                  cost_usd=res.cost, ok=res.ok,
                                  error=(res.error or "")[:300]))
                    _s.commit()
            except Exception:  # noqa: BLE001 — metering must never break generation
                pass
            if not res.ok:
                metrics["retries"] += 1
                continue
            section = parse_section(res.text)
            errors = qa_section(section, chart, domain) if section else ["invalid JSON"]
            if not errors:
                sections[domain] = section
                ok = True
                break
            metrics["qa_failures"] += 1
            if attempt < MAX_RETRIES:
                metrics["retries"] += 1

        if not ok:
            fallback_domains.append(domain)
            sections[domain] = {
                "section": domain,
                "title_fa": ctx_info["domain_title"],
                "intro": "بر اساس عوامل محاسبهشده، این حوزه از زندگی اهمیت ویژهای دارد.",
                "insights": [{
                    "insight": "نقشهی نجومی این حوزه را میتوان با دقت بیشتری در گزارش تکمیلی بررسی کرد. "
                               "عوامل فعال: " + (ctx_info["factors"].replace("\n", " — ")[:200]),
                    "evidence": [],
                    "strengths": [], "challenges": [],
                    "practical_advice": "برای تفسیر دقیقتر، به گزارش کامل مراجعه کنید.",
                }],
            }

    rep = qa_repetition(sections)
    if rep:
        log.info("repetition warnings: %s", rep[:3])
    metrics["provider"] = sorted(metrics["provider"])
    metrics["fallback_domains"] = fallback_domains
    return sections, metrics


async def generate_report(ctx: dict, report_id: str) -> None:
    """ARQ job: sections → DB → PDF."""
    with Session(db_engine) as session:
        rep = session.get(Report, report_id)
        if not rep:
            log.error("report %s not found", report_id)
            return
        chart = session.get(Chart, rep.chart_id)
        if not chart:
            rep.status = "failed"
            rep.error = "chart not found"
            session.commit()
            return

        rep.status = "running"
        session.commit()

        try:
            # load profile focus_areas + personal_question so the report actually uses them
            profile = session.get(BirthProfile, chart.profile_id) if chart.profile_id else None
            sections, metrics = await generate_sections_async(
                ctx["router"], chart.chart_json, report_id=report_id,
                plan_key=rep.plan_key or "full",
                focus_areas=(profile.focus_areas if profile else None),
                personal_question=(profile.personal_question if profile else None))
            rep.sections = sections
            rep.metrics = {**metrics, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

            # render PDF
            chart_json = chart.chart_json
            chart_json["birth"]["city_fa"] = chart_json["birth"].get("city_fa", "")
            report_json = build_report_json(chart_json, sections, rep.metrics)
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            pdf = render_report_pdf(report_json, REPORTS_DIR / f"{report_id}.pdf",
                                    plan_key=rep.plan_key or None)
            rep.pdf_path = str(pdf)
            from app.storage import upload_report
            rep.r2_key = upload_report(report_id, str(pdf))
            fallback = metrics.get("fallback_domains", [])
            if fallback:
                # audit P1-7: never silently deliver a low-quality report
                rep.status = "degraded"
                rep.error = f"بخش‌های ناقص (fallback): {', '.join(fallback)}"
            else:
                rep.status = "done"
        except Exception as e:  # noqa: BLE001
            log.exception("report %s failed", report_id)
            rep.status = "failed"
            rep.error = str(e)[:500]
        session.commit()


async def startup(ctx: dict) -> None:
    ctx["router"] = build_router()
    log.info("worker started with router")


async def shutdown(ctx: dict) -> None:
    log.info("worker shutdown")


class WorkerSettings:
    functions = [generate_report]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 4
    job_timeout = 1800


if __name__ == "__main__":  # pragma: no cover — direct async test
    from app.astrology.engine import compute_from_fields

    async def _test():
        from arq import create_pool
        redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        chart = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json
        res = await generate_sections_async(build_router(), chart)
        print("sections:", len(res[0]), "| cost:", res[1]["cost_usd"], "| calls:", res[1]["calls"])
        await redis.aclose()

    asyncio.run(_test())
