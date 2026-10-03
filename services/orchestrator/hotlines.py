"""Emergency numbers per city, loaded once from data/hotlines.json.

Every number there was read off an official government page (source_url)
and its wording kept verbatim (source_quote), so a reader can check it; see
the file's own note. A city gets the national numbers, then its state's
(keyed by the data/cities.json region), then its district's and city's own.
"""

import json
import re

import cities
from config import DATA_DIR

_PATH = DATA_DIR / "hotlines.json"


def _load() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))


try:
    _DATA = _load()
except (OSError, ValueError) as exc:
    raise RuntimeError(f"could not load hotlines from {_PATH}: {exc}") from exc

CHECKED: str = _DATA["checked"]


def entries(city_key: str) -> list[dict]:
    """The raw entries for a registry city, national first."""
    region = cities.CITIES[city_key].region["en"]
    return [*_DATA["national"], *_DATA["regions"].get(region, []),
            *_DATA["cities"].get(city_key, [])]


def public(city_key: str) -> dict:
    """GET /hotlines' body for a registry city: each line's `number` as shown,
    `dial` (digits only, for a tel: link), `name` and `note` (English; the
    apps translate them), `scope` and `source_url`. The quotes stay in the
    data file."""
    return {
        "checked": CHECKED,
        "hotlines": [
            {
                "number": e["number"],
                "dial": re.sub(r"\D", "", e["number"]),
                "name": e["name"],
                "note": e["note"],
                "scope": e["scope"],
                "source_url": e["source_url"],
            }
            for e in entries(city_key)
        ],
    }
