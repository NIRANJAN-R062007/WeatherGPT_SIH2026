"""Build the India gazetteer from GeoNames (location.py, plan.md §8 Phase 1).

Inputs, downloaded by hand into data/geonames/ (gitignored):

    curl -LO https://download.geonames.org/export/dump/cities500.zip
    curl -L -o alternatenames_IN.zip \\
        https://download.geonames.org/export/dump/alternatenames/IN.zip
    curl -LO https://download.geonames.org/export/dump/admin1CodesASCII.txt
    curl -LO https://download.geonames.org/export/dump/admin2Codes.txt
    unzip cities500.zip && unzip alternatenames_IN.zip   # -> cities500.txt, IN.txt

IN.txt is alternateNamesV2 cut to India. Only its ta/hi/te/mr/en names are
used. Output:

    python scripts/import_geonames.py                # writes the gazetteer file
    python scripts/import_geonames.py --db           # ... and upserts into `cities`

--db goes through weather_store.sync_places() (idempotent upsert) against
DATABASE_URL, and refuses anything but a local database unless --allow-remote
is given. The file is what the request path loads when Postgres is down.

GeoNames data is CC-BY 4.0 (see NOTICE).
"""

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

import cities  # noqa: E402
import placenames  # noqa: E402

LANGS = ("en", "ta", "hi", "te", "mr")
MAX_NAME_LEN = 80
DEFAULT_SRC = REPO_ROOT / "data" / "geonames"
DEFAULT_OUT = REPO_ROOT / "data" / "gazetteer" / "in_places.json.gz"
ATTRIBUTION = ("Place names and coordinates from GeoNames (https://www.geonames.org/), "
               "licensed CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/).")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}


def script_ok(lang: str, name: str) -> bool:
    return placenames.script_ok(lang, name)


def clean_names(raw: list[tuple[str, str]]) -> tuple[dict[str, list[str]], Counter]:
    """Keep the usable names, in order; count what was dropped and why."""
    names: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    dropped: Counter = Counter()
    for lang, name in raw:
        name = (name or "").strip()
        if not name:
            dropped["empty"] += 1
        elif len(name) > MAX_NAME_LEN:
            dropped["too_long"] += 1
        elif not script_ok(lang, name):
            dropped["wrong_script"] += 1
        elif (lang, placenames.normalize(name)) in seen:
            dropped["duplicate"] += 1
        else:
            seen.add((lang, placenames.normalize(name)))
            names.setdefault(lang, []).append(name)
    return names, dropped


