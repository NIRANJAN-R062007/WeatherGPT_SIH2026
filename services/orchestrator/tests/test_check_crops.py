"""scripts/check_crops.py: the crop file checked against its own quotes (TFA-10).

Done-when: a tampered or sourceless entry fails the check. The real file is checked
offline here too, so CI goes red if an edit leaves a number its quote doesn't give."""

import copy
import importlib.util
import json

import config
import pytest

_SCRIPT = config.REPO_ROOT / "scripts" / "check_crops.py"
_spec = importlib.util.spec_from_file_location("check_crops", _SCRIPT)
check_crops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_crops)

URL = "https://example.invalid/groundnut"
QUOTE_MONTHS = "June-July | Anipattam | Madurai ... Dec- Jan | Margazhipattam | Madurai"
QUOTE_TEMP = "T. Max | T. Min | 40 o C | 15 o C"


def _value(value, quote="", source="Fixture guide", url=URL):
    return {"value": value, "source": source, "url": url, "quote": quote}


def _doc(**values) -> dict:
    base = {"sowing_months": _value([6, 7, 12, 1], QUOTE_MONTHS),
            "temp_range_c": _value({"min": 15, "max": 40}, QUOTE_TEMP),
            "max_rain_probability_pct": _value(None)}
    return {"entries": [{"crop": "groundnut", "region": "madurai", "reviewed": False,
                         "values": {**base, **values}}]}


def test_the_real_crop_file_is_clean():
    doc = json.loads(check_crops.DEFAULT_PATH.read_text(encoding="utf-8"))
    assert check_crops.check(doc) == []


def test_a_clean_entry_passes_and_a_null_value_needs_no_quote():
    assert check_crops.check(_doc()) == []


# --- tampered: a number its quote doesn't give ----------------------------------------


@pytest.mark.parametrize("field, value, problem", [
    ("temp_range_c", {"min": 15, "max": 45}, "not in the quote: 45"),
    ("temp_range_c", {"min": 18, "max": 40}, "not in the quote: 18"),
    ("sowing_months", [6, 7, 8, 12, 1], "not in the quote: August"),
    ("max_rain_probability_pct", 30, "not in the quote: 30"),
])
def test_a_tampered_value_fails(field, value, problem):
    given = copy.deepcopy(_doc()["entries"][0]["values"][field])
    given["value"] = value
    if field == "max_rain_probability_pct":
        given["quote"] = "Rainfall 500 - 700 mm"
    assert check_crops.check(_doc(**{field: given})) == [f"groundnut/madurai {field}: {problem}"]


def test_a_tampered_quote_fails_too():
    tampered = _value({"min": 15, "max": 40}, "T. Optimum | 25 - 35 o C")
    assert check_crops.check(_doc(temp_range_c=tampered)) == [
        "groundnut/madurai temp_range_c: not in the quote: 15, 40"]


def test_months_match_by_name_or_abbreviation_never_by_number():
    assert check_crops.check(_doc(sowing_months=_value([9], "September - October"))) == []
    assert check_crops.check(_doc(sowing_months=_value([9], "Sept to Oct"))) == []
    assert check_crops.check(_doc(sowing_months=_value([9], "month 9"))) != []


# --- sourceless -----------------------------------------------------------------------


@pytest.mark.parametrize("given, problem", [
    (_value({"min": 15, "max": 40}, QUOTE_TEMP, source=""), "no source"),
    (_value({"min": 15, "max": 40}, QUOTE_TEMP, url=""), "no https url"),
    (_value({"min": 15, "max": 40}, QUOTE_TEMP, url="http://example.invalid"), "no https url"),
    (_value({"min": 15, "max": 40}, ""), "no quote for a value"),
    (_value(None, source=""), "no source"),
    (None, "missing: give the field, with value null when the source has none"),
])
def test_a_sourceless_value_fails(given, problem):
    doc = _doc(temp_range_c=given)
    if given is None:
        del doc["entries"][0]["values"]["temp_range_c"]
    assert check_crops.check(doc) == [f"groundnut/madurai temp_range_c: {problem}"]


# --- the entry itself -----------------------------------------------------------------


def test_unknown_crop_and_region_a_repeat_and_a_bad_reviewed_flag_fail():
    doc = _doc()
    entry = doc["entries"][0]
    doc["entries"] += [{**entry, "crop": "coffee"}, {**entry, "region": "atlantis"},
                       copy.deepcopy(entry), {**entry, "region": "coimbatore", "reviewed": "no"}]
    assert check_crops.check(doc) == [
        "coffee/madurai: unknown crop (not in advisory/slots.py CROPS)",
        "groundnut/atlantis: unknown region (not a district key or state slug)",
        "groundnut/madurai: given twice",
        "groundnut/coimbatore: `reviewed` must be true or false",
    ]


def test_a_state_slug_is_a_region():
    doc = _doc()
    doc["entries"][0]["region"] = "tamil_nadu"
    assert check_crops.check(doc) == []


def test_a_malformed_value_fails():
    bad = _value({"min": 40, "max": 15}, QUOTE_TEMP)
    assert check_crops.check(_doc(temp_range_c=bad)) == [
        "groundnut/madurai temp_range_c: malformed value {'min': 40, 'max': 15}"]


def test_a_file_without_entries_fails():
    assert check_crops.check({"crops": []}) == ["file: no `entries` list"]


# --- --fetch: each quote passage on its page ------------------------------------------


PAGE = """<html><head><style>td {}</style></head><body><table>
<tr><td>June-July</td><td>Anipattam</td><td>Madurai</td></tr>
<tr><td>Dec- Jan</td><td>Margazhipattam</td><td>Madurai</td></tr></table>
<table><tr><td>T. Max</td><td>T. Min</td></tr><tr><td>40 o C</td><td>15 o C</td></tr></table>
</body></html>"""


def test_every_quote_passage_found_on_its_page_passes():
    fetched = []
    assert check_crops.check_pages(_doc(), get=lambda url: fetched.append(url) or PAGE) == []
    assert fetched == [URL]  # one fetch per page


def test_a_quote_the_page_does_not_have_fails():
    doc = _doc(temp_range_c=_value({"min": 15, "max": 45}, "T. Max | T. Min | 45 o C | 15 o C"))
    problems = check_crops.check_pages(doc, get=lambda url: PAGE)
    assert problems == ["groundnut/madurai temp_range_c: quote not on the page: "
                        "'T. Max | T. Min | 45 o C | 15 o C'"]


def test_a_page_that_cannot_be_fetched_is_reported_once():
    def down(url):
        raise OSError("timed out")

    assert check_crops.check_pages(_doc(), get=down) == [f"{URL}: could not fetch (timed out)"]


# --- the command ----------------------------------------------------------------------


def test_main_exits_nonzero_on_a_tampered_file_and_zero_on_a_clean_one(tmp_path, capsys):
    clean, tampered = tmp_path / "clean.json", tmp_path / "tampered.json"
    clean.write_text(json.dumps(_doc()), encoding="utf-8")
    doc = _doc()
    doc["entries"][0]["values"]["temp_range_c"]["value"]["max"] = 45
    tampered.write_text(json.dumps(doc), encoding="utf-8")
    assert check_crops.main([str(clean)]) == 0
    assert check_crops.main([str(tampered)]) == 1
    out = capsys.readouterr().out
    assert "groundnut/madurai temp_range_c: not in the quote: 45" in out
    assert "1 entries, 1 problems" in out


def test_main_rejects_an_unreadable_file(tmp_path):
    bad = tmp_path / "crops.json"
    bad.write_text("{not json", encoding="utf-8")
    assert check_crops.main([str(bad)]) == 1
