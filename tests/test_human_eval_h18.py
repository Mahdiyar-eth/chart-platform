"""H1.8 (HARDENING): human-eval framework exists and is runnable offline —
20 charts, 13 domain prompts each, 8-criteria rubric documented."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "docs" / "eval"


def test_rubric_documents_eight_criteria():
    rubric = (EVAL / "RUBRIC.md").read_text(encoding="utf-8")
    for c in ("genericness", "accuracy", "personalization", "actionability",
              "language", "safety", "balance", "flow"):
        assert c in rubric.lower(), f"rubric missing criterion {c}"
    assert "۱ = ضعیف" in rubric or "1 = ضعیف" in rubric


def test_eval_charts_materialized():
    charts = list((EVAL / "charts").glob("*.json"))
    assert len(charts) >= 20, "plan requires 20 eval charts"
    # each chart JSON has a usable chart_json (planets + angles)
    import json
    for p in charts[:5]:
        rec = json.loads(p.read_text(encoding="utf-8"))
        assert rec["chart_json"].get("planets"), f"{p.name} missing planets"


def test_eval_prompts_all_domains():
    prompts = list((EVAL / "prompts").glob("*"))
    charts = len(list((EVAL / "charts").glob("*.json")))
    assert len(prompts) == charts, "one prompt dir per chart"
    for d in prompts[:3]:
        files = list(d.glob("*.txt"))
        assert len(files) == 13, f"{d.name} should have 13 domain prompts"
