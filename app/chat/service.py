"""Chat service — one grounded turn: intent → retrieve → LLM → answer."""
from __future__ import annotations

import asyncio

from app.chat.intents import route_question
from app.chat.retrieval import build_chat_prompt, retrieve_context


def chat_answer(question: str, chart_json: dict, report_sections: dict | None = None,
                focus_areas: list[str] | None = None, router=None,
                report_id: str | None = None) -> dict:
    """Sync entry (dev/tests): returns {answer, intent, domains, cost, tokens, provider, model}."""
    route = route_question(question, focus_areas)
    ctx = retrieve_context(chart_json, report_sections, route["domains"])
    # D2: semantic RAG chunks (best-effort — falls back to sections-only)
    if report_id:
        try:
            from app.rag import search_relevant
            ctx["rag_chunks"] = search_relevant(report_id, question)
        except Exception:  # noqa: BLE001 — RAG must never break chat
            ctx["rag_chunks"] = []
    prompt = build_chat_prompt(question, ctx)

    from app.core.llm import build_chat_router
    rtr = router or build_chat_router()
    res = asyncio.run(rtr.complete(prompt, max_tokens=1024, temperature=0.7))
    answer = res.text or ""
    if not answer:
        answer = "در حال حاضر سرویس پاسخ‌گویی در دسترس نیست (محدودیت سهمیه). لطفاً چند ساعت بعد تلاش کنید."
    return {
        "answer": answer,
        "intent": route["intent"],
        "domains": route["domains"],
        "ok": res.ok,
        "cost_usd": res.cost,
        "tokens": res.usage.total,
        "provider": getattr(res, "provider", None),
        "model": getattr(res, "model", None),
    }
