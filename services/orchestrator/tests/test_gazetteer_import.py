"""The GeoNames gazetteer pipeline: scripts/import_geonames.py, the migration
that gives `cities` its trigram index, and the committed gazetteer file.

No GeoNames download and no Postgres here: the import is exercised on a few
synthetic rows in GeoNames' own column layout, and the database side through
the fake engine pattern test_weather_store.py uses.
"""

import gzip
import importlib.util
import json

import cities
import config
import pytest
import weather_store

_SCRIPT = config.REPO_ROOT / "scripts" / "import_geonames.py"
_GAZETTEER = config.DATA_DIR / "gazetteer" / "in_places.json.gz"
_MIGRATION = weather_store._MIGRATIONS_DIR / "006_cities_gazetteer.sql"

_SCRIPT_STEP = pytest.mark.xfail(strict=True, reason="step 1: import script")
_FILE_STEP = pytest.mark.xfail(strict=True, reason="step 1: generated gazetteer file")

DEMO_PLACE_IDS = {
    "chennai": "gn:1264527", "madurai": "gn:1264521", "coimbatore": "gn:1273865",
    "bengaluru": "gn:1277333", "hyderabad": "gn:1269843", "mumbai": "gn:1275339",
    "delhi": "gn:1273294", "thiruvananthapuram": "gn:1254163",
}


