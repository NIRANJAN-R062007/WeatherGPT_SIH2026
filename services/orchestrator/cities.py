"""Shared demo-city registry, loaded once from data/cities.json.

The frontend keeps its own copy in WeatherGPT.dc.html until it fetches
GET /cities; data/cities.json is the source both sides track.
"""

import json
import re
import unicodedata
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
    travel_only: bool = False  # TFA-8: a travel-advisory destination, not a demo city


def _load() -> dict:
    raw = json.loads(_PATH.read_text(encoding="utf-8"))
    cities = {}
    for c in raw["cities"]:
        cities[c["key"]] = City(
            key=c["key"], lat=c["lat"], lon=c["lon"],
            names=c["names"], region=c["region"],
            timezone=c["timezone"], aliases=tuple(c.get("aliases", [])),
            place_id=c["place_id"], travel_only=bool(c.get("travel_only")),
        )
    return cities


try:
    # Every entry: the demo cities and the travel-only destinations (TFA-8).
    TRAVEL_CITIES: dict[str, City] = _load()
except (OSError, KeyError, ValueError) as exc:
    raise RuntimeError(f"could not load city registry from {_PATH}: {exc}") from exc

# The demo cities: what /ask, /cities, offline mode, hotlines and the gazetteer know.
# A travel-only destination is only ever reached through `travel=True` below.
CITIES: dict[str, City] = {k: c for k, c in TRAVEL_CITIES.items() if not c.travel_only}
CITY_KEYS = frozenset(CITIES)
TRAVEL_KEYS = frozenset(TRAVEL_CITIES)


_TAMIL_PULLI = "்"  # "்" — virama; case suffixes (e.g. -இல்) commonly elide it,
                          # e.g. கோயம்புத்தூர் + இல் -> கோயம்புத்தூரில், which no
                          # longer contains the bare name as a substring.


def _names_for(city: City) -> list[str]:
    names = [city.key, *(n.lower() for n in city.names.values() if n),
             *(a.lower() for a in city.aliases)]
    names += [n[:-1] for n in names if n.endswith(_TAMIL_PULLI)]
    return names


def resolve(text: str | None, *, travel: bool = False) -> str | None:
    """Map free text (a query, or a city name in EN/TA, or an alias) to a canonical key.
    `travel=True` also knows the travel-only destinations."""
    if not text:
        return None
    pool = TRAVEL_CITIES if travel else CITIES
    s = text.strip().lower()
    if s in pool:
        return s
    for key, city in pool.items():
        if s in _names_for(city):
            return key
    for key, city in pool.items():  # within the text: "...weather in chennai" -> chennai
        if any(_spans(name, s) for name in _names_for(city)):
            return key
    return None


# An Indic name this short ("லே", Leh) would turn up inside ordinary words ("லேசான",
# light), so it has to stand alone like a Latin name; longer ones keep matching
# with a case suffix attached.
_SHORT_INDIC = 2


def _is_letter(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "LM"  # letters and combining vowel signs


def _spans(name: str, s: str) -> list[tuple[int, int]]:
    """Where `name` occurs in `s` (lowercased): Latin and very short Indic names only
    as whole words, other Indic names anywhere (they take case suffixes)."""
    if not name:
        return []
    if name.isascii():
        return [m.span() for m in re.finditer(rf"(?<![a-z]){re.escape(name)}(?![a-z])", s)]
    found = [m.span() for m in re.finditer(re.escape(name), s)]
    if len(name) > _SHORT_INDIC:
        return found
    return [(a, b) for a, b in found
            if not (a > 0 and _is_letter(s[a - 1])) and not (b < len(s) and _is_letter(s[b]))]


def mentions(text: str | None, *, travel: bool = False) -> list[tuple[str, int, int]]:
    """Every registry city named in `text`, as `(key, start, end)` in reading
    order. Unlike `resolve()`, which returns the first city it finds, this
    finds them all — a route names two. Where names overlap the longer wins
    ("new delhi" over "delhi"). Latin names, and Indic names of two characters or
    fewer, must stand alone as words; longer Indic names may carry case suffixes,
    so they match as substrings. `travel=True` also knows the travel-only
    destinations."""
    if not text:
        return []
    s = text.lower()
    spans: list[tuple[int, int, str]] = []
    for key, city in (TRAVEL_CITIES if travel else CITIES).items():
        for name in set(_names_for(city)):
            spans += [(a, b, key) for a, b in _spans(name, s)]
    spans.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    out: list[tuple[str, int, int]] = []
    last_end = -1
    for start, end, key in spans:
        if start >= last_end:  # not inside the previous (longer or earlier) match
            out.append((key, start, end))
            last_end = end
    return out


def display_name(key: str | None, lang: str) -> str:
    city = TRAVEL_CITIES.get(key or "")
    if not city:
        return key or ""
    return city.names.get(lang) or city.names["en"]


def as_public_list() -> list[dict]:
    return [
        {"key": c.key, "lat": c.lat, "lon": c.lon, "names": c.names,
         "region": c.region, "timezone": c.timezone}
        for c in CITIES.values()
    ]
