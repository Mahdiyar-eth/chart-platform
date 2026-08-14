"""F-27c regression: QA rejection reasons are fed back into the retry prompt.

Without feedback the model repeats the same banned word 3× and the section
falls back to generic text (2 of 3 real runtime reports degraded this way).
"""
import asyncio

from app.report import worker as w


def test_retry_includes_qa_feedback(monkeypatch):
    calls = []

    class _FakeRes:
        ok = True
        text = '{"section": "x", "insights": [{"insight": "متن کوتاه است", "evidence": []}]}'
        usage = type("U", (), {"total": 0, "prompt_tokens": 0, "completion_tokens": 0})()
        cost = 0.0
        provider = "fake"
        model = "fake"
        error = None

    class _FakeRouter:
        def __init__(self, prompts, chart, user_id, report_id):
            self._calls = calls

        async def complete(self, prompt, **kw):
            calls.append(prompt)
            return _FakeRes()

    # first two attempts fail QA (short text), third passes with long text
    attempt = {"n": 0}

    async def _run():
        class R(_FakeRouter):
            async def complete(self, prompt, **kw):
                attempt["n"] += 1
                if attempt["n"] < 3:
                    return _FakeRes()
                r = _FakeRes()
                r.text = '{"section": "x", "insights": [' \
                         '{"insight": "' + "جمله طولانی " * 20 + '", "evidence": []},' \
                         '{"insight": "' + "جمله طولانی " * 20 + '", "evidence": []}]}'
                return r

        sections, metrics = await w.generate_sections_async(
            R(None, None, None, None), {}, max_tokens=4096,
            report_id="rep", plan_key="full", user_id="user")
        return sections, metrics

    sections, metrics = asyncio.run(_run())
    assert "identity" in sections  # converged, no fallback
    assert metrics["qa_failures"] >= 2  # every domain retried at least once
    assert metrics["calls"] >= 3
    # F-27c: at least the retry prompt after a rejection carries the reasons
    assert any("رد شد" in p for p in calls[:5])
