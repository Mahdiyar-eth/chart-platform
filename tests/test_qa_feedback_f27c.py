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
                calls.append(prompt)
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


def test_debug_calls(monkeypatch):
    calls = []

    class _FakeRes:
        ok = True
        text = '{"insights": [{"insight": "کوتاه"}]}'
        usage = type("U", (), {"total": 0, "prompt_tokens": 0, "completion_tokens": 0})()
        cost = 0.0
        provider = "f"
        model = "f"
        error = None

    class R:
        async def complete(self, prompt, **kw):
            calls.append(prompt)
            return _FakeRes()

    import asyncio
    sec, m = asyncio.run(w.generate_sections_async(
        R(), {}, max_tokens=4096, report_id="r", plan_key="full", user_id="u"))
    assert len(calls) == m["calls"] == m["qa_failures"] >= 13 * 3
    assert any("رد شد" in p for p in calls[:5])


def test_fix_hint_lists_allowed_factors(monkeypatch):
    """F-32c: retry prompt must name the allowed factors for the section."""
    calls = []

    class _FakeRes:
        ok = True
        text = '{"section": "x", "insights": [{"insight": "کوتاه", "evidence": [{"factor": "Mercury", "sign": "Virgo", "house": 6}]}]}'
        usage = type("U", (), {"total": 0, "prompt_tokens": 0, "completion_tokens": 0})()
        cost = 0.0
        provider = "fake"
        model = "fake"
        error = None

    attempt = {"n": 0}

    async def _run():
        class R:
            async def complete(self, prompt, **kw):
                calls.append(prompt)
                attempt["n"] += 1
                if attempt["n"] < 2:
                    return _FakeRes()  # still rejected: Mercury not in karma
                r = _FakeRes()
                r.text = '{"section": "x", "insights": [' \
                         '{"insight": "' + "جمله طولانی " * 20 + '", "evidence": [{"factor": "Node", "sign": "عقرب", "house": 8}]},' \
                         '{"insight": "' + "جمله طولانی " * 20 + '", "evidence": [{"factor": "Pluto", "sign": "عقرب", "house": 4}]}]}'
                return r

        from tests.test_qa_f27_fix import _CHART
        _c = {k: dict(v) for k, v in _CHART.items()}
        _c["planets"] = {k: dict(v) | {"longitude": i * 30.0, "house": i % 12 + 1}
                         for i, (k, v) in enumerate(_CHART["planets"].items())}
        _c["angles"] = {k: dict(v) | {"longitude": 15.0} for k, v in _CHART["angles"].items()}
        sections, metrics = await w.generate_sections_async(
            R(), _c, max_tokens=4096, report_id="rep", plan_key="karma", user_id="user")
        return sections, metrics

    sections, metrics = asyncio.run(_run())
    assert metrics["qa_failures"] >= 1
    assert any("عوامل مجاز این بخش فقط: Node" in p for p in calls)  # whitelist embedded
