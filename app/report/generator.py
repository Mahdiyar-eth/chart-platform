"""
Report generator — orchestrates the full pipeline (plan v3.1 §6):

Chart JSON → Rule Engine → Prompts → LLM (LLMRouter) → JSON → QA → sections
→ PDF render. Logs cost/tokens/calls per report (Claude review #7).

Phase 3: synchronous worker (ARQ queue comes in the same phase, see worker.py).
"""
from __future__ import annotations

import json
import logging
import time

from app.core.llm import build_router
from app.report.prompt_builder import build_all_prompts, build_prompts_for_plan
from app.report.qa import parse_section, qa_repetition, qa_section

log = logging.getLogger("report")

MAX_RETRIES = 2


def generate_sections(chart: dict, max_tokens: int = 4096, router=None,
                      plan_key: str = "full") -> tuple[dict[str, dict], dict]:
    """Run the plan's section set through the LLM + QA (plan v3.0 §10.3)."""
    router = router or build_router()
    prompts = build_prompts_for_plan(chart, plan_key)
    sections: dict[str, dict] = {}
    metrics = {
        "calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
        "qa_failures": 0, "provider": set(),
    }

    for domain, (prompt, ctx) in prompts.items():
        ok = False
        for attempt in range(MAX_RETRIES + 1):
            res = await_complete(router, prompt, max_tokens)
            metrics["calls"] += 1
            metrics["total_tokens"] += res.usage.total
            metrics["cost_usd"] += res.cost
            metrics["provider"].add(res.provider)
            if not res.ok:
                metrics["retries"] += 1
                continue

            section = parse_section(res.text)
            if section is not None:
                errors = qa_section(section, chart, domain)
            else:
                errors = ["خروجی JSON نامعتبر است"]
            if not errors:
                sections[domain] = section
                ok = True
                break
            metrics["qa_failures"] += 1
            log.warning("QA fail %s (attempt %d): %s", domain, attempt, errors[:2])
            if attempt < MAX_RETRIES:
                metrics["retries"] += 1

        if not ok:
            # last resort: minimal deterministic fallback (never empty section)
            sections[domain] = {
                "section": domain,
                "title_fa": ctx["domain_title"],
                "intro": "بر اساس عوامل محاسبهشده، این حوزه از زندگی اهمیت ویژهای دارد.",
                "insights": [{
                    "insight": "نقشهی نجومی این حوزه را میتوان با دقت بیشتری در گزارش تکمیلی بررسی کرد. "
                               "عوامل فعال: " + (ctx["factors"].replace("\n", " — ")[:200]),
                    "evidence": [],
                    "strengths": [], "challenges": [],
                    "practical_advice": "برای تفسیر دقیقتر، به گزارش کامل مراجعه کنید.",
                }],
            }

    # cross-section repetition check (informational — does not fail the report)
    rep = qa_repetition(sections)
    if rep:
        log.info("repetition warnings: %s", rep[:3])

    metrics["provider"] = sorted(metrics["provider"])
    return sections, metrics


def await_complete(router, prompt: str, max_tokens: int):
    """Sync wrapper over the async LLMRouter (worker will be async later)."""
    import asyncio
    return asyncio.run(router.complete(prompt, max_tokens=max_tokens, temperature=0.6, json_mode=True))


def build_report_json(chart: dict, sections: dict[str, dict], metrics: dict) -> dict:
    """Assemble the final structured report (stored + rendered)."""
    return {
        "chart": chart,
        "sections": sections,
        "metrics": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "calls": metrics.get("calls", 0),
            "retries": metrics.get("retries", 0),
            "total_tokens": metrics.get("total_tokens", 0),
            "cost_usd": round(metrics.get("cost_usd", 0.0), 6),
            "providers": sorted(metrics.get("provider", [])) if isinstance(metrics.get("provider"), (set, list)) else [],
            "qa_failures": metrics.get("qa_failures", 0),
        },
    }
