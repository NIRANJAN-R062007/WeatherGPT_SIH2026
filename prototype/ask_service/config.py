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

# Second-provider fallback (plan.md §5): tried when Gemini fails, before the
# template. Groq deprecated llama-3.3-70b-versatile in Aug 2026; gpt-oss-120b
# is their recommended replacement — see https://console.groq.com/docs/deprecations
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
GROQ_BASE = "https://api.groq.com/openai/v1"

def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


# Demo kill switch (plan.md §8 Phase 6): fixtures-only weather, Ollama-only
# narration/NLU, Bhashini disabled — for a dead venue network.
OFFLINE_MODE: bool = (os.getenv("OFFLINE_MODE") or "").strip().lower() in ("1", "true", "yes")

OLLAMA_BASE: str = (os.getenv("OLLAMA_BASE") or "http://localhost:11434").rstrip("/")
OLLAMA_MODEL: str | None = os.getenv("OLLAMA_MODEL") or "llama3.2:3b"
OLLAMA_TIMEOUT: float = _float_env("OLLAMA_TIMEOUT", 30.0)

BHASHINI_USER_ID: str | None = os.getenv("BHASHINI_USER_ID")
BHASHINI_ULCA_API_KEY: str | None = os.getenv("BHASHINI_ULCA_API_KEY")
# Udyat-issued inference key: used as the compute Authorization header when the
# config response carries no per-call inferenceApiKey (the newer Bhashini flow).
BHASHINI_INFERENCE_KEY: str | None = os.getenv("BHASHINI_INFERENCE_KEY")

_origins = (os.getenv("ALLOWED_ORIGINS") or "").strip()
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _origins.split(",") if o.strip()] or ["*"]

# Weather data source: "auto" (live, fixture fallback) | "live" (no fallback) |
# "fixtures" (offline; the demo-morning kill switch). OFFLINE_MODE forces
# fixtures regardless of what WEATHER_MODE says.
WEATHER_MODE: str = "fixtures" if OFFLINE_MODE else (os.getenv("WEATHER_MODE") or "auto").lower()

# Supabase project (plan.md §14 Deepthi track). ANON_KEY is the public
# "anon" key — safe in frontend JS. There is no service-role key here on
# purpose: the backend never needs elevated DB access, it only asks
# Supabase's own Auth API to validate a user's session token (see auth.py).
SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY: str | None = os.getenv("SUPABASE_ANON_KEY")


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
