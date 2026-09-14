"""IMD-style district warning colour codes (plan.md §14 Task D).

Stand-in until the real CAP (Common Alerting Protocol) feed lands — see
plan.md §3.3 / Phase 4. For now this reads hand-written fixtures under
data/fixtures/imd_warnings/ in the same envelope shape google_weather._fixture
expects ({"_meta": {...}, "response": {...}}), so the demo never depends on a
live IMD integration.

Named `imd_warnings.py`, not `warnings.py`: this directory is on sys.path[0]
(see tests/conftest.py's sys.path shim, plus how the app is imported), so a
top-level `warnings.py` here shadows the *stdlib* `warnings` module for the
whole process — anyio/starlette import `from warnings import warn` during
`import limits`, and that import breaks (`ImportError: cannot import name
'warn' from 'warnings'`), taking down app startup entirely. Confirmed by
reproducing it locally before renaming.
"""

import json
import logging

import config

_LOG = logging.getLogger("weathergpt.warnings")

_WARNINGS_DIR = config.FIXTURES_DIR / "imd_warnings"

_CACHE: dict[str, dict | None] = {}


def load(city_key: str) -> dict | None:
    """Read and cache the warning fixture for a city key. Returns None (and
    logs) if the file is missing or malformed — never raises, since a missing
    warning is a legitimate "nothing to show" state for the UI."""
    if city_key in _CACHE:
        return _CACHE[city_key]

    path = _WARNINGS_DIR / f"warnings.{city_key}.json"
    if not path.exists():
        _CACHE[city_key] = None
        return None

    try:
        env = json.loads(path.read_text(encoding="utf-8"))
        response = env["response"]
        meta = env["_meta"]
        # Touch the fields callers rely on so a malformed fixture fails here,
        # not deep inside public().
        _ = (response["district"], response["colour"], response["valid_from"],
             response["valid_to"], response["advice"], response["labels"],
             meta["issued_by"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        _LOG.warning("malformed IMD warning fixture for %s (%s): %s", city_key, path, exc)
        _CACHE[city_key] = None
        return None

    _CACHE[city_key] = env
    return env


def public(city_key: str, lang: str) -> dict | None:
    """Flattened shape for the API. Returns None if no warning fixture is
    available for this city (caller decides what that means for the response)."""
    env = load(city_key)
    if env is None:
        return None

    response = env["response"]
    meta = env["_meta"]
    labels = response["labels"]
    label = labels.get(lang) or labels["en"]

    return {
        "city": city_key,
        "district": response["district"],
        "colour": response["colour"],
        "category": response.get("category"),
        "headline": label.get("headline") or labels["en"]["headline"],
        "advice": response["advice"],
        "valid_from": response["valid_from"],
        "valid_to": response["valid_to"],
        "issued_by": meta["issued_by"],
        "source": "fixture",
    }


def cache_clear() -> None:
    _CACHE.clear()
