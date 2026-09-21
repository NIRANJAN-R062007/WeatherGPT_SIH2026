"""data/i18n/glossary.json, its loader (glossary.py) and GET /glossary — the
single source for warning colour words/meanings and category labels that
/warnings and the web app render from (plan.md §3.1). Fully offline.
"""

import json

import glossary
import main
import pytest
from config import DATA_DIR
from fastapi.testclient import TestClient
from i18n import SUPPORTED_LANGUAGES

client = TestClient(main.app)

GLOSSARY_PATH = DATA_DIR / "i18n" / "glossary.json"
LANGS = list(SUPPORTED_LANGUAGES)


def _entries():
    raw = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def test_every_entry_has_all_five_languages():
    # Mirrors the import-time check in glossary._load, straight off the file:
    # a 6th language (or a dropped one) must fail here, not fall back to
    # English in a demo.
    for entry_id, langs in _entries().items():
        for lang in LANGS:
            assert lang in langs, f"{entry_id} is missing '{lang}'"
            assert langs[lang]["text"].strip(), f"{entry_id}/{lang} has empty text"
            assert isinstance(langs[lang]["native_qa"], bool), f"{entry_id}/{lang} native_qa"


def test_english_is_the_authored_source():
    for entry_id, langs in _entries().items():
        assert langs["en"]["native_qa"] is True, entry_id


def test_required_ids_present():
    ids = set(_entries())
    for colour in glossary.COLOURS:
        assert f"colour_{colour}" in ids and f"colour_word_{colour}" in ids
    assert "category_no_warning" in ids


# --- loader fails loud -------------------------------------------------------


def test_load_fails_on_malformed_json(tmp_path):
    bad = tmp_path / "glossary.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):  # json.JSONDecodeError
        glossary._load(bad)


def test_load_fails_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        glossary._load(tmp_path / "glossary.json")


def test_load_fails_on_missing_language(tmp_path):
    entries = _entries()
    del entries["colour_word_red"]["mr"]
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    with pytest.raises(RuntimeError, match="colour_word_red.*mr"):
        glossary._load(path)


def test_load_fails_on_missing_required_id(tmp_path):
    entries = _entries()
    del entries["category_no_warning"]
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    with pytest.raises(RuntimeError, match="category_no_warning"):
        glossary._load(path)


def test_load_fails_on_bad_entry_shape(tmp_path):
    entries = _entries()
    entries["colour_green"]["hi"] = {"text": "", "native_qa": False}
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    with pytest.raises(RuntimeError, match="colour_green.*hi"):
        glossary._load(path)


def test_load_skips_meta_block(tmp_path):
    entries = _entries()
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"_meta": {"description": "x"}, **entries}), encoding="utf-8")
    assert set(glossary._load(path)) == set(entries)


# --- lookups -----------------------------------------------------------------


def test_text_falls_back_to_english_for_unknown_lang():
    assert glossary.text("colour_word_red", "fr") == "Red"


def test_text_unknown_id_is_loud():
    with pytest.raises(KeyError):
        glossary.text("colour_word_purple", "en")


def test_legend_is_four_rows_least_to_most_severe():
    rows = glossary.legend("ta")
    assert [r["colour"] for r in rows] == ["green", "yellow", "orange", "red"]
    assert [r["label"] for r in rows] == ["பச்சை", "மஞ்சள்", "ஆரஞ்சு", "சிவப்பு"]
    assert all(set(r) == {"colour", "label", "meaning"} and r["meaning"] for r in rows)


@pytest.mark.parametrize(
    "category,lang,expected",
    [
        (None, "en", "No warning in force"),
        (None, "hi", "कोई चेतावनी नहीं"),
        ("Heavy rainfall", "ta", "கனமழை"),
        ("heavy  rainfall!", "en", "Heavy rainfall"),  # slug is case/punctuation-insensitive
        ("Thunderstorm with lightning", "mr", "विजांच्या कडकडाटासह वादळ"),
        ("Dense fog", "te", "Dense fog"),  # unknown: the feed's own text, verbatim
    ],
)
def test_category_label(category, lang, expected):
    assert glossary.category_label(category, lang) == expected


# --- GET /glossary -----------------------------------------------------------


@pytest.mark.parametrize("lang", LANGS)
def test_glossary_route_serves_every_language(lang):
    body = client.get("/glossary", params={"lang": lang}).json()
    assert body["lang"] == lang
    assert set(body["entries"]) == set(_entries())
    entry = body["entries"]["colour_word_orange"]
    assert entry == {"text": glossary.text("colour_word_orange", lang),
                     "native_qa": _entries()["colour_word_orange"][lang]["native_qa"]}


def test_glossary_route_defaults_to_english():
    body = client.get("/glossary").json()
    assert body["lang"] == "en"
    assert body["entries"]["colour_green"]["text"].startswith("Green means no warning")


def test_glossary_route_rejects_unsupported_lang():
    assert client.get("/glossary", params={"lang": "fr"}).status_code == 422
