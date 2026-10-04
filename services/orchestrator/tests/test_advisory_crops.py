"""advisory/crops.py: reading the sourced crop file (plan.md §11.7, TFA-9/TFA-11).

No real crop data: every file here is a test fixture written to tmp_path."""

import json

import pytest
from advisory import crops
from advisory import facts as facts_module


def _value(value, source="Fixture guide", quote="a verbatim fixture sentence"):
    return {"value": value, "source": source, "url": "https://example.invalid", "quote": quote}


def _entry(crop="groundnut", region="madurai", reviewed=False, **values):
    base = {"sowing_months": _value([6, 7]), "temp_range_c": _value({"min": 20, "max": 30}),
            "max_rain_probability_pct": _value(60)}
    return {"crop": crop, "region": region, "reviewed": reviewed, "values": {**base, **values}}


@pytest.fixture
def crop_file(tmp_path, monkeypatch):
    path = tmp_path / "crops.json"
    monkeypatch.setattr(crops, "PATH", path)
    monkeypatch.setattr(crops, "_cache", {"key": None, "entries": []})

    def write(*entries):
        path.write_text(json.dumps({"entries": list(entries)}), encoding="utf-8")
        return path

    return write


def test_no_file_covers_no_crop(crop_file):
    assert crops.lookup("groundnut", "madurai") is None
    section = facts_module.crop_entry("groundnut", "madurai")
    assert not section.available
    assert section.reason == "crop/region not in the sourced crop file"


def test_a_covered_crop_is_flattened_with_its_sources(crop_file):
    crop_file(_entry())
    got = crops.lookup("groundnut", "madurai")
    assert got["temp_range_c"] == {"min": 20, "max": 30}
    assert got["max_rain_probability_pct"] == 60
    assert got["sowing_months"] == ["June", "July"]  # names: never read as a figure
    assert {s["field"] for s in got["sources"]} == set(crops.FIELDS)
    assert got["reviewed"] is False and "not yet reviewed" in got["source"]
    section = facts_module.crop_entry("groundnut", "madurai")
    assert section.available and section.source == got["source"]


def test_a_reviewed_entry_says_so(crop_file):
    crop_file(_entry(reviewed=True))
    got = crops.lookup("groundnut", "madurai")
    assert got["reviewed"] is True and got["source"] == crops.SOURCE


def test_the_states_entry_covers_its_districts_and_a_district_entry_wins(crop_file):
    crop_file(_entry(region="tamil_nadu"),
              _entry(region="coimbatore", temp_range_c=_value({"min": 18, "max": 28})))
    assert crops.state_slug("madurai") == "tamil_nadu"
    assert crops.lookup("groundnut", "madurai")["region"] == "tamil_nadu"
    assert crops.lookup("groundnut", "coimbatore")["temp_range_c"] == {"min": 18, "max": 28}
    assert crops.lookup("groundnut", "mumbai") is None  # Maharashtra: not covered
    assert crops.lookup("rice", "madurai") is None


@pytest.mark.parametrize("bad", [
    _value(55, source=""), _value(55, quote="  "), {"value": 55},
])
def test_an_unsourced_value_is_ignored_not_used(crop_file, bad):
    crop_file(_entry(max_rain_probability_pct=bad))
    got = crops.lookup("groundnut", "madurai")
    assert got["max_rain_probability_pct"] is None
    assert "max_rain_probability_pct" not in {s["field"] for s in got["sources"]}


@pytest.mark.parametrize("field, bad", [
    ("sowing_months", [0, 13]), ("temp_range_c", {"min": 30, "max": 20}),
    ("max_rain_probability_pct", 140),
])
def test_a_malformed_value_is_ignored(crop_file, field, bad):
    crop_file(_entry(**{field: _value(bad)}))
    assert crops.lookup("groundnut", "madurai")[field] is None


def test_a_null_value_stays_null(crop_file):
    crop_file(_entry(sowing_months=_value(None)))
    assert crops.lookup("groundnut", "madurai")["sowing_months"] is None


def test_an_unknown_crop_or_a_broken_file_covers_nothing(crop_file):
    crop_file(_entry(crop="dragonfruit"))
    assert crops.entries() == []
    crops.PATH.write_text("{not json", encoding="utf-8")
    assert crops.lookup("groundnut", "madurai") is None


def test_the_file_is_reread_when_it_changes(crop_file):
    import os

    path = crop_file(_entry())
    assert crops.lookup("groundnut", "madurai") is not None
    crop_file(_entry(region="delhi"))
    os.utime(path, ns=(1, 1))  # a different mtime even within one clock tick
    assert crops.lookup("groundnut", "madurai") is None
