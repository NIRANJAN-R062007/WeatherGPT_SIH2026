"""resolve_location(): a place name, a tapped place_id or a GPS fix -> one
point to fetch weather for (plan.md §2 principle 3, §8 Phase 1/3).

    resolve_location(query_place, lat, lon, lang, place_id=None) ->
      {lat, lon, label, source: "gps" | "gazetteer" | "demo_fixture",
       place_id?, ambiguous?: [{place_id, label, district, state}],
       not_found?: True, nearest?: {...}, needs_location?: True,
       outside_india?: True}

Precedence: place_id, then the place named in the query, then GPS (the query
named no place, or said "here"), then nothing — a reply with no lat/lon and
`needs_location`, never a default city.

Matching, the same on both data paths: exact on any name in any language,
then pg_trgm-style fuzzy (Latin, Tamil, Devanagari; Telugu gets exact and
prefix only, see placenames.py), ranked by similarity then population, then
the ambiguity rule, then not_found with the nearest known place. No LLM
calls here.

Data: Postgres `cities` (sql/003 + 006) when it answers; otherwise the
gazetteer file, loaded once at import into the in-memory index below. A
Postgres failure parks that path for _PG_COOLDOWN_SECONDS, so a dead
database costs one connect timeout, not one per request. Demo cities
(data/cities.json) resolve to their own coordinates as source
"demo_fixture", so their snapshots keep working offline.
"""

import gzip
import json
import logging
import math
import time
from dataclasses import dataclass, field

import cities
import i18n
import placenames
from config import DATA_DIR
from sqlalchemy import text

GAZETTEER_PATH = DATA_DIR / "gazetteer" / "in_places.json.gz"

# Generous: mainland India plus Lakshadweep, the Andamans and the northern
# borders. A point outside it is answered "India only", never fetched.
INDIA_BBOX = {"lat": (6.0, 37.5), "lon": (68.0, 97.5)}

FUZZY_MIN = 0.5          # below this a fuzzy hit is a suggestion, not an answer
AMBIGUITY_SIMILARITY = 0.1
AMBIGUITY_POPULATION_RATIO = 2.0
MAX_CANDIDATES = 3
PREFIX_MIN_LEN = 3

_PG_COOLDOWN_SECONDS = 300.0
_LOG = logging.getLogger("weathergpt.location")
_monotonic = time.monotonic  # test seam


@dataclass(frozen=True)
class Place:
    id: str
    lat: float
    lon: float
    pop: int
    names: dict           # lang -> tuple of names, preferred first
    admin1: dict          # lang -> state name
    admin2: dict          # lang -> district name
    demo: str | None = None

    def name(self, lang: str) -> str:
        if self.demo:
            return cities.display_name(self.demo, lang)
        for code in (lang, "en"):
            if self.names.get(code):
                return self.names[code][0]
        return next(iter(n[0] for n in self.names.values() if n), self.id)

    def state(self, lang: str) -> str | None:
        return self.admin1.get(lang) or self.admin1.get("en")

    def district(self, lang: str) -> str | None:
        return self.admin2.get(lang) or self.admin2.get("en")

    def label(self, lang: str) -> str:
        if self.demo:
            return self.name(lang)
        state = self.state(lang)
        return f"{self.name(lang)}, {state}" if state else self.name(lang)

    def all_names(self) -> list[str]:
        return [n for values in self.names.values() for n in values]


def _place_from_record(rec: dict) -> Place:
    return Place(
        id=rec["id"], lat=float(rec["lat"]), lon=float(rec["lon"]),
        pop=int(rec.get("pop") or 0),
        names={lang: tuple(v if isinstance(v, list) else [v])
               for lang, v in rec.get("names", {}).items()},
        admin1=dict(rec.get("admin1") or {}), admin2=dict(rec.get("admin2") or {}),
        demo=rec.get("demo"),
    )


def _demo_place(city: cities.City) -> Place:
    names: dict[str, list[str]] = {lang: [n] for lang, n in city.names.items() if n}
    for alias in city.aliases:
        names.setdefault(placenames.text_script(alias) == "latin" and "en" or "ta",
                         []).append(alias)
    return Place(id=city.place_id, lat=city.lat, lon=city.lon, pop=0,
                 names={k: tuple(v) for k, v in names.items()},
                 admin1=dict(city.region), admin2={}, demo=city.key)


