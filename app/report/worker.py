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
from app.core.llm import (LLM_DAILY_BUDGET_USD, build_section_router, build_router,
                          section_model, today_llm_cost)
from app.db import engine as db_engine
from app.env import IS_PROD
from app.models import BirthProfile, Chart, LLMRun, Report
from app.private_tmp import private_tmp
from app.report.generator import build_report_json
from app.report.prompt_builder import (build_personal_question_prompt,
                                       build_prompts_for_plan, order_domains_by_focus)
from app.report.qa import parse_section, qa_repetition, qa_section
from app.report.renderer import render_report_pdf

log = logging.getLogger("report.worker")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
MAX_RETRIES = 6  # F-31: 3 attempts were not enough for stubborn sections;
                 # each retry now carries the QA reasons + replacement words
                 # F-§11: 4 was not enough for the go account — narrow
                 # whitelists (emotions=Moon only) trip the model repeatedly
# M3: concurrent section generation — bounded by this semaphore. The GO pool
# load-balances across keys internally; raise per key headroom only.
SECTION_CONC = int(os.getenv("SECTION_CONC", "4"))


def fallback_section(domain: str, ctx_info: dict) -> dict:
    """Honest intro-only section when the LLM cannot produce a real one."""
    return {
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


def budget_fallback_sections(chart_json: dict, plan_key: str) -> dict[str, dict]:
    """M9: full fallback section set (no LLM call) when the daily budget is hit."""
    from app.report.prompt_builder import build_prompts_for_plan
    prompts = build_prompts_for_plan(chart_json, plan_key)
    return {d: fallback_section(d, ctx) for d, (_, ctx) in prompts.items()}


async def generate_sections_async(chart: dict, max_tokens: int = 8192,
                                   report_id: str | None = None, plan_key: str = "full",
                                   focus_areas: list[str] | None = None,
                                   personal_question: str | None = None,
                                   router=None,
                                   user_id: str | None = None) -> tuple[dict, dict]:
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

    # M3 (multi-provider plan): sections run CONCURRENTLY (bounded by
    # SECTION_CONC). The GO pool also load-balances keys internally; the
    # per-key breaker protects the whole pipeline from one exhausted account.
    t0 = time.monotonic()
    _sem = asyncio.Semaphore(SECTION_CONC)

    async def _gen_one(domain: str, prompt: str, ctx_info: dict) -> None:
        """Full retry chain for ONE section — runs concurrently with others."""
        async with _sem:
            # M2: per-section routing — each domain gets its own model
            # (pro by default, flash for light sections, admin-overridable).
            ok = False
            for attempt in range(MAX_RETRIES + 1):
                # M2: per-section routing — each domain gets its own model
                # (pro by default, flash for light sections, admin-overridable).
                # A caller-supplied router (tests / external callers) wins.
                r = router if router is not None else build_section_router(domain, section_model(domain))
                res = await r.complete(prompt, max_tokens=max_tokens,
                temperature=0.6, json_mode=True)
                metrics["calls"] += 1
                metrics["total_tokens"] += res.usage.total
                metrics["cost_usd"] += res.cost
                metrics["provider"].add(res.provider)
                try:
                    with Session(db_engine) as _s:
                        _s.add(LLMRun(report_id=report_id, user_id=user_id, kind="report",
                                      provider=res.provider,
                                      model=res.model, gateway=res.provider,
                                      prompt_tokens=res.usage.prompt_tokens,
                                      completion_tokens=res.usage.completion_tokens,
                                      latency_ms=getattr(res, "latency_ms", 0) or 0,
                                      cost_usd=res.cost, ok=res.ok,
                                      error=(res.error or "")[:300],
                                      key_slot=getattr(res, "key_slot", None),
                                      section=domain, attempt=attempt,
                                      error_code=res.error_code,
                                      fallback_used=attempt > 0,
                                      prompt_version=ctx_info.get("prompt_version") if ctx_info else None))
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
                # F-26 (runtime audit): QA rejections used to be silent here, making
                # degraded reports undebuggable — surface the reasons in worker logs
                log.warning("QA fail %s (attempt %d/%d): %s", domain, attempt + 1,
                            MAX_RETRIES + 1, errors[:3])
                if attempt < MAX_RETRIES:
                    metrics["retries"] += 1
                # F-27c (runtime audit): feed the QA reasons back into the next
                # attempt — static prompt rules alone can't stop the model from
                # writing «درمان»/«مرگ»/«ششضلعی»; telling it exactly why the
                # previous draft was rejected converges in one retry.
                # F-31: banned words get concrete replacements — the model kept
                # swapping one banned word for another (مرگ → درمان) because the
                # reason string didn't say what to write instead.
                for _bad, _good in (("درمان", "پیشنهاد/راهکار"), ("دارو", "عادت سالم"),
                                    ("مرگ", "پایان/تحول"), ("بیماری", "چالش تندرستی"),
                                    ("پیشگویی", "نگاه به آینده"), ("پیشگویی", "نگاه به آینده")):
                    errors = [e.replace(_bad, f"{_bad}«← بنویس: {_good}»") for e in errors]
                # F-32c: «خارج از عوامل فعال» without telling the model which
                # factors ARE allowed made it swap one wrong planet for another
                # (Mercury→Jupiter→Mars, 5 failed attempts). Always append the
                # whitelist for this section.
                try:
                    from app.report.rules import evaluate
                    _allowed = sorted({r["factor"] for r in evaluate(chart).get(domain, [])})
                except Exception:  # noqa: BLE001
                    _allowed = []
                if _allowed:
                    errors.append("عوامل مجاز این بخش فقط: " + "، ".join(_allowed))
                # F-§11: numeric demands — «تعداد insight کافی نیست» needs an
                # explicit number, not a vague «بیشتر بنویس» (career fell back
                # 5× with 1 short insight on the go account).
                _hard = []
                for e in errors[:5]:
                    if "کافی نیست" in e or "کوتاه" in e:
                        _hard.append(e + " (حداقل ۴ insight، هرکدام ۵-۷ جمله، جمعاً ۷۰۰-۱۰۰۰ کلمه)")
                    else:
                        _hard.append(e)
                fix_hint = ("\n\n⚠️ تلاش قبلیِ تو برای این بخش به این دلایل رد شد — "
                            "این موارد را دقیقاً رفع کن (به‌ویژه واژه‌های ممنوع را با "
                            "جایگزین پیشنهادی عوض کن و فقط از عوامل مجاز استفاده کن) "
                            "و دوباره بنویس:\n- "
                            + "\n- ".join(_hard))
                prompt = prompt + fix_hint

            if not ok:
                fallback_domains.append(domain)
                sections[domain] = fallback_section(domain, ctx_info)


    await asyncio.gather(*(_gen_one(d, p, c) for d, (p, c) in prompts.items()))
    # M3: preserve declared order (focus reorder / plan order) — completion
    # order under gather is not deterministic.
    sections = {d: sections[d] for d in prompts if d in sections}

    rep = qa_repetition(sections)
    if rep:
        log.info("repetition warnings: %s", rep[:3])
    metrics["provider"] = sorted(metrics["provider"])
    metrics["fallback_domains"] = fallback_domains
    metrics["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    return sections, metrics


async def generate_report_audio(ctx: dict, report_id: str) -> None:
    """H1.5: queued edge-tts audio generation — no more inline TTS in the
    request path. Bounded text (9k chars) → mp3 → R2 → status=ready."""
    import asyncio

    with Session(db_engine) as session:
        rep = session.get(Report, report_id)
        if not rep:
            log.error("audio: report %s not found", report_id)
            return
        if rep.audio_status == "ready":
            return  # idempotent
        rep.audio_status = "generating"
        session.commit()
    try:
        text = "گزارش اختصاصی چارت تولد. "
        with Session(db_engine) as session:
            rep = session.get(Report, report_id)
            for k, v in (rep.sections or {}).items():
                t = (v or {}).get("title", k)
                c = (v or {}).get("content", "")
                text += f"بخش {t}. {' '.join(str(c).split())[:800]} "
                if len(text) > 9000:
                    break
        out = private_tmp() / f"report-audio-{report_id[:8]}.mp3"
        import edge_tts

        async def _gen():
            tts = edge_tts.Communicate(text, "fa-IR-DilaraNeural", rate="+0%")
            await tts.save(str(out))

        await asyncio.to_thread(lambda: asyncio.run(_gen()))
        from app.storage import upload_audio
        key = upload_audio(report_id, str(out))
        out.unlink(missing_ok=True)
        with Session(db_engine) as session:
            rep = session.get(Report, report_id)
            rep.audio_r2_key = key
            rep.audio_status = "ready"
            session.commit()
        log.info("audio ready: %s (%s)", report_id[:8], key)
    except Exception:  # noqa: BLE001
        log.exception("audio generation failed for %s", report_id)
        with Session(db_engine) as session:
            rep = session.get(Report, report_id)
            rep.audio_status = "failed"
            session.commit()


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

        # M9: hard daily cost ceiling — degrade honestly instead of spending
        today = today_llm_cost(db_engine)
        if today >= LLM_DAILY_BUDGET_USD:
            rep.status = "degraded"
            rep.error = (f"daily LLM budget reached (${today:.2f} ≥ ${LLM_DAILY_BUDGET_USD:.2f}) "
                         "— fallback intro-only sections")
            from app.report.worker import budget_fallback_sections
            rep.sections = budget_fallback_sections(chart.chart_json, rep.plan_key or "full")
            rep.metrics = {"fallback": "budget", "llm_cost_today_usd": round(today, 2)}
            session.commit()
            log.warning("report %s degraded: daily LLM budget reached", report_id[:8])
            return

        try:
            # load profile focus_areas + personal_question so the report actually uses them
            profile = session.get(BirthProfile, chart.profile_id) if chart.profile_id else None
            sections, metrics = await generate_sections_async(
                chart.chart_json, report_id=report_id,
                plan_key=rep.plan_key or "full",
                focus_areas=(profile.focus_areas if profile else None),
                personal_question=(profile.personal_question if profile else None),
                router=ctx.get("router"),
                user_id=(profile.user_id if profile else None))
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
            if not rep.r2_key and IS_PROD:
                # audit r4 B4: never silently deliver a local-only report in
                # prod — the local disk is ephemeral; surface it as degraded
                rep.status = "degraded"
                rep.error = "آپلود فایل گزارش در R2 ناموفق بود — گزارش موقتاً محلی است؛ با ادمین تماس بگیرید"
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
        # F-24 (runtime audit): read status INSIDE the session — rep is
        # detached after `with Session(...)` exits; touching rep.status then
        # raised DetachedInstanceError and killed the job AFTER the report was
        # fully generated (8-minute LLM work wasted, ARQ retried it again).
        final_status = rep.status

    if final_status == "done":
        # D2: index chunks for semantic chat retrieval — best-effort, must
        # never fail the report (model load is ~1 min on CPU, worker-side)
        try:
            from app.rag import index_report
            n = await asyncio.to_thread(index_report, report_id)
            log.info("RAG indexed %d chunks for report %s", n, report_id[:8])
        except Exception as e:  # noqa: BLE001
            log.warning("RAG index skipped for %s: %s", report_id[:8], e)


async def startup(ctx: dict) -> None:
    ctx["router"] = build_router()
    log.info("worker started with router")


async def shutdown(ctx: dict) -> None:
    log.info("worker shutdown")


class WorkerSettings:
    functions = [generate_report, generate_report_audio]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 4
    job_timeout = 1800
    max_tries = 5          # H0.4: ARQ-level retry (default already 5 — explicit)
    retry_delay = 15       # seconds before ARQ re-runs a failed job
    keep_result = 120      # keep job results for observability (seconds)


if __name__ == "__main__":  # pragma: no cover — direct async test
    from app.astrology.engine import compute_from_fields

    async def _test():
        from arq import create_pool
        redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        chart = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json
        res = await generate_sections_async(chart)
        print("sections:", len(res[0]), "| cost:", res[1]["cost_usd"], "| calls:", res[1]["calls"])
        await redis.aclose()

    asyncio.run(_test())
