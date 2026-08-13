"""Env loader — must be imported FIRST (before app.db / any env reads).

Loads /root/chart-platform/.env (secrets: bot tokens, zarinpal, keys path).
"""
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=False)