@dataclass
class Gazetteer:
    """The in-memory index: exact names, a trigram inverted index for the
    fuzzy scripts, and a plain list for Telugu prefix matching."""
    places: dict = field(default_factory=dict)
    _exact: dict = field(default_factory=dict)       # norm -> {place_id}
    _names: list = field(default_factory=list)       # [(norm, place_id, n_trigrams)]
    _by_trigram: dict = field(default_factory=dict)  # trigram -> [name index]
    _prefix: list = field(default_factory=list)      # [(norm, place_id)], Telugu

    @classmethod
    def from_records(cls, records: list[dict]) -> "Gazetteer":
        gaz = cls()
        for rec in records:
            gaz._add(_place_from_record(rec))
        for city in cities.CITIES.values():
            if city.place_id in gaz.places:
                # The file's GeoNames row for a demo city: keep its names,
                # population and district, answer with the curated city.
                p = gaz.places[city.place_id]
                gaz.places[city.place_id] = Place(
                    id=p.id, lat=city.lat, lon=city.lon, pop=p.pop, names=p.names,
                    admin1=p.admin1, admin2=p.admin2, demo=city.key)
            else:
                gaz._add(_demo_place(city))
        return gaz

    @classmethod
    def load(cls, path=GAZETTEER_PATH) -> "Gazetteer":
        try:
            blob = json.loads(gzip.decompress(path.read_bytes()))
            return cls.from_records(blob["places"])
        except (OSError, ValueError, KeyError) as exc:
            # Demo cities still resolve; everything else is not_found.
            _LOG.error("gazetteer file %s unusable (%s); demo cities only", path, exc)
            return cls.from_records([])

    def _add(self, place: Place) -> None:
        self.places[place.id] = place
        for name in place.all_names():
            norm = placenames.normalize(name)
            if not norm:
                continue
            self._exact.setdefault(norm, set()).add(place.id)
            script = placenames.text_script(norm)
            if script in placenames.FUZZY_SCRIPTS:
                grams = placenames.trigrams(norm)
                idx = len(self._names)
                self._names.append((norm, place.id, len(grams)))
                for g in grams:
                    self._by_trigram.setdefault(g, []).append(idx)
            elif script is not None:
                self._prefix.append((norm, place.id))

    def exact(self, norm: str) -> set:
        return self._exact.get(norm, set())

    def fuzzy(self, norm: str) -> dict:
        """place_id -> best pg_trgm similarity of any of its names (> 0)."""
        grams = placenames.trigrams(norm)
        shared: dict[int, int] = {}
        for g in grams:
            for idx in self._by_trigram.get(g, ()):
                shared[idx] = shared.get(idx, 0) + 1
        best: dict[str, float] = {}
        for idx, n in shared.items():
            _, pid, size = self._names[idx]
            sim = n / (len(grams) + size - n)
            if sim > best.get(pid, 0.0):
                best[pid] = sim
        return best

    def prefix(self, norm: str) -> dict:
        """Telugu: a name the query starts with (a case suffix: "చెన్నైలో"),
        or that starts with the query (typed short). Scored by length ratio."""
        out: dict[str, float] = {}
        for name, pid in self._prefix:
            short, long_ = sorted((name, norm), key=len)
            if len(short) >= PREFIX_MIN_LEN and long_.startswith(short):
                out[pid] = max(out.get(pid, 0.0), len(short) / len(long_))
        return out

    def nearest(self, lat: float, lon: float) -> Place | None:
        return min(self.places.values(), key=lambda p: _haversine_km(lat, lon, p.lat, p.lon),
                   default=None)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


_load_started = time.perf_counter()
_GAZETTEER: Gazetteer = Gazetteer.load()
LOAD_SECONDS = time.perf_counter() - _load_started


# --- Postgres path ---------------------------------------------------------------

_pg_down_until = 0.0

_PG_MATCH = """
    SELECT place_id, lat, lon, population, names, admin1, admin2
    FROM cities
    WHERE place_id IS NOT NULL AND (
        names_norm @> ARRAY[:q]
        OR (:fuzzy AND :q <% names_text)
        OR (:prefix AND EXISTS (
            SELECT 1 FROM unnest(names_norm) n
            WHERE (length(:q) >= :min_len AND n LIKE :q || '%')
               OR (length(n) >= :min_len AND :q LIKE n || '%')))
    )
    ORDER BY names_norm @> ARRAY[:q] DESC, word_similarity(:q, names_text) DESC,
             population DESC
    LIMIT 50
"""
_PG_NEAREST = """
    SELECT place_id, lat, lon, population, names, admin1, admin2
    FROM cities WHERE place_id IS NOT NULL
    ORDER BY geog <-> ST_MakePoint(:lon, :lat)::geography
    LIMIT 1
"""


