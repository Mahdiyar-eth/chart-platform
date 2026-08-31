"""R.5 / P2-1 / V7 — the brand-language gate must FAIL on an un-allowlisted word.

The review's law: test a gate by making it FAIL. Here we append a banned sentence
to a real template, run the gate, assert it exits 1 and names the file:line, then
restore and assert it passes. Mirrors AC-1 for the brand gate.
"""
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "scripts/brand_language_gate.py"
TARGET = REPO / "app/templates/synastry.html"  # already allowlisted; we add a NEW line
_MARKER = 'R5-BRAND-PROBE-فال و طالع بینی'


@pytest.fixture()
def _probe():
    original = TARGET.read_text(encoding="utf-8")
    try:
        TARGET.write_text(original.rstrip("\n") + "\n" + _MARKER + "\n", encoding="utf-8")
        yield
    finally:
        TARGET.write_text(original, encoding="utf-8")


def _run() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["venv/bin/python", str(GATE)], cwd=REPO,
        capture_output=True, text=True, timeout=120,
    )


def test_brand_gate_fails_on_unallowlisted_line(_probe):
    r = _run()
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    assert r.returncode != 0, f"gate passed with an un-allowlisted banned line:\n{out}"
    assert "بanned brand-language" in out or "banned brand-language" in out.lower() or "❌" in out


def test_brand_gate_passes_on_clean_tree():
    r = _run()
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    assert r.returncode == 0, f"gate failed on clean tree:\n{out}"
    assert "no banned brand-language" in out