def _rows(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                yield line.rstrip("\n").split("\t")


def _alternate_names(path: Path, wanted: set[int]) -> dict[int, list[tuple[str, str]]]:
    """geonameid -> [(lang, name)] for our languages, preferred names first."""
    out: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for cols in _rows(path):
        gid, lang, name = int(cols[1]), cols[2], cols[3]
        if gid in wanted and lang in LANGS:
            preferred = len(cols) > 4 and cols[4] == "1"
            out[gid].append((0 if preferred else 1, lang, name))
    return {gid: [(lang, name) for _, lang, name in sorted(v, key=lambda t: t[0])]
            for gid, v in out.items()}


def _admin_names(alt: dict, gid: int, english: str) -> dict[str, str]:
    names, _ = clean_names([("en", english), *alt.get(gid, [])])
    return {lang: values[0] for lang, values in names.items()}


def _demo_ids() -> dict[int, str]:
    return {int(c.place_id.removeprefix("gn:")): c.key for c in cities.CITIES.values()}


def build(src: Path) -> tuple[list[dict], dict]:
    """Records for every Indian place in cities500, plus per-language stats."""
    places = [c for c in _rows(src / "cities500.txt") if c[8] == "IN"]
    admin1 = {c[0]: (c[1], int(c[3])) for c in _rows(src / "admin1CodesASCII.txt")
              if c[0].startswith("IN.")}
    admin2 = {c[0]: (c[1], int(c[3])) for c in _rows(src / "admin2Codes.txt")
              if c[0].startswith("IN.")}
    wanted = {int(c[0]) for c in places} | {g for _, g in admin1.values()} \
        | {g for _, g in admin2.values()}
    alt = _alternate_names(src / "IN.txt", wanted)
    demo = _demo_ids()

    kept: Counter = Counter()
    dropped: dict[str, Counter] = defaultdict(Counter)
    records = []
    for c in places:
        gid = int(c[0])
        raw = [("en", c[1]), ("en", c[2]), *alt.get(gid, [])]
        if gid in demo:  # the curated names and aliases match too
            city = cities.CITIES[demo[gid]]
            raw += [(lang, n) for lang, n in city.names.items()]
            raw += [("en" if placenames.is_latin(a) else "ta", a) for a in city.aliases]
        for lang, name in raw:  # per-language drop counts, for the report
            _, d = clean_names([(lang, name)])
            dropped[lang].update(d)
        names, d = clean_names(raw)
        dropped["_dup"].update(d)
        for lang, values in names.items():
            kept[lang] += len(values)

        record = {"id": f"gn:{gid}", "lat": round(float(c[4]), 5),
                  "lon": round(float(c[5]), 5), "pop": int(c[14] or 0), "names": names}
        a1 = admin1.get(f"IN.{c[10]}")
        a2 = admin2.get(f"IN.{c[10]}.{c[11]}")
        record["admin1"] = _admin_names(alt, a1[1], a1[0]) if a1 else {}
        record["admin2"] = _admin_names(alt, a2[1], a2[0]) if a2 else {}
        if gid in demo:
            record["demo"] = demo[gid]
        records.append(record)

    records.sort(key=lambda r: int(r["id"][3:]))
    stats = {"places": len(records), "kept": dict(kept),
             "dropped": {lang: dict(dropped[lang]) for lang in LANGS},
             "duplicates": dropped["_dup"].get("duplicate", 0)}
    return records, stats


def write_gazetteer(records: list[dict], out: Path) -> int:
    """Deterministic bytes (sorted records, mtime 0), so re-running the import
    on the same inputs changes nothing in git."""
    blob = json.dumps({"version": 1, "attribution": ATTRIBUTION, "places": records},
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0,
                                             filename="") as gz:
        gz.write(blob.encode("utf-8"))
    return out.stat().st_size


def _print_stats(stats: dict) -> None:
    print(f"places: {stats['places']}")
    print(f"{'lang':<6}{'kept':>8}{'empty':>8}{'long':>8}{'script':>8}")
    for lang in LANGS:
        d = stats["dropped"][lang]
        print(f"{lang:<6}{stats['kept'].get(lang, 0):>8}{d.get('empty', 0):>8}"
              f"{d.get('too_long', 0):>8}{d.get('wrong_script', 0):>8}")
    print(f"duplicates dropped (all languages): {stats['duplicates']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--db", action="store_true", help="also upsert into the cities table")
    ap.add_argument("--allow-remote", action="store_true",
                    help="allow --db against a non-local DATABASE_URL")
    args = ap.parse_args(argv)

    records, stats = build(args.src)
    _print_stats(stats)
    size = write_gazetteer(records, args.out)
    print(f"wrote {args.out.relative_to(REPO_ROOT)} ({size / 1024:.0f} KiB)")

    if args.db:
        import config
        import weather_store
        host = urlparse(config.DATABASE_URL).hostname or ""
        if host not in _LOCAL_HOSTS and not args.allow_remote:
            print(f"refusing --db against non-local host {host!r}", file=sys.stderr)
            return 1
        weather_store._ensure_schema()
        if not weather_store._SCHEMA_READY:
            print("migrations failed — see the log above", file=sys.stderr)
            return 1
        print(f"upserted {weather_store.sync_places(records)} places")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
