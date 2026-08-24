"""R.6 / U4 — the bash -n gate must FAIL on an unparseable script.

The review's law: test a gate by making it FAIL. `scripts/ci.sh` now runs
`bash -n scripts/*.sh`; an unparseable shell script (like the dead
`runtime_withdrawal_race.sh` had) must turn the build RED, not rot silently.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_bash_n(script: Path) -> int:
    return subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode


def test_bash_n_accepts_parseable_script():
    assert _run_bash_n(ROOT / "scripts" / "ci.sh") == 0
    assert _run_bash_n(ROOT / "scripts" / "deploy.sh") == 0


def test_bash_n_rejects_broken_script():
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        # dangling continuation (the exact bug runtime_withdrawal_race.sh had)
        f.write('#!/bin/bash\nWID="x"\n  -d \'amount=1\' | python3 -c "...")\necho "done"\n')
        bad = Path(f.name)
    try:
        assert _run_bash_n(bad) != 0, "bash -n must flag an unparseable script"
    finally:
        bad.unlink(missing_ok=True)


def test_ci_bash_n_gate_loop_matches_ci_sh():
    """Mirror ci.sh's exact loop: every scripts/*.sh must parse (so the checked-out
    repo is green for the new gate). This is the positive half of the gate's proof."""
    scripts = sorted((ROOT / "scripts").glob("*.sh"))
    assert scripts, "no scripts found to gate"
    for s in scripts:
        assert _run_bash_n(s) == 0, f"scripts/{s.name} does not parse (bash -n failed)"
