"""M1 smoke — live KeyPool test with the real GO keys (chat part, flash model)."""
import asyncio
import sys

sys.path.insert(0, "/root/chart-platform")
import app.config  # noqa: F401 — loads .env

from app.core.llm import build_router


async def main():
    r = build_router("chat")
    for p in r.providers.values():
        n_slots = len(getattr(p, "slots", [])) if hasattr(p, "slots") else 0
        print(f"provider: {p.name} ({type(p).__name__}, slots={n_slots})")
    res = await r.complete("به فارسی بگو: سلام از تست pool", system="تو دستیار هستی",
                           max_tokens=40, temperature=0.3)
    print("ok:", res.ok, "| provider:", res.provider, "| model:", res.model)
    print("text:", (res.text or "")[:70])
    print("err:", (res.error or "")[:100])


asyncio.run(main())
