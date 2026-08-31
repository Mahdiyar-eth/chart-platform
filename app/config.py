"""Env loader — must be imported FIRST (before app.db / any env reads).

Loads the repo-root .env (secrets: bot tokens, zarinpal, keys path) — path resolved relative to this file, never hardcoded.
"""
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=False)
