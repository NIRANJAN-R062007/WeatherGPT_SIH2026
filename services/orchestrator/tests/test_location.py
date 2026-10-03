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
_STEP2 = pytest.mark.xfail(strict=True, reason="step 2: location.py resolver")
_STEP3 = pytest.mark.xfail(strict=True, reason="step 3: NLU place extraction")


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

@_STEP2
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


@_STEP2
def test_a_homonym_over_twice_the_others_population_wins_outright(synthetic):
    loc = synthetic()
    out = loc.resolve_location("Sitapur", None, None, "en")
    assert out["place_id"] == "gn:5" and out["source"] == "gazetteer"
    assert "ambiguous" not in out
    assert out["label"] == "Sitapur, State A"


@_STEP2
def test_place_id_skips_matching(synthetic, monkeypatch):
    loc = synthetic()

    def _no_match(*a, **k):
        raise AssertionError("matching ran despite a place_id")

    monkeypatch.setattr(loc, "_match", _no_match)
    out = loc.resolve_location("Rampur", None, None, "en", place_id="gn:3")
    assert out["place_id"] == "gn:3"
    assert (out["lat"], out["lon"]) == (24.0, 84.0)
    assert out["source"] == "gazetteer"


@_STEP2
def test_place_id_beats_the_named_place_and_gps(synthetic):
    loc = synthetic()
    out = loc.resolve_location("Sitapur", 10.96, 79.38, "en", place_id="gn:1")
    assert out["place_id"] == "gn:1"


@_STEP2
def test_unknown_place_id_is_not_found_not_a_guess(synthetic):
    loc = synthetic()
    out = loc.resolve_location(None, None, None, "en", place_id="gn:999")
    assert out["not_found"] is True and out.get("lat") is None


# --- real gazetteer -----------------------------------------------------------

@_STEP2
def test_trichy_and_tiruchirappalli_are_one_place():
    loc = _location()
    a = loc.resolve_location("Trichy", None, None, "en")
    b = loc.resolve_location("Tiruchirappalli", None, None, "en")
    assert a["place_id"] == b["place_id"] == TRICHY
    assert a["source"] == "gazetteer"


@_STEP3
def test_query_text_weather_in_trichy_resolves_to_tiruchirappalli(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    pq = nlu.parse("weather in Trichy")
    out = _location().resolve_location(pq.place, None, None, "en")
    assert out["place_id"] == TRICHY


@_STEP3
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


@_STEP2
@pytest.mark.parametrize("name,pid,state", [
    ("Aurangabad", AURANGABAD_MH, "Maharashtra"),
    ("Bilaspur", BILASPUR_CG, "Chhattisgarh"),
])
def test_big_homonym_wins_and_label_names_the_state(name, pid, state):
    out = _location().resolve_location(name, None, None, "en")
    assert out["place_id"] == pid
    assert "ambiguous" not in out
    assert state in out["label"]


@_STEP2
def test_puttur_is_ambiguous_against_the_real_gazetteer():
    out = _location().resolve_location("Puttur", None, None, "en")
    assert "ambiguous" in out and len(out["ambiguous"]) >= 2
    states = {c["state"] for c in out["ambiguous"]}
    assert len(states) >= 2  # the Karnataka and Andhra Pradesh Putturs


@_STEP2
def test_unknown_place_is_not_found_with_a_nearest_known_place():
    out = _location().resolve_location("Xyzabad", None, None, "en")
    assert out["not_found"] is True
    assert out.get("lat") is None and out.get("source") is None  # never a guess
    assert out["nearest"]["place_id"].startswith("gn:")
    assert out["nearest"]["label"]


@_STEP2
def test_no_place_and_no_gps_asks_for_a_location():
    out = _location().resolve_location(None, None, None, "en")
    assert out.get("needs_location") is True
    assert out.get("lat") is None  # never Chennai or any other default


@_STEP2
def test_no_place_with_gps_uses_gps():
    out = _location().resolve_location(None, 10.79, 78.70, "en")
    assert out["source"] == "gps"
    assert out["lat"] is not None and out["lon"] is not None