def _pg(sql: str, params: dict, *, fuzzy_floor: float | None = None) -> list | None:
    """Rows from Postgres, or None when it is down or not migrated (the
    caller then uses the file). Never raises."""
    global _pg_down_until
    if _monotonic() < _pg_down_until:
        return None
    try:
        import weather_store  # its engine, and tests/conftest.py's kill switch
        with weather_store._engine.begin() as conn:
            if fuzzy_floor is not None:
                conn.execute(text("SELECT set_config('pg_trgm.word_similarity_threshold', "
                                  ":floor, true)"), {"floor": str(fuzzy_floor)})
            return conn.execute(text(sql), params).fetchall()
    except Exception as exc:
        _pg_down_until = _monotonic() + _PG_COOLDOWN_SECONDS
        _LOG.warning("location: postgres unavailable (%s); using the gazetteer file "
                     "for %.0f s", " ".join(str(exc).split())[:200], _PG_COOLDOWN_SECONDS)
        return None


def _row_place(row) -> Place:
    pid, lat, lon, pop, names, admin1, admin2 = row
    demo = next((c for c in cities.CITIES.values() if c.place_id == pid), None)
    if demo is not None:
        local = _GAZETTEER.places.get(pid)
        if local is not None:
            return local
        return _demo_place(demo)
    return _place_from_record({"id": pid, "lat": lat, "lon": lon, "pop": pop,
                               "names": names, "admin1": admin1, "admin2": admin2})


def _pg_candidates(norm: str) -> dict | None:
    """place_id -> similarity, from Postgres, scored with the same Python
    rules as the file path so both rank alike. None if Postgres is down."""
    script = placenames.text_script(norm)
    rows = _pg(_PG_MATCH, {"q": norm, "fuzzy": script in placenames.FUZZY_SCRIPTS,
                           "prefix": script not in placenames.FUZZY_SCRIPTS,
                           "min_len": PREFIX_MIN_LEN},
               fuzzy_floor=0.3)
    if rows is None:
        return None
    scored = {}
    for row in rows:
        place = _row_place(row)
        _PG_PLACES[place.id] = place
        scored[place.id] = _score(norm, place)
    return {pid: s for pid, s in scored.items() if s > 0}


_PG_PLACES: dict[str, Place] = {}


def _score(norm: str, place: Place) -> float:
    names = [placenames.normalize(n) for n in place.all_names()]
    if norm in names:
        return 1.0
    if placenames.text_script(norm) in placenames.FUZZY_SCRIPTS:
        return max((placenames.similarity(norm, n) for n in names), default=0.0)
    best = 0.0
    for n in names:
        short, long_ = sorted((n, norm), key=len)
        if len(short) >= PREFIX_MIN_LEN and long_.startswith(short):
            best = max(best, len(short) / len(long_))
    return best


# --- matching ----------------------------------------------------------------------

def _lookup(pid: str) -> Place | None:
    return _GAZETTEER.places.get(pid) or _PG_PLACES.get(pid)


def _match(query: str) -> list[tuple[float, Place]]:
    """Candidates for `query`, best first: (similarity, place), similarity 1.0
    for an exact name. Postgres first, the file when it is down."""
    norm = placenames.normalize(query)
    if not norm:
        return []
    scores = _pg_candidates(norm)
    if scores is None:
        exact = _GAZETTEER.exact(norm)
        if exact:
            scores = dict.fromkeys(exact, 1.0)
        elif placenames.text_script(norm) in placenames.FUZZY_SCRIPTS:
            scores = _GAZETTEER.fuzzy(norm)
        else:
            scores = _GAZETTEER.prefix(norm)
    elif any(s == 1.0 for s in scores.values()):
        scores = {pid: s for pid, s in scores.items() if s == 1.0}
    ranked = [(s, _lookup(pid)) for pid, s in scores.items() if _lookup(pid)]
    ranked.sort(key=lambda t: (-t[0], -t[1].pop, t[1].id))
    return ranked


def _too_close_to_call(a: tuple[float, Place], b: tuple[float, Place]) -> bool:
    (sa, pa), (sb, pb) = a, b
    if sa - sb > AMBIGUITY_SIMILARITY:
        return False
    big, small = max(pa.pop, pb.pop), min(pa.pop, pb.pop)
    return big <= AMBIGUITY_POPULATION_RATIO * small


