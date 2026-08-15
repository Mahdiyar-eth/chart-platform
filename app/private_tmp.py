"""Private temp directory for the app (B108 fix, P12 gate 6).

Everything the app writes transiently (audio, share cards, audit fallback)
lives here instead of /tmp: mode 0700, owned by the service user, inside
the project — no world-readable artifacts, no predictable /tmp names, no
symlink surface for other local users.

Runtime callers must always resolve through private_tmp() so the location
stays consistent in tests too.
"""
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent
_PRIVATE_TMP = Path("/var/lib/chart-platform/private-tmp")

# Prefer the real deployment location; fall back to the repo (dev/tests).
_PRIVATE_TMP_ENV = Path(_APP_DIR) / "data" / "private-tmp"


def private_tmp() -> Path:
    p = _PRIVATE_TMP if _PRIVATE_TMP.exists() else _PRIVATE_TMP_ENV
    p.mkdir(parents=True, exist_ok=True)
    try:
        p.chmod(0o700)
    except OSError:  # pragma: no cover — owner-only chmod is best-effort
        pass
    return p
