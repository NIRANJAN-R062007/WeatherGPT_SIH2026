"""nlu.py's location signals: the place a query names (`pq.place`, handed to
location.resolve_location()) and whether it asks about the user's own
location (`pq.here`, which lets /ask use GPS). Rules first, LLM schema second.
"""

import config
import narrate
import nlu
import pytest

_STEP3 = pytest.mark.xfail(strict=True, reason="step 3: NLU place/here extraction")


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)


def _llm_says(monkeypatch, payload: str):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: payload)


# TODO: native_qa — the ta/hi/te/mr phrasings below are first drafts.
@_STEP3
@pytest.mark.parametrize("text,lang", [
    ("will it rain here", "en"),
    ("weather at my location", "en"),
    ("what's the weather in my location", "en"),
    ("இங்கே மழை பெய்யுமா?", "ta"),
    ("यहाँ बारिश होगी क्या?", "hi"),
    ("ఇక్కడ వర్షం పడుతుందా?", "te"),
    ("इथे पाऊस पडेल का?", "mr"),
    ("येथे हवामान कसे आहे?", "mr"),
])
def test_here_is_detected_by_the_rules_in_all_five_languages(text, lang):
    pq = nlu.parse(text, lang_hint=lang)
    assert pq.here is True
    assert pq.place is None


@_STEP3
def test_here_promotes_a_weather_question_with_no_city():
    pq = nlu.parse("weather at my location tomorrow")
    assert (pq.intent, pq.time_window, pq.source) == ("current_weather", "tomorrow", "rules")


@_STEP3
@pytest.mark.parametrize("text,place", [
    ("weather in Trichy", "Trichy"),
    ("will it rain in Tiruchirappalli tomorrow", "Tiruchirappalli"),
    ("Kumbakonam weather", "Kumbakonam"),
])
def test_a_gazetteer_place_is_extracted_and_answered_by_the_rules(text, place):
    pq = nlu.parse(text)
    assert pq.place == place
    assert pq.intent in ("current_weather", "will_it_rain") and pq.source == "rules"
    assert pq.here is False


@_STEP3
def test_a_native_script_gazetteer_place_is_extracted_with_its_case_suffix():
    pq = nlu.parse("తిరుపతిలో వాతావరణం ఎలా ఉంది?", lang_hint="te")
    assert pq.place == "తిరుపతి"


@_STEP3
def test_an_unknown_place_is_unsupported_and_still_named():
    pq = nlu.parse("weather in Xyzabad")
    assert pq.intent == "unsupported_city"
    assert pq.place == "Xyzabad"


@_STEP3
def test_a_demo_city_is_still_its_key():
    pq = nlu.parse("weather in Chennai")
    assert pq.city == "chennai" and pq.place is not None


@_STEP3
def test_llm_gazetteer_place_is_not_a_refusal(monkeypatch):
    _llm_says(monkeypatch, '{"intent":"current_weather","city":"तिरुचिरापल्ली",'
                           '"time_window":"today","days":null,"parameter":"general",'
                           '"language":"hi","confidence":0.9}')
    pq = nlu.parse("तिरुचिरापल्ली का मौसम कैसा है?", lang_hint="hi")
    assert pq.intent == "current_weather" and pq.source == "llm"
    assert pq.place == "तिरुचिरापल्ली"


@_STEP3
def test_llm_here_flag_is_read(monkeypatch):
    _llm_says(monkeypatch, '{"intent":"will_it_rain","city":null,"here":true,'
                           '"time_window":"tomorrow","days":null,"parameter":"rain",'
                           '"language":"te","confidence":0.9}')
    pq = nlu.parse("రేపు మా ఊరిలో వర్షం పడుతుందా?", lang_hint="te")
    assert pq.here is True and pq.place is None


@_STEP3
def test_here_is_in_the_llm_schema_and_prompt():
    assert nlu._NLU_SCHEMA["properties"]["here"] == {"type": "boolean"}
    assert '"here"' in nlu._NLU_PROMPT or "here:" in nlu._NLU_PROMPT


def test_llm_place_outside_india_stays_a_refusal(monkeypatch):
    _llm_says(monkeypatch, '{"intent":"current_weather","city":"London",'
                           '"time_window":"today","days":null,"parameter":"general",'
                           '"language":"en","confidence":0.9}')
    pq = nlu.parse("how's the weather over in london these days")
    assert pq.intent == "unsupported_city"
