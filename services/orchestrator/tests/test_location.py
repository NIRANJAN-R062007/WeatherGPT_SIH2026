"""resolve_location(): the one place a place name, a tapped place_id or a GPS fix
becomes {lat, lon, label} (location.py).

Ambiguity and place_id tests run against a small synthetic gazetteer, so they
don't depend on GeoNames population figures. The rest use the committed
gazetteer file (data/gazetteer/in_places.json.gz) — never Postgres, which
tests/conftest.py keeps unreachable.

`location` is imported inside each test, not at the top: tests marked xfail
before the module existed have to fail in the test body, not at collection.
"""

import importlib

import config
import narrate
import nlu
import pytest

TRICHY = "gn:1254388"
MADURAI = "gn:1264521"
AURANGABAD_MH = "gn:1278149"
BILASPUR_CG = "gn:1275637"

# Tests land before the code they test (each commit stays green); each marker
# comes off in the commit that makes its tests pass.


def _location():
    return importlib.import_module("location")


def _place(pid, name, lat, lon, pop, district="Dist", state="State", **names):
    return {"id": pid, "lat": lat, "lon": lon, "pop": pop,
            "admin2": {"en": district}, "admin1": {"en": state},
            "names": {"en": [name], **names}}


def _synthetic():
    return [
        # Two Rampurs within 2x of each other: ambiguous.
        _place("gn:1", "Rampur", 20.0, 80.0, 40000, "North Dist", "State A"),
        _place("gn:2", "Rampur", 22.0, 82.0, 60000, "South Dist", "State B"),
        _place("gn:3", "Rampur", 24.0, 84.0, 30000, "East Dist", "State C"),
        _place("gn:4", "Rampur", 26.0, 86.0, 20000, "West Dist", "State D"),
        # A Sitapur 10x the other: not ambiguous, the big one wins.
        _place("gn:5", "Sitapur", 21.0, 81.0, 500000, "Big Dist", "State A"),
        _place("gn:6", "Sitapur", 23.0, 83.0, 50000, "Small Dist", "State B"),
        _place("gn:7", "Kumbakonam", 10.96, 79.38, 140000, "Thanjavur", "Tamil Nadu"),
    ]


@pytest.fixture
def synthetic(monkeypatch):
    def install():
        loc = _location()
        monkeypatch.setattr(loc, "_GAZETTEER", loc.Gazetteer.from_records(_synthetic()))
        return loc
    return install


# --- ambiguity rule, on synthetic data ---------------------------------------

def test_close_population_homonyms_are_ambiguous(synthetic):
    loc = synthetic()
    out = loc.resolve_location("Rampur", None, None, "en")
    assert out["source"] is None and out.get("lat") is None
    cands = out["ambiguous"]
    assert len(cands) == 3  # capped at 3, most populous first
    assert [c["place_id"] for c in cands] == ["gn:2", "gn:1", "gn:3"]
    for c in cands:
        assert set(c) >= {"place_id", "label", "district", "state"}
    assert cands[0]["district"] == "South Dist" and cands[0]["state"] == "State B"


def test_a_homonym_over_twice_the_others_population_wins_outright(synthetic):
    loc = synthetic()
    out = loc.resolve_location("Sitapur", None, None, "en")
    assert out["place_id"] == "gn:5" and out["source"] == "gazetteer"
    assert "ambiguous" not in out
    assert out["label"] == "Sitapur, State A"


def test_place_id_skips_matching(synthetic, monkeypatch):
    loc = synthetic()

    def _no_match(*a, **k):
        raise AssertionError("matching ran despite a place_id")

    monkeypatch.setattr(loc, "_match", _no_match)
    out = loc.resolve_location("Rampur", None, None, "en", place_id="gn:3")
    assert out["place_id"] == "gn:3"
    assert (out["lat"], out["lon"]) == (24.0, 84.0)
    assert out["source"] == "gazetteer"


def test_place_id_beats_the_named_place_and_gps(synthetic):
    loc = synthetic()
    out = loc.resolve_location("Sitapur", 10.96, 79.38, "en", place_id="gn:1")
    assert out["place_id"] == "gn:1"


def test_unknown_place_id_is_not_found_not_a_guess(synthetic):
    loc = synthetic()
    out = loc.resolve_location(None, None, None, "en", place_id="gn:999")
    assert out["not_found"] is True and out.get("lat") is None


# --- real gazetteer -----------------------------------------------------------

def test_trichy_and_tiruchirappalli_are_one_place():
    loc = _location()
    a = loc.resolve_location("Trichy", None, None, "en")
    b = loc.resolve_location("Tiruchirappalli", None, None, "en")
    assert a["place_id"] == b["place_id"] == TRICHY
    assert a["source"] == "gazetteer"


