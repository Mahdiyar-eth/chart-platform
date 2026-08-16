"""M5 — LLM run telemetry columns round-trip + error_code classification."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.core.llm import LLMResult, LLMUsage
from app.db import engine
from app.models import LLMRun


def test_error_code_classification():
    ok = LLMResult(text="x", provider="go", model="m", usage=LLMUsage(1, 1))
    assert ok.error_code is None
    empty = LLMResult(text="", provider="go", model="m")
    assert empty.error_code == "empty"
    quota = LLMResult(text="", provider="go", model="m",
                      error="HTTP 429: GoUsageLimitError: Weekly usage limit reached")
    assert quota.error_code == "429"
    free = LLMResult(text="", provider="zen-free", model="m",
                     error="HTTP 429: FreeUsageLimitError: Rate limit exceeded")
    assert free.error_code == "429"
    to = LLMResult(text="", provider="go", model="m", error="ReadTimeout on ...")
    assert to.error_code == "timeout"
    s5 = LLMResult(text="", provider="go", model="m", error="HTTP 502: bad gateway")
    assert s5.error_code == "5xx"


def test_llm_run_telemetry_roundtrip():
    run = LLMRun(report_id="r1", user_id="u1", kind="report", provider="go",
                 model="deepseek-v4-flash", key_slot="go-1", section="career",
                 attempt=1, error_code="429", fallback_used=True,
                 prompt_version="gen-v1", ok=False,
                 error="HTTP 429: GoUsageLimitError")
    with Session(engine) as s:
        s.add(run)
        s.commit()
        rid = run.id
    try:
        with Session(engine) as s:
            got = s.get(LLMRun, rid)
            assert got is not None
            assert got.key_slot == "go-1"
            assert got.section == "career"
            assert got.attempt == 1
            assert got.error_code == "429"
            assert got.fallback_used is True
            assert got.prompt_version == "gen-v1"
            assert got.ok is False
    finally:
        with Session(engine) as s:
            s.exec(select(LLMRun).where(LLMRun.id == rid)).first()
            s.delete(s.get(LLMRun, rid))
            s.commit()
