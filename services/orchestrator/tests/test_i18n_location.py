"""The location replies /ask gives instead of an answer — which place?, place
not found, a location is needed, India only — in all five languages
(i18n.LOCATION_MESSAGES)."""

import inspect

import i18n
import pytest

_KEYS = ("need_location", "which_place", "place_not_found", "place_not_found_bare",
         "india_only")
_GPS_KEYS = ("gps_label", "gps_label_bare")


@pytest.mark.parametrize("key", _KEYS)
@pytest.mark.parametrize("lang", i18n.SUPPORTED_LANGUAGES)
def test_every_location_message_exists_in_every_language(key, lang):
    text = i18n.location_message(key, lang, place="Xyzabad", nearest="Fyzābād")
    assert text and "{" not in text
    assert not any(ch.isdigit() for ch in text)  # never a figure the guardrail must ground


def test_not_found_names_the_place_and_the_nearest_one():
    text = i18n.location_message("place_not_found", "en", place="Xyzabad",
                                 nearest="Fyzābād, Uttar Pradesh")
    assert "Xyzabad" in text and "Fyzābād, Uttar Pradesh" in text


def test_unknown_language_falls_back_to_english():
    assert i18n.location_message("need_location", "fr") == \
        i18n.location_message("need_location", "en")


def test_new_indic_strings_carry_the_native_qa_marker():
    """audit-4.2: unreviewed ta/hi/te/mr text is marked at its source."""
    source = inspect.getsource(i18n).splitlines()
    for key in _KEYS:
        for lang in ("ta", "hi", "te", "mr"):
            first_line = i18n.LOCATION_MESSAGES[key][lang].splitlines()[0][:20]
            lines = [ln for ln in source if first_line in ln]
            assert lines and all("TODO: native_qa" in ln for ln in lines), (key, lang)


@pytest.mark.parametrize("key", _GPS_KEYS)
@pytest.mark.parametrize("lang", i18n.SUPPORTED_LANGUAGES)
def test_gps_labels_exist_in_every_language(key, lang):
    text = i18n.location_message(key, lang, town="Tiruchirappalli")
    assert text and "{" not in text and not any(ch.isdigit() for ch in text)
    if key == "gps_label":
        assert "Tiruchirappalli" in text


def test_gps_labels_carry_the_native_qa_marker():
    source = inspect.getsource(i18n).splitlines()
    for key in _GPS_KEYS:
        for lang in ("ta", "hi", "te", "mr"):
            first = i18n.LOCATION_MESSAGES[key][lang][:12]
            lines = [ln for ln in source if first in ln]
            assert lines and all("TODO: native_qa" in ln for ln in lines), (key, lang)
