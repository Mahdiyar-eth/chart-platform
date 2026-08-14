"""Centralized environment parsing (audit r4 — A2).

The code used to check `APP_ENV == "prod"` while `.env.example` shipped
`APP_ENV=production`; anyone copying the template silently disabled all
production fail-closed behavior. Now BOTH spellings activate production mode.
Use `IS_PROD` everywhere — never raw `os.getenv("APP_ENV")` comparisons.
"""
from __future__ import annotations

import os

ENV: str = os.getenv("APP_ENV", "dev").lower().strip()
IS_PROD: bool = ENV in ("prod", "production")
