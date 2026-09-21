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
import glossary

_LOG = logging.getLogger("weathergpt.warnings")

_WARNINGS_DIR = config.FIXTURES_DIR / "imd_warnings"

_CACHE: dict[str, dict | None] = {}

# What public() can say about a city. "No verdict" and "checked, nothing in
# force" are deliberately distinct: with WARNINGS_ENABLED off — the default,
# so every current deploy — the answer is UNAVAILABLE, and a UI must render
# that as "not available", never as a green all-clear (plan.md §2 principle 3).
STATUS_UNAVAILABLE = "unavailable"  # feed off, or no usable fixture for the city
STATUS_CLEAR = "clear"              # feed checked: green, nothing in force
STATUS_ACTIVE = "active"            # yellow / orange / red in force


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
        if response["colour"] not in glossary.COLOURS:  # public() looks the word up
            raise ValueError(f"unknown colour {response['colour']!r}")
    except (OSError, ValueError, KeyError, TypeError) as exc:  # json errors are ValueErrors
        _LOG.warning("malformed IMD warning fixture for %s (%s): %s", city_key, path, exc)
        _CACHE[city_key] = None
        return None

    _CACHE[city_key] = env
    return env


def public(city_key: str, lang: str) -> dict:
    """What the API says about a city's warning, in `lang`:

        {"status": STATUS_*, "warning": {...} | None, "legend": [...]}

    `warning` is the flattened fixture (colour, headline, advice, validity,
    provenance) plus glossary-sourced `colour_label` and `category_label`;
    `category` stays the feed's own text. It is None exactly when status is
    UNAVAILABLE, so a consumer that only knows `warning` (prototype/frontend's
    loadHero) keeps working. Green is CLEAR and the object is still returned:
    it carries the feed's own "nothing in force" headline, validity window
    and issuer, which is what a checked all-clear should show. `legend` is
    glossary.legend(lang), so a banner can explain its colour code without a
    second call.

    UNAVAILABLE covers config.WARNINGS_ENABLED off (the default — the fixture
    is fake data, not a live feed, and shouldn't read as a real alert unless
    someone deliberately turns it on for a demo) and a missing or malformed
    fixture for the city.
    """
    legend = glossary.legend(lang)
    env = load(city_key) if config.WARNINGS_ENABLED else None
    if env is None:
        return {"status": STATUS_UNAVAILABLE, "warning": None, "legend": legend}

    response = env["response"]
    meta = env["_meta"]
    labels = response["labels"]
    label = labels.get(lang) or labels["en"]
    colour = response["colour"]

    warning = {
        "city": city_key,
        "district": response["district"],
        "colour": colour,
        "colour_label": glossary.text(f"colour_word_{colour}", lang),
        "category": response.get("category"),
        "category_label": glossary.category_label(response.get("category"), lang),
        "headline": label.get("headline") or labels["en"]["headline"],
        "advice": response["advice"],
        "valid_from": response["valid_from"],
        "valid_to": response["valid_to"],
        "issued_by": meta["issued_by"],
        "source": "fixture",
    }
    status = STATUS_CLEAR if colour == "green" else STATUS_ACTIVE
    return {"status": status, "warning": warning, "legend": legend}


def cache_clear() -> None:
    _CACHE.clear()