def test_query_text_weather_in_trichy_resolves_to_tiruchirappalli(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    pq = nlu.parse("weather in Trichy")
    out = _location().resolve_location(pq.place, None, None, "en")
    assert out["place_id"] == TRICHY


@pytest.mark.parametrize("text,lang", [("மதுரை", "ta"), ("मदुरै", "hi")])
def test_native_script_madurai_resolves_with_zero_llm_calls(monkeypatch, text, lang):
    calls = []
    monkeypatch.setattr(narrate, "is_configured", lambda: True)
    monkeypatch.setattr(narrate, "run_chain", lambda *a, **k: calls.append(a) or (None, None))
    pq = nlu.parse(text, lang_hint=lang)
    out = _location().resolve_location(pq.place, None, None, lang)
    assert calls == []
    assert pq.source == "rules"
    assert out["place_id"] == MADURAI and out["source"] == "demo_fixture"


@pytest.mark.parametrize("name,pid,state", [
    ("Aurangabad", AURANGABAD_MH, "Maharashtra"),
    ("Bilaspur", BILASPUR_CG, "Chhattisgarh"),
])
def test_big_homonym_wins_and_label_names_the_state(name, pid, state):
    out = _location().resolve_location(name, None, None, "en")
    assert out["place_id"] == pid
    assert "ambiguous" not in out
    assert state in out["label"]


def test_puttur_is_ambiguous_against_the_real_gazetteer():
    out = _location().resolve_location("Puttur", None, None, "en")
    assert "ambiguous" in out and len(out["ambiguous"]) >= 2
    states = {c["state"] for c in out["ambiguous"]}
    assert len(states) >= 2  # the Karnataka and Andhra Pradesh Putturs


def test_unknown_place_is_not_found_with_a_nearest_known_place():
    out = _location().resolve_location("Xyzabad", None, None, "en")
    assert out["not_found"] is True
    assert out.get("lat") is None and out.get("source") is None  # never a guess
    assert out["nearest"]["place_id"].startswith("gn:")
    assert out["nearest"]["label"]


def test_no_place_and_no_gps_asks_for_a_location():
    out = _location().resolve_location(None, None, None, "en")
    assert out.get("needs_location") is True
    assert out.get("lat") is None  # never Chennai or any other default


def test_no_place_with_gps_uses_gps():
    out = _location().resolve_location(None, 10.79, 78.70, "en")
    assert out["source"] == "gps"
    assert out["lat"] is not None and out["lon"] is not None


# --- Postgres path ---------------------------------------------------------------

class _PgEngine:
    """weather_store._engine stand-in: answers the match query with `rows`,
    or raises on begin() when `down`."""

    def __init__(self, rows=(), down=False):
        self.rows, self.down, self.begins = list(rows), down, 0

    def begin(self):
        self.begins += 1
        if self.down:
            raise RuntimeError("postgres down")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        rows = self.rows if "FROM cities" in str(stmt) else []

        class _R:
            def fetchall(self):
                return rows
        return _R()


def test_a_dead_postgres_costs_one_attempt_then_the_file_answers(synthetic, monkeypatch):
    import weather_store
    loc = synthetic()
    engine = _PgEngine(down=True)
    monkeypatch.setattr(weather_store, "_engine", engine)
    monkeypatch.setattr(loc, "_pg_down_until", 0.0)
    assert loc.resolve_location("Sitapur", None, None, "en")["place_id"] == "gn:5"
    assert loc.resolve_location("Sitapur", None, None, "en")["place_id"] == "gn:5"
    assert engine.begins == 1  # parked after the first failure


def test_postgres_candidates_are_ranked_like_the_file(synthetic, monkeypatch):
    import weather_store
    loc = synthetic()
    rows = [(r["id"], r["lat"], r["lon"], r["pop"], r["names"], r["admin1"], r["admin2"])
            for r in _synthetic() if r["names"]["en"] == ["Rampur"]]
    monkeypatch.setattr(weather_store, "_engine", _PgEngine(rows))
    monkeypatch.setattr(loc, "_pg_down_until", 0.0)
    from_pg = loc.resolve_location("Rampur", None, None, "en")
    monkeypatch.setattr(loc, "_pg_down_until", float("inf"))
    from_file = loc.resolve_location("Rampur", None, None, "en")
    assert from_pg == from_file
    assert [c["place_id"] for c in from_pg["ambiguous"]] == ["gn:2", "gn:1", "gn:3"]


# --- GPS label (step 4) ------------------------------------------------------------

_STEP4 = pytest.mark.xfail(strict=True, reason="step 4: GPS 'near X' label")


@_STEP4
def test_gps_label_names_the_nearest_town_in_english():
    out = _location().resolve_location(None, 10.79, 78.70, "en")
    assert out["label"] == "your location (near Tiruchirappalli)"
    assert out["nearest"]["place_id"] == TRICHY


@_STEP4
@pytest.mark.parametrize("lang,town", [("ta", "திருச்சிராப்பள்ளி"), ("hi", "तिरुचिरापल्ली"),
                                       ("mr", "तिरुचिरापल्ली")])
def test_gps_label_prefers_the_towns_name_in_the_users_language(lang, town):
    import i18n
    out = _location().resolve_location(None, 10.79, 78.70, lang)
    assert out["label"] == i18n.location_message("gps_label", lang, town=town)


@_STEP4
def test_gps_label_falls_back_to_the_english_name():
    # GeoNames has no Telugu name for Tiruchirappalli.
    import i18n
    out = _location().resolve_location(None, 10.79, 78.70, "te")
    assert out["label"] == i18n.location_message("gps_label", "te", town="Tiruchirappalli")


@_STEP4
def test_gps_label_without_any_known_town(monkeypatch):
    import i18n
    loc = _location()
    monkeypatch.setattr(loc, "nearest_place", lambda lat, lon: None)
    out = loc.resolve_location(None, 10.79, 78.70, "hi")
    assert out["label"] == i18n.location_message("gps_label_bare", "hi")
    assert out["source"] == "gps"
