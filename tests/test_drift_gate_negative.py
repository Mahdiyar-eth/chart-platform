"""R.5 / AC-1 / V3 — the drift gate must FAIL when the schema drifts.

The review's P0-1 was that `scripts/drift_gate.sh` used `alembic check && echo ...`,
which put the check on the LEFT of `&&` — exempt from `set -e` — so a drift was
detected yet the gate still exited 0 ("silently green"). The review's law: test a
gate by making it FAIL, not by watching it pass.

This test:
  1. Registers a temporary SQLModel table with NO alembic migration (a drift).
  2. Runs `bash scripts/drift_gate.sh` and asserts it exits NON-ZERO.
  3. Asserts its output does NOT claim "drift gate OK".
  4. Restores app/models.py exactly, re-runs, asserts exit 0 + "DRIFT-GATE: CLEAN".

Guarded by a Postgres reachability check: the drift gate rebuilds a throwaway DB
(`chart_platform_drift`) via the local superuser path, so it only runs where that's
available (CI + this host). It never touches `chart_platform_test`. Marked slow.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Temp drift model. The class name is a unique marker so we can strip it exactly.
_MARK = "class _DriftProbeR5(SQLModel, table=True):"
_DRIFT_MODEL = f"""
{_MARK}
    \"\"\"R.5 temp probe — lets AC-1 (drift gate fails) be tested automatically.\"\"\"
    __tablename__ = "_drift_probe_r5"
    id: int = Field(default=0, primary_key=True)
    note: str = Field(default="")
"""


def _pg_ready() -> bool:
    """True when the local Postgres the drift gate uses is reachable."""
    db = os.environ.get("DATABASE_URL", "")
    if not db:
        return False
    try:
        import sqlalchemy as sa
        e = sa.create_engine(db)
        with e.connect():
            pass
        e.dispose()
        return True
    except Exception:  # noqa: BLE001
        return False


def _append(models_path: Path) -> None:
    models_path.write_text(
        models_path.read_text().rstrip("\n") + "\n\n" + _DRIFT_MODEL.lstrip("\n")
    )


def _strip(models_path: Path, original: str) -> None:
    """Restore models.py to its ORIGINAL bytes (exact) — bulletproof."""
    models_path.write_text(original)


@pytest.mark.slow
def test_drift_gate_fails_on_unmigrated_model():
    if not _pg_ready():
        pytest.skip("local Postgres for the drift gate not reachable")

    models = REPO / "app" / "models.py"
    original = models.read_text()
    assert _MARK not in original, "probe marker already in models.py (bad state)"
    try:
        _append(models)
        assert _MARK in models.read_text()

        r = subprocess.run(
            ["bash", "scripts/drift_gate.sh"], cwd=REPO,
            capture_output=True, text=True, timeout=300,
        )
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        assert r.returncode != 0, (
            "drift gate returned 0 on a drifted schema — the gate is SILENTLY GREEN.\n"
            f"---- output ----\n{out}"
        )
        assert "drift gate OK" not in out.lower(), (
            f"gate claimed 'drift gate OK' despite a drift — the set -e bug is back.\n"
            f"---- output ----\n{out}"
        )
        assert "DRIFT-GATE: FAILED" in out, (
            f"gate did not report the explicit DRIFT-GATE: FAILED marker.\n"
            f"---- output ----\n{out}"
        )
    finally:
        _strip(models, original)
        assert _MARK not in models.read_text(), "probe model left in app/models.py"

    # Healthy path MUST be clean (exit 0 + DRIFT-GATE: CLEAN).
    r2 = subprocess.run(
        ["bash", "scripts/drift_gate.sh"], cwd=REPO,
        capture_output=True, text=True, timeout=300,
    )
    out2 = (r2.stdout or "") + "\n" + (r2.stderr or "")
    assert r2.returncode == 0, f"healthy drift gate returned {r2.returncode}: {out2}"
    assert "DRIFT-GATE: CLEAN" in out2, f"healthy gate did not report CLEAN: {out2}"
