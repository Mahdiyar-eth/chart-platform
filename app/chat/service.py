"""Chat service — one grounded turn: intent → retrieve → LLM → answer.
D4 adds chat_stream(): the same pipeline over a real SSE token stream."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.chat.intents import route_question
from app.chat.retrieval import build_chat_prompt, retrieve_context


def _retrieve(question: str, chart_json: dict, report_sections: dict | None,
              focus_areas: list[str] | None, report_id: str | None,
              history=None) -> tuple[dict, dict, str]:
    """Shared retrieval: route + context (+ RAG chunks). Returns (route, ctx, prompt)."""
    route = route_question(question, focus_areas)
    ctx = retrieve_context(chart_json, report_sections, route["domains"])
    # D2: semantic RAG chunks (best-effort — falls back to sections-only)
    if report_id:
        try:
            from app.rag import search_relevant
            ctx["rag_chunks"] = search_relevant(report_id, question)
        except Exception:  # noqa: BLE001 — RAG must never break chat
            ctx["rag_chunks"] = []
    return route, ctx, build_chat_prompt(question, ctx, history=history)


def chat_answer(question: str, chart_json: dict, report_sections: dict | None = None,
                focus_areas: list[str] | None = None, router=None,
                report_id: str | None = None, history=None) -> dict:
    """Sync entry (dev/tests): returns {answer, intent, domains, cost, tokens, provider, model}."""
    route, _ctx, prompt = _retrieve(question, chart_json, report_sections,
                                    focus_areas, report_id, history)

    from app.core.llm import build_chat_router
    from app.chat.retrieval import CHAT_SYSTEM_PROMPT
    rtr = router or build_chat_router()
    # F-09 (audit v5 P1): policy goes in the system message — real trust
    # boundary between the fixed rules and the user's untrusted input.
    res = asyncio.run(rtr.complete(prompt, system=CHAT_SYSTEM_PROMPT,
                                   max_tokens=1024, temperature=0.7))
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


async def chat_stream(question: str, chart_json: dict,
                      report_sections: dict | None = None,
                      focus_areas: list[str] | None = None,
                      router=None, report_id: str | None = None,
                      history=None) -> AsyncIterator[dict]:
    """D4: async generator of events for the SSE endpoint:
      {"type": "intent", ...} once,
      {"type": "token", "text": <accumulated so far>} per chunk,
      {"type": "done", "answer", "provider", "model", "cost_usd", "tokens", "ok"}
      {"type": "error", "message"} if the whole chain failed.
    """
    route, _ctx, prompt = _retrieve(question, chart_json, report_sections,
                                    focus_areas, report_id, history)
    yield {"type": "intent", "intent": route["intent"], "domains": route["domains"]}

    from app.core.llm import build_chat_router
    from app.chat.retrieval import CHAT_SYSTEM_PROMPT
    rtr = router or build_chat_router()
    last = None
    async for chunk in rtr.stream_complete(prompt, system=CHAT_SYSTEM_PROMPT,
                                           max_tokens=1024, temperature=0.7):
        last = chunk
        if chunk.error:
            break
        if chunk.text:
            yield {"type": "token", "text": chunk.text}

    if not last or last.error:
        yield {"type": "error",
               "message": "در حال حاضر سرویس پاسخ‌گویی در دسترس نیست (محدودیت سهمیه). لطفاً چند ساعت بعد تلاش کنید."}
        return
    yield {
        "type": "done",
        "answer": last.text or "",
        "ok": True,
        "cost_usd": last.cost,
        "tokens": last.usage.total,
        "provider": last.provider,
        "model": last.model,
        "intent": route["intent"],
        "domains": route["domains"],
    }