def _candidate(place: Place, lang: str) -> dict:
    return {"place_id": place.id, "label": place.label(lang),
            "district": place.district(lang), "state": place.state(lang)}


def _nearest_info(place: Place, lang: str) -> dict:
    return {**_candidate(place, lang), "lat": place.lat, "lon": place.lon}


def _point(place: Place, lang: str) -> dict:
    return {"lat": place.lat, "lon": place.lon, "label": place.label(lang),
            "source": "demo_fixture" if place.demo else "gazetteer", "place_id": place.id}


def _unresolved(**flags) -> dict:
    return {"lat": None, "lon": None, "label": None, "source": None, **flags}


def in_india(lat: float, lon: float) -> bool:
    (la0, la1), (lo0, lo1) = INDIA_BBOX["lat"], INDIA_BBOX["lon"]
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


def nearest_place(lat: float, lon: float) -> Place | None:
    """The gazetteer place nearest a point: Postgres KNN on geog, else a
    brute-force haversine over the in-memory index."""
    rows = _pg(_PG_NEAREST, {"lat": lat, "lon": lon})
    if rows:
        return _row_place(rows[0])
    return _GAZETTEER.nearest(lat, lon)


def nearest_demo_city(lat: float, lon: float) -> cities.City:
    """The demo city (data/cities.json) nearest a point — the only places with
    saved snapshots, so what an offline GPS answer falls back to."""
    return min(cities.CITIES.values(), key=lambda c: _haversine_km(lat, lon, c.lat, c.lon))


def _gps(lat: float, lon: float, lang: str) -> dict:
    if not in_india(lat, lon):
        return _unresolved(outside_india=True)
    near = nearest_place(lat, lon)
    if near is None:
        return {"lat": lat, "lon": lon, "label": i18n.location_message("gps_label_bare", lang),
                "source": "gps"}
    # The town by its name in the user's language where GeoNames has one,
    # else English (Place.name's fallback).
    label = i18n.location_message("gps_label", lang, town=near.name(lang))
    return {"lat": lat, "lon": lon, "label": label, "source": "gps",
            "nearest": _nearest_info(near, lang)}


def _spelling_neighbour(query: str) -> Place | None:
    """The closest-spelled known place, offered (never used) when nothing
    matched and there is no GPS fix to measure distance from."""
    norm = placenames.normalize(query)
    scores = (_GAZETTEER.fuzzy(norm)
              if placenames.text_script(norm) in placenames.FUZZY_SCRIPTS
              else _GAZETTEER.prefix(norm))
    if not scores:
        return None
    pid = max(scores, key=lambda p: (scores[p], _GAZETTEER.places[p].pop))
    return _GAZETTEER.places[pid]


def resolve_location(query_place: str | None, lat: float | None, lon: float | None,
                     lang: str, place_id: str | None = None) -> dict:
    lang = lang if lang in placenames.LANG_SCRIPT else "en"
    if lat is not None and lon is not None:
        # ~1 km, before anything else sees it: the raw fix goes no further
        # than this line — not into Postgres, a log line or the reply.
        lat, lon = round(lat, 2), round(lon, 2)

    if place_id:
        place = _lookup(place_id)
        if place is None:
            rows = _pg("SELECT place_id, lat, lon, population, names, admin1, admin2 "
                       "FROM cities WHERE place_id = :pid", {"pid": place_id})
            place = _row_place(rows[0]) if rows else None
        return _point(place, lang) if place else _unresolved(not_found=True)

    if query_place and query_place.strip():
        ranked = _match(query_place)
        ranked = [(s, p) for s, p in ranked if s >= FUZZY_MIN]
        if ranked:
            if len(ranked) > 1 and _too_close_to_call(ranked[0], ranked[1]):
                top = ranked[0][0]
                close = [p for s, p in ranked if top - s <= AMBIGUITY_SIMILARITY]
                close.sort(key=lambda p: (-p.pop, p.id))
                return _unresolved(ambiguous=[_candidate(p, lang)
                                              for p in close[:MAX_CANDIDATES]])
            return _point(ranked[0][1], lang)
        out = _unresolved(not_found=True)
        near = (nearest_place(lat, lon) if lat is not None and lon is not None
                and in_india(lat, lon) else _spelling_neighbour(query_place))
        if near is not None:
            out["nearest"] = _nearest_info(near, lang)
        return out

    if lat is not None and lon is not None:
        return _gps(lat, lon, lang)

    return _unresolved(needs_location=True)
