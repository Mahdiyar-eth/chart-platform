"""G11 (master-spec §108) — runtime feature flags backed by the encrypted
secret store (DB > env > default), so ops can toggle product surface without
a deploy. Flags are cached in-process like other secrets; admin toggles
invalidate the cache.

Conventions:
  - key:   `feature_<name>`   (DB row key)
  - env:   `FEATURE_<NAME>`   (optional override)
  - value: "on" / "off" / "auto" (auto = default policy)
"""
from app.secret_store import get_secret

_ON = {"on", "1", "true", "yes", "enabled"}


def flag(name: str, default: str = "on") -> bool:
    """Is feature `name` enabled? default ∈ {"on","off","auto"}."""
    val = get_secret(f"feature_{name}", f"FEATURE_{name.upper()}", default).strip().lower()
    if val == "auto":
        val = default
    return val in _ON


def set_flag(name: str, value: str, admin: str = "admin") -> None:
    """Turn a feature on/off at runtime (admin-only callers)."""
    value = value.strip().lower()
    if value not in _ON and value not in {"off", "auto", "0", "false", "no", "disabled"}:
        raise ValueError(f"invalid flag value: {value!r}")
    from app.secret_store import set_secret
    set_secret(f"feature_{name}", "on" if value in _ON else "off", admin=admin)


def all_flags() -> dict:
    """Known flags + current resolved value (for the admin panel)."""
    known = ["chat", "explore", "weekly", "reports", "push", "synastry", "seo_cities"]
    out = {}
    for k in known:
        out[k] = flag(k)
    return out
