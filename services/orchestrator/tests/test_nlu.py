"""nlu.parse(): the EN/TA rule fast-path, precedence between overlapping
patterns, and the LLM path (Gemini -> Groq -> rules_fallback) when the rules
don't confidently apply. All offline — LLM keys are patched off by default.
"""

import config
import narrate
import nlu
import pytest
from cities import resolve as resolve_city
from intent import parse_intent


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)


# --- script detection -------------------------------------------------------

def test_detect_script_tamil():
    assert nlu.detect_script("சென்னையில் மழை பெய்யுமா?") == "ta"


def test_detect_script_telugu():
    assert nlu.detect_script("చెన్నైలో వర్షం పడుతుందా?") == "te"


def test_telugu_script_is_a_supported_language_without_llm(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    pq = nlu.parse("చెన్నైలో వర్షం పడుతుందా?")
    assert pq.language == "te" and pq.source == "rules_fallback"


def test_detect_script_devanagari():
    assert nlu.detect_script("कल चेन्नई में बारिश होगी क्या?") == "deva"


def test_detect_script_english():
    assert nlu.detect_script("will it rain in Chennai tomorrow") == "en"


def test_detect_script_other():
    assert nlu.detect_script("ചെന്നൈയിൽ നാളെ മഴ പെയ്യുമോ?") == "other"


def test_detect_script_mixed_favors_indic():
    assert nlu.detect_script("Chennai-ல் மழை") == "ta"


# --- rules: each P0 intent x windows x params -------------------------------

def test_rules_current_weather_today():
    pq = nlu.parse("what's the weather in Chennai")
    assert (pq.intent, pq.time_window, pq.parameter, pq.source) == \
        ("current_weather", "today", "general", "rules")


def test_rules_will_it_rain_tomorrow():
    pq = nlu.parse("will it rain in Madurai tomorrow")
    assert (pq.intent, pq.time_window, pq.parameter, pq.source) == \
        ("will_it_rain", "tomorrow", "rain", "rules")


def test_rules_forecast_next_n_days():
    pq = nlu.parse("3 day forecast for Coimbatore")
    assert (pq.intent, pq.time_window, pq.days, pq.source) == \
        ("forecast", "next_n_days", 3, "rules")


def test_rules_this_week_defaults_to_seven():
    pq = nlu.parse("Chennai weather this week")
    assert pq.days == 7


def test_rules_rainfall_so_far_today():
    pq = nlu.parse("how much rain has Chennai had so far today?")
    assert (pq.intent, pq.time_window, pq.parameter, pq.source) == \
        ("rainfall_so_far_today", "today", "rain", "rules")


def test_rules_temperature_param():
    pq = nlu.parse("how hot is it in Chennai")
    assert pq.parameter == "temperature"


def test_rules_humidity_param():
    pq = nlu.parse("humidity in Chennai today")
    assert pq.parameter == "humidity"


def test_rules_wind_param():
    pq = nlu.parse("wind speed in Chennai")
    assert pq.parameter == "wind"


# --- warnings vs out_of_scope (audit 2.3) -----------------------------------
# A warning / alert question is answered from imd_warnings, whatever the
# hazard; the products plan.md §3.1 says we don't have (cyclone track /
# landfall, tsunami, marine / fishermen bulletins) and bare hazard questions
# with no warning word stay out of scope.

@pytest.mark.parametrize("text,city", [
    ("is there any warning for Chennai?", "chennai"),
    ("red alert in Chennai today?", "chennai"),
    ("flood warning for Madurai tomorrow?", "madurai"),
    ("cyclone warning for Chennai?", "chennai"),
    ("storm warning for Chennai", "chennai"),
    ("heavy rain warning in Coimbatore", "coimbatore"),
    ("any weather alerts in Madurai?", "madurai"),
    ("weather advisory for Madurai", "madurai"),
    ("சென்னைக்கு ஏதேனும் எச்சரிக்கை உள்ளதா?", "chennai"),
    ("சென்னையில் வெள்ள எச்சரிக்கை உள்ளதா?", "chennai"),
    ("மதுரைக்கு ரெட் அலர்ட் உள்ளதா?", "madurai"),
])
def test_rules_warning_shaped_query_is_warnings(text, city):
    pq = nlu.parse(text)
    assert (pq.intent, resolve_city(pq.city), pq.source, pq.confidence) == \
        ("warnings", city, "rules", 0.9)


@pytest.mark.parametrize("text", [
    "is a cyclone hitting Chennai tomorrow?",
    "will Chennai flood tomorrow?",
    "where will the cyclone make landfall?",
    "cyclone track near Chennai",
    "path of the cyclone",
    "tsunami warning for Chennai?",
    "is there a warning for fishermen in Chennai?",
    "marine bulletin for Chennai",
    "storm surge warning Chennai",
    "rough sea warning",
    "சென்னையில் புயல் வருமா?",
    "சுனாமி எச்சரிக்கை உள்ளதா?",
    "மீனவர்களுக்கு எச்சரிக்கை உள்ளதா?",
    "புயல் கரையைக் கடக்குமா?",
])
def test_rules_unsupported_products_stay_out_of_scope(text):
    pq = nlu.parse(text)
    assert (pq.intent, pq.source) == ("out_of_scope", "rules")


def test_rules_warnings_hit_needs_no_city():
    pq = nlu.parse("is there any warning?")
    assert (pq.intent, pq.city, pq.source) == ("warnings", None, "rules")


def test_rules_warnings_hit_never_calls_the_llm(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")

    def _boom(*a, **k):
        raise AssertionError("generate() was called")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(narrate, "generate_groq", _boom)
    pq = nlu.parse("is there any warning for Chennai?")
    assert pq.intent == "warnings" and pq.source == "rules"


def test_rules_warning_for_unsupported_city_is_a_refusal():
    pq = nlu.parse("warning in Mumbai")
    assert pq.intent == "unsupported_city"


def test_warnings_in_llm_schema_enum():
    assert "warnings" in nlu._NLU_SCHEMA["properties"]["intent"]["enum"]


def test_llm_warnings_intent_is_accepted(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        narrate, "generate",
        lambda *a, **k: '{"intent":"warnings","city":"chennai","time_window":"today",'
                        '"days":null,"parameter":"general","language":"hi","confidence":0.9}',
    )
    pq = nlu.parse("क्या चेन्नई के लिए कोई चेतावनी है?")
    assert (pq.intent, pq.city, pq.language, pq.source) == ("warnings", "chennai", "hi", "llm")


def test_llm_warnings_for_unknown_city_becomes_unsupported_city(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        narrate, "generate",
        lambda *a, **k: '{"intent":"warnings","city":"Mumbai","time_window":"today",'
                        '"days":null,"parameter":"general","language":"hi","confidence":0.9}',
    )
    pq = nlu.parse("क्या मुंबई के लिए कोई चेतावनी है?")
    assert pq.intent == "unsupported_city" and pq.source == "llm"


# --- precedence --------------------------------------------------------------

def test_precedence_out_of_scope_beats_rain():
    pq = nlu.parse("is a cyclone hitting Chennai tomorrow?")
    assert pq.intent == "out_of_scope"


def test_precedence_warning_word_beats_rain_so_far():
    pq = nlu.parse("how much rain so far in Chennai, any warning?")
    assert pq.intent == "warnings"


def test_precedence_rain_so_far_beats_will_it_rain():
    pq = nlu.parse("how much rain has fallen in Chennai so far?")
    assert pq.intent == "rainfall_so_far_today"


def test_precedence_next_n_beats_tomorrow():
    pq = nlu.parse("next 3 days forecast for Chennai tomorrow")
    assert pq.time_window == "next_n_days" and pq.days == 3


def test_day_after_tomorrow():
    pq = nlu.parse("day after tomorrow weather in Chennai")
    assert pq.time_window == "day_after_tomorrow"


def test_day_after_tomorrow_tamil():
    pq = nlu.parse("நாளை மறுநாள் சென்னையில் மழை பெய்யுமா?")
    assert pq.time_window == "day_after_tomorrow" and pq.intent == "will_it_rain"


# --- test_intent.py rows resolve identically (that file is untouched) -------

@pytest.mark.parametrize("text,expected_intent,expected_city,expected_day", [
    ("நாளை சென்னையில் மழை பெய்யுமா?", "will_it_rain", "chennai", "tomorrow"),
    ("இன்று மதுரையில் மழை வருமா?", "will_it_rain", "madurai", "today"),
    ("இன்றிரவு கோயம்புத்தூரில் மழை பெய்யுமா?", "will_it_rain", "coimbatore", "tonight"),
    ("சென்னை வானிலை", "current_weather", "chennai", "today"),
    ("will it rain in Chennai tomorrow", "will_it_rain", "chennai", "tomorrow"),
])
def test_intent_rows_resolve_identically(text, expected_intent, expected_city, expected_day):
    legacy = parse_intent(text)
    assert legacy["intent"] == expected_intent
    assert resolve_city(legacy["city"]) == expected_city
    assert legacy["day"] == expected_day

    pq = nlu.parse(text)
    assert pq.intent == expected_intent
    assert resolve_city(pq.city) == expected_city
    assert pq.time_window == expected_day


def test_unrecognized_has_no_city():
    pq = nlu.parse("hello there")
    assert pq.intent == "unrecognized" and pq.city is None


def test_city_only_chennai_is_rules_fallback():
    pq = nlu.parse("Chennai")
    assert pq.intent == "current_weather" and pq.source == "rules_fallback"


# --- LLM path ----------------------------------------------------------------

_CANNED = {
    "hi": '{"intent":"will_it_rain","city":"chennai","time_window":"tomorrow","days":null,'
          '"parameter":"rain","language":"hi","confidence":0.9}',
    "te": '{"intent":"current_weather","city":"madurai","time_window":"today","days":null,'
          '"parameter":"general","language":"te","confidence":0.9}',
    "mr": '{"intent":"forecast","city":"chennai","time_window":"next_n_days","days":3,'
          '"parameter":"general","language":"mr","confidence":0.9}',
}


@pytest.mark.parametrize("lang", ["hi", "te", "mr"])
def test_llm_path_returns_source_llm_with_right_language(monkeypatch, lang):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: _CANNED[lang])
    pq = nlu.parse("some native-language text")
    assert pq.source == "llm" and pq.language == lang


def test_llm_invalid_json_falls_back_to_rules():
    import config as cfg

    cfg.GEMINI_API_KEY = "k"
    try:
        import narrate as nr
        orig = nr.generate
        nr.generate = lambda *a, **k: "not json"
        pq = nlu.parse("hello there")
        assert pq.source == "rules_fallback"
    finally:
        nr.generate = orig
        cfg.GEMINI_API_KEY = None


def test_llm_unknown_city_becomes_unsupported_city(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        narrate, "generate",
        lambda *a, **k: '{"intent":"current_weather","city":"Mumbai","time_window":"today",'
                        '"days":null,"parameter":"general","language":"en","confidence":0.9}',
    )
    pq = nlu.parse("weather in Mumbai")
    assert pq.intent == "unsupported_city" and pq.source == "llm"


def test_llm_enum_violation_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        narrate, "generate",
        lambda *a, **k: '{"intent":"bogus_intent","city":"chennai","time_window":"today",'
                        '"days":null,"parameter":"general","language":"en","confidence":0.9}',
    )
    pq = nlu.parse("hello there")
    assert pq.source == "rules_fallback"