def _script():
    spec = importlib.util.spec_from_file_location("import_geonames", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- migration ----------------------------------------------------------------

def test_gazetteer_migration_is_additive_and_indexed():
    sql = _MIGRATION.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql
    for column in ("place_id", "population", "admin1", "admin2", "names_text", "names_norm"):
        assert f"ADD COLUMN IF NOT EXISTS {column} " in sql, column
    assert "gin_trgm_ops" in sql
    # Never a generated column over JSONB: names_text is written at upsert time.
    assert "GENERATED" not in sql
    for destructive in ("DROP ", "DELETE ", "TRUNCATE", "ALTER COLUMN"):
        assert destructive not in sql.upper(), destructive


# --- demo cities ----------------------------------------------------------------

def test_every_demo_city_carries_its_geonames_place_id():
    assert {k: c.place_id for k, c in cities.CITIES.items()} == DEMO_PLACE_IDS


# --- import script ----------------------------------------------------------------

@_SCRIPT_STEP
@pytest.mark.parametrize("lang,name,ok", [
    ("en", "Tiruchirappalli", True),
    ("en", "Bilāspur", True),          # Latin with diacritics is still Latin
    ("en", "திருச்சி", False),          # Tamil script under "en"
    ("ta", "திருச்சிராப்பள்ளி", True),
    ("ta", "Trichy", False),
    ("hi", "तिरुचिरापल्ली", True),
    ("mr", "तिरुचिरापल्ली", True),
    ("hi", "திருச்சி", False),
    ("te", "హైదరాబాద్", True),
    ("te", "हैदराबाद", False),
])
def test_script_check_per_language(lang, name, ok):
    assert _script().script_ok(lang, name) is ok


@_SCRIPT_STEP
def test_clean_names_drops_junk_and_counts_it():
    raw = [
        ("en", "Trichy"), ("en", "trichy"),          # duplicate, case-insensitive
        ("en", ""), ("en", "   "),                   # empty
        ("en", "x" * 81),                            # over 80 chars
        ("ta", "Trichy"),                            # wrong script
        ("ta", "திருச்சி"), ("hi", "तिरुचिरापल्ली"),
    ]
    names, dropped = _script().clean_names(raw)
    assert names == {"en": ["Trichy"], "ta": ["திருச்சி"], "hi": ["तिरुचिरापल्ली"]}
    assert dropped == {"duplicate": 1, "empty": 2, "too_long": 1, "wrong_script": 1}


def _write_geonames(tmp_path):
    def row(*cols):
        return "\t".join(str(c) for c in cols) + "\n"

    # cities500 layout: id, name, asciiname, alternatenames, lat, lon, fclass,
    # fcode, cc, cc2, admin1, admin2, admin3, admin4, population, ...
    (tmp_path / "cities500.txt").write_text(
        row(1254388, "Tiruchirappalli", "Tiruchirappalli", "", 10.8155, 78.69651, "P", "PPL",
            "IN", "", "25", "614", "", "", 1022518, "", 88, "Asia/Kolkata", "2024-01-01")
        + row(1264527, "Chennai", "Chennai", "", 13.08784, 80.27847, "P", "PPLA",
              "IN", "", "25", "603", "", "", 4681087, "", 6, "Asia/Kolkata", "2024-01-01")
        + row(2643743, "London", "London", "", 51.5, -0.12, "P", "PPLC",
              "GB", "", "ENG", "", "", "", 8961989, "", 25, "Europe/London", "2024-01-01"),
        encoding="utf-8")
    # alternateNamesV2: altid, geonameid, lang, name, preferred, short, colloquial, historic
    (tmp_path / "IN.txt").write_text(
        row(1, 1254388, "en", "Trichy", "", "", "", "")
        + row(2, 1254388, "ta", "திருச்சிராப்பள்ளி", "1", "", "", "")
        + row(3, 1254388, "ml", "തിരുച്ചിറപ്പള്ളി", "", "", "", "")
        + row(4, 1254388, "link", "https://en.wikipedia.org/wiki/Tiruchirappalli", "", "", "", "")
        + row(5, 1255053, "ta", "தமிழ்நாடு", "1", "", "", "")
        + row(6, 1264527, "en", "Madras", "", "", "", "1"),
        encoding="utf-8")
    (tmp_path / "admin1CodesASCII.txt").write_text(
        row("IN.25", "Tamil Nadu", "Tamil Nadu", 1255053), encoding="utf-8")
    (tmp_path / "admin2Codes.txt").write_text(
        row("IN.25.614", "Tiruchirappalli", "Tiruchirappalli", 1254387)
        + row("IN.25.603", "Chennai", "Chennai", 1264526), encoding="utf-8")


@_SCRIPT_STEP
def test_build_keeps_india_only_and_maps_demo_cities(tmp_path):
    _write_geonames(tmp_path)
    records, _ = _script().build(tmp_path)
    by_id = {r["id"]: r for r in records}
    assert set(by_id) == {"gn:1254388", "gn:1264527"}  # London dropped: not IN
    trichy = by_id["gn:1254388"]
    assert trichy["names"]["en"] == ["Tiruchirappalli", "Trichy"]
    assert trichy["names"]["ta"] == ["திருச்சிராப்பள்ளி"]
    assert "ml" not in trichy["names"] and "link" not in trichy["names"]
    assert trichy["admin1"] == {"en": "Tamil Nadu", "ta": "தமிழ்நாடு"}
    assert trichy["admin2"] == {"en": "Tiruchirappalli"}
    assert trichy["pop"] == 1022518 and "demo" not in trichy
    assert by_id["gn:1264527"]["demo"] == "chennai"
    assert "Madras" in by_id["gn:1264527"]["names"]["en"]


@_SCRIPT_STEP
def test_written_file_round_trips(tmp_path):
    _write_geonames(tmp_path)
    mod = _script()
    records, _ = mod.build(tmp_path)
    out = tmp_path / "in_places.json.gz"
    mod.write_gazetteer(records, out)
    blob = json.loads(gzip.decompress(out.read_bytes()))
    assert "CC-BY 4.0" in blob["attribution"]
    assert {p["id"] for p in blob["places"]} == {"gn:1254388", "gn:1264527"}


class _Engine:
    def __init__(self):
        self.rows = []

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        if params is not None:
            self.rows.append(params)


@_SCRIPT_STEP
def test_sync_places_upserts_names_text_and_keys_demo_rows_by_city(monkeypatch, tmp_path):
    _write_geonames(tmp_path)
    records, _ = _script().build(tmp_path)
    engine = _Engine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    monkeypatch.setattr(weather_store, "_SCHEMA_READY", True)
    assert weather_store.sync_places(records) == 2
    by_key = {r["key"]: r for r in engine.rows}
    assert set(by_key) == {"gn:1254388", "chennai"}  # a demo city keeps its key
    assert by_key["chennai"]["place_id"] == "gn:1264527"
    assert "trichy" in by_key["gn:1254388"]["names_text"]
    assert "திருச்சிராப்பள்ளி" in by_key["gn:1254388"]["names_norm"]


# --- the committed file --------------------------------------------------------------

@_FILE_STEP
def test_committed_gazetteer_is_small_and_agrees_with_the_demo_list():
    assert _GAZETTEER.stat().st_size < 5 * 1024 * 1024
    blob = json.loads(gzip.decompress(_GAZETTEER.read_bytes()))
    demo = {p["demo"]: p["id"] for p in blob["places"] if "demo" in p}
    assert demo == DEMO_PLACE_IDS
    assert len(blob["places"]) > 5000
    assert len({p["id"] for p in blob["places"]}) == len(blob["places"])
