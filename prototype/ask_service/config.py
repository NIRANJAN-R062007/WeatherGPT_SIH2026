"""Central config for the /ask prototype: paths, API keys, CORS origins.

Keys come from a repo-root .env (gitignored), loaded here once. Nothing raises
at import time — /ask must import with an empty environment (CI has no .env).
Call require() at the point of use to fail loudly with an actionable message.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
ENV_PATH = REPO_ROOT / ".env"

load_dotenv(ENV_PATH)  # no-op if the file is absent

GOOGLE_WEATHER_API_KEY: str | None = os.getenv("GOOGLE_WEATHER_API_KEY")
GOOGLE_WEATHER_BASE = "https://weather.googleapis.com/v1"

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL") or "gemini-flash-latest"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

BHASHINI_USER_ID: str | None = os.getenv("BHASHINI_USER_ID")
BHASHINI_ULCA_API_KEY: str | None = os.getenv("BHASHINI_ULCA_API_KEY")
# Udyat-issued inference key: used as the compute Authorization header when the
# config response carries no per-call inferenceApiKey (the newer Bhashini flow).
BHASHINI_INFERENCE_KEY: str | None = os.getenv("BHASHINI_INFERENCE_KEY")

_origins = (os.getenv("ALLOWED_ORIGINS") or "").strip()
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _origins.split(",") if o.strip()] or ["*"]

# Weather data source: "auto" (live, fixture fallback) | "live" (no fallback) |
# "fixtures" (offline; the demo-morning kill switch).
WEATHER_MODE: str = (os.getenv("WEATHER_MODE") or "auto").lower()


class ConfigError(RuntimeError):
    pass


def require(name: str, value: str | None) -> str:
    """Return value, or raise ConfigError naming the .env key that's missing."""
    if not value:
        raise ConfigError(f"{name} is not set — add it to {ENV_PATH} (see .env.example)")
    return value


def redact(secret: str | None) -> str:
    """first4…last4 for logging — never print a key in full."""
    if not secret:
        return "<unset>"
    if len(secret) <= 8:
        return "…"
    return f"{secret[:4]}…{secret[-4:]}"
