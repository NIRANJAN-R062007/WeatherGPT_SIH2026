"""The decoder tables are well-formed and stay in sync with i18n's condition keys
and with the enum values that actually appear in the committed fixtures.
"""

import json

import i18n
import pytest
from config import DATA_DIR, FIXTURES_DIR

DECODERS = DATA_DIR / "decoders"


def _load(name):
    return json.loads((DECODERS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["weather_conditions.json", "wind_cardinals.json"])
def test_decoder_well_formed(name):
    doc = _load(name)
    assert doc["_meta"]["purpose"]
    assert isinstance(doc["map"], dict) and doc["map"]
    assert all(isinstance(k, str) and k for k in doc["map"])
    # wind_cardinals has one intentionally-empty value (DIRECTION_UNSPECIFIED)
    empties = [k for k, v in doc["map"].items() if v == ""]
    assert empties in ([], ["DIRECTION_UNSPECIFIED"])


def test_condition_values_exist_in_i18n():
    values = set(_load("weather_conditions.json")["map"].values())
    assert values <= set(i18n.CONDITION_EN), values - set(i18n.CONDITION_EN)
    assert values <= set(i18n.CONDITION_TA), values - set(i18n.CONDITION_TA)


def test_wind_cardinal_labels_are_short():
    for label in _load("wind_cardinals.json")["map"].values():
        assert label == label.upper() and len(label) <= 3


def test_every_fixture_condition_type_is_mapped():
    mapping = _load("weather_conditions.json")["map"]
    seen = set()
    for path in (FIXTURES_DIR / "google_weather").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))["response"]
        _collect_condition_types(payload, seen)
    assert seen, "no weatherCondition.type found in fixtures"
    unmapped = seen - set(mapping)
    assert not unmapped, f"fixture condition types missing from decoder: {unmapped}"


def _collect_condition_types(node, seen):
    if isinstance(node, dict):
        wc = node.get("weatherCondition")
        if isinstance(wc, dict) and isinstance(wc.get("type"), str):
            seen.add(wc["type"])
        for v in node.values():
            _collect_condition_types(v, seen)
    elif isinstance(node, list):
        for v in node:
            _collect_condition_types(v, seen)