def test_llm_language_other_becomes_none(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        narrate, "generate",
        lambda *a, **k: '{"intent":"will_it_rain","city":"chennai","time_window":"tomorrow",'
                        '"days":null,"parameter":"rain","language":"other","confidence":0.9}',
    )
    pq = nlu.parse("ചെന്നൈയിൽ നാളെ മഴ പെയ്യുമോ?")
    assert pq.language is None and pq.source == "llm"


def test_llm_gemini_raises_groq_stub_used(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")

    def _boom(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(
        narrate, "generate_groq",
        lambda *a, **k: '{"intent":"will_it_rain","city":"chennai","time_window":"tomorrow",'
                        '"days":null,"parameter":"rain","language":"hi","confidence":0.9}',
    )
    pq = nlu.parse("kal chennai mein baarish hogi kya?")
    assert pq.source == "llm" and pq.language == "hi"


def test_llm_both_providers_raise_falls_back(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")

    def _boom(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(narrate, "generate_groq", _boom)
    pq = nlu.parse("hello there")
    assert pq.source == "rules_fallback"


def test_is_configured_false_never_calls_generate(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("generate() was called")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(narrate, "generate_groq", _boom)
    pq = nlu.parse("hello there")
    assert pq.source == "rules_fallback"


def test_script_overrides_llm_language_for_tamil_telugu(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: _CANNED["hi"].replace(
        '"language":"hi"', '"language":"ta"'))
    pq = nlu.parse("చెన్నైలో వర్షం పడుతుందా?")
    assert pq.source == "llm" and pq.language == "te"


# --- Ollama path (plan.md §8 Phase 6) ----------------------------------------

def test_llm_path_via_ollama(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    captured = {}

    def _ollama_stub(*a, response_schema=None, **k):
        captured["response_schema"] = response_schema
        return _CANNED["hi"]

    monkeypatch.setattr(narrate, "generate_ollama", _ollama_stub)
    pq = nlu.parse("some native-language text")
    assert pq.source == "llm" and pq.language == "hi"
    assert captured["response_schema"]["type"] == "object"


def test_gemini_receives_gemini_dialect_schema(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    captured = {}

    def _gemini_stub(*a, response_schema=None, **k):
        captured["response_schema"] = response_schema
        return _CANNED["hi"]

    monkeypatch.setattr(narrate, "generate", _gemini_stub)
    nlu.parse("some native-language text")
    assert captured["response_schema"]["type"] == "OBJECT"
    assert "propertyOrdering" in captured["response_schema"]


def test_offline_mode_nlu_uses_ollama_only(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _boom(*a, **k):
        raise AssertionError("cloud provider called in OFFLINE_MODE")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(narrate, "generate_groq", _boom)
    monkeypatch.setattr(narrate, "generate_ollama", lambda *a, **k: _CANNED["hi"])
    pq = nlu.parse("some native-language text")
    assert pq.source == "llm" and pq.language == "hi"


def test_all_three_providers_raise_falls_back(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _boom(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(narrate, "generate_groq", _boom)
    monkeypatch.setattr(narrate, "generate_ollama", _boom)
    pq = nlu.parse("hello there")
    assert pq.source == "rules_fallback"
