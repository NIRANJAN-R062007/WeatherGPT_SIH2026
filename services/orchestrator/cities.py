"""Shared demo-city registry, loaded once from data/cities.json.

The frontend keeps its own copy in WeatherGPT.dc.html until it fetches
GET /cities; data/cities.json is the source both sides track.
"""

import json
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


def _load() -> dict:
    raw = json.loads(_PATH.read_text(encoding="utf-8"))
    cities = {}
    for c in raw["cities"]:
        cities[c["key"]] = City(
            key=c["key"], lat=c["lat"], lon=c["lon"],
            names=c["names"], region=c["region"],
            timezone=c["timezone"], aliases=tuple(c.get("aliases", [])),
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
    names = [city.key, city.names["en"].lower(), city.names["ta"].lower(),
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
