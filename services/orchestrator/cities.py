"""Shared demo-city registry, loaded once from data/cities.json.

The frontend keeps its own copy in WeatherGPT.dc.html until it fetches
GET /cities; data/cities.json is the source both sides track.
"""

import json
import re
from dataclasses import dataclass

from config import DATA_DIR

_PATH = DATA_DIR / "cities.json"


@dataclass(frozen=True)
class City:
    key: str
    lat: float
    lon: float
    names: dict
    region: dict
    timezone: str
    aliases: tuple
    place_id: str  # GeoNames id, shared with the gazetteer (location.py)


def _load() -> dict:
    raw = json.loads(_PATH.read_text(encoding="utf-8"))
    cities = {}
    for c in raw["cities"]:
        cities[c["key"]] = City(
            key=c["key"], lat=c["lat"], lon=c["lon"],
            names=c["names"], region=c["region"],
            timezone=c["timezone"], aliases=tuple(c.get("aliases", [])),
            place_id=c["place_id"],
        )
    return cities


try:
    CITIES: dict[str, City] = _load()
except (OSError, KeyError, ValueError) as exc:
    raise RuntimeError(f"could not load city registry from {_PATH}: {exc}") from exc

CITY_KEYS = frozenset(CITIES)


_TAMIL_PULLI = "்"  # "்" — virama; case suffixes (e.g. -இல்) commonly elide it,
                          # e.g. கோயம்புத்தூர் + இல் -> கோயம்புத்தூரில், which no
                          # longer contains the bare name as a substring.


def _names_for(city: City) -> list[str]:
    names = [city.key, *(n.lower() for n in city.names.values() if n),
             *(a.lower() for a in city.aliases)]
    names += [n[:-1] for n in names if n.endswith(_TAMIL_PULLI)]
    return names


def resolve(text: str | None) -> str | None:
    """Map free text (a query, or a city name in EN/TA, or an alias) to a canonical key."""
    if not text:
        return None
    s = text.strip().lower()
    if s in CITIES:
        return s
    for key, city in CITIES.items():
        if s in _names_for(city):
            return key
    for key, city in CITIES.items():  # substring: "...weather in chennai" -> chennai
        if any(name in s for name in _names_for(city)):
            return key
    return None


def mentions(text: str | None) -> list[tuple[str, int, int]]:
    """Every registry city named in `text`, as `(key, start, end)` in reading
    order. Unlike `resolve()`, which returns the first city it finds, this
    finds them all — a route names two. Where names overlap the longer wins
    ("new delhi" over "delhi"). Latin names must stand alone as words;
    Indic names may carry case suffixes, so they match as substrings."""
    if not text:
        return []
    s = text.lower()
    spans: list[tuple[int, int, str]] = []
    for key, city in CITIES.items():
        for name in set(_names_for(city)):
            if not name:
                continue
            pattern = re.escape(name)
            if name.isascii():
                pattern = rf"(?<![a-z]){pattern}(?![a-z])"
            spans += [(m.start(), m.end(), key) for m in re.finditer(pattern, s)]
    spans.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    out: list[tuple[str, int, int]] = []
    last_end = -1
    for start, end, key in spans:
        if start >= last_end:  # not inside the previous (longer or earlier) match
            out.append((key, start, end))
            last_end = end
    return out


def display_name(key: str | None, lang: str) -> str:
    city = CITIES.get(key or "")
    if not city:
        return key or ""
    return city.names.get(lang) or city.names["en"]


def as_public_list() -> list[dict]:
    return [
        {"key": c.key, "lat": c.lat, "lon": c.lon, "names": c.names,
         "region": c.region, "timezone": c.timezone}
        for c in CITIES.values()
    ]
