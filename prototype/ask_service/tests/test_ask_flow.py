"""The full /ask narration chain: LLM answer -> guardrail -> template fallback
-> refuse. The guardrail runs on whatever the LLM produces.
"""

import cities
import config
import google_weather
import httpx
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params}).json()


def test_grounded_llm_answer_is_used(monkeypatch):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: warm and cloudy at 28°C, humidity 81%.")
    body = _ask("what's the weather in Chennai")
    assert body["response"].startswith("Chennai: warm and cloudy")
    assert body["grounding"]["narration"] == "llm"
    assert body["grounding"]["ok"] is True
    assert body["grounding"]["fallback_used"] is False


def test_hallucinated_llm_answer_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: "Chennai: 99°C and 4 inches of rain.")
    body = _ask("what's the weather in Chennai")
    assert "99" not in body["response"] and "4 inches" not in body["response"]
    assert body["response"] == "Chennai: cloudy, 28°C right now, feels like 32.5°C, humidity 81%."
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["fallback_used"] is True
    assert body["grounding"]["ok"] is True


def test_llm_unavailable_uses_template_without_flagging_fallback(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["fallback_used"] is False
    assert body["grounding"]["attempts"] == 1  # nothing to regenerate from


@pytest.mark.parametrize("lang", ["ta", "hi", "te", "mr"])
def test_non_english_uses_bhashini_translation_of_grounded_english(monkeypatch, lang):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    monkeypatch.setattr(main.bhashini, "is_configured", lambda: True)
    seen = []

    def _translate(text, target_lang):
        seen.append(target_lang)
        return f"[{target_lang}] Chennai: 28°C, 81%."

    monkeypatch.setattr(main.bhashini, "translate", _translate)
    body = _ask("what's the weather in Chennai", lang=lang)
    assert body["response"] == f"[{lang}] Chennai: 28°C, 81%."
    assert seen == [lang]  # translate() is called with the requested target language
    assert body["grounding"]["narration"] == "llm+bhashini"
    assert body["grounding"]["fallback_used"] is False
    assert body["grounding"]["ok"] is True


@pytest.mark.parametrize("lang", ["ta", "hi", "te", "mr"])
def test_non_english_falls_back_to_template_when_bhashini_unconfigured(monkeypatch, lang):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    monkeypatch.setattr(main.bhashini, "is_configured", lambda: True)
    monkeypatch.setattr(main.bhashini, "translate", lambda text, target_lang: None)
    body = _ask("what's the weather in Chennai", lang=lang)
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["fallback_used"] is True  # LLM grounded in EN, translation failed


@pytest.mark.parametrize("lang", ["ta", "hi", "te", "mr"])
def test_non_english_falls_back_to_template_when_translation_hallucinates(monkeypatch, lang):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    monkeypatch.setattr(main.bhashini, "is_configured", lambda: True)
    monkeypatch.setattr(main.bhashini, "translate",
                        lambda text, target_lang: "99°C, nonsense.")  # doesn't ground
    body = _ask("what's the weather in Chennai", lang=lang)
    assert body["grounding"]["narration"] == "template"
    assert "99" not in body["response"]


@pytest.mark.parametrize("key", sorted(["chennai", "madurai", "coimbatore"]))
@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
@pytest.mark.parametrize("intent_text", [
    "what's the weather in {c}", "will it rain in {c} tomorrow",
])
def test_all_combos_ground_with_llm_stub(monkeypatch, key, lang, intent_text):
    # EN narration returns a grounded sentence; every non-EN path uses the template
    # (no bhashini keys configured in this test module)
    monkeypatch.setattr(
        main, "narrate",
        lambda intent, city, facts, ln: (
            f"{city}: {facts.get('temp_c', facts.get('rain_probability_pct'))}"
            f"{'°C' if 'temp_c' in facts else '%'}." if ln == "en" else None
        ),
    )
    name = cities.CITIES[key].names["en"]
    body = _ask(intent_text.format(c=name), lang=lang)
    assert body["city"] == key
    g = body["grounding"]
    assert g["ok"] is True and g["matched"] == g["total"] >= 1


def test_provenance_and_health_shape(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("what's the weather in Chennai")
    assert set(body["provenance"]) == {"source", "issued", "is_live", "retrieved_at"}
    health = client.get("/health").json()
    assert health["weather_source"] in {"fixtures", "google-weather-api"}
    assert "weather_cache" in health and "narration" in health
    assert set(health["llm"]) == {"offline_mode", "providers", "ollama"}
    assert set(health["llm"]["ollama"]) == {"base", "model", "reachable", "model_present"}
    assert "weather_mode" in health and "offline_mode" in health


def test_grounding_provider_is_template_when_no_llm_answer(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["provider"] == "template"


def test_grounding_provider_reports_ollama(monkeypatch):
    def _narrate(intent, city, facts, lang, **kw):
        main.narrate_module.last_provider = "ollama"
        return "Chennai: cloudy, 28°C right now, humidity 81%."

    monkeypatch.setattr(main, "narrate", _narrate)
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["provider"] == "ollama"
    assert body["grounding"]["ok"] is True


def test_offline_mode_falls_through_ollama_to_grounded_answer(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _boom(*a, **k):
        raise AssertionError("cloud provider called in OFFLINE_MODE")

    monkeypatch.setattr(main.narrate_module, "generate", _boom)
    monkeypatch.setattr(main.narrate_module, "generate_groq", _boom)
    monkeypatch.setattr(main.narrate_module, "generate_ollama",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["provider"] == "ollama"
    assert body["grounding"]["ok"] is True


def test_offline_mode_ollama_connect_error_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _boom(*a, **k):
        raise AssertionError("cloud provider called in OFFLINE_MODE")

    def _connect_error(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(main.narrate_module, "generate", _boom)
    monkeypatch.setattr(main.narrate_module, "generate_groq", _boom)
    monkeypatch.setattr(main.narrate_module, "generate_ollama", _connect_error)
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["provider"] == "template"
    assert body["grounding"]["fallback_used"] is False
    assert body["grounding"]["attempts"] == 1


def test_mocked_live_data_marks_is_live(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)

    def _serve(path, params, timeout=google_weather.TIMEOUT):
        kind = "current_conditions" if "currentConditions" in path else "forecast_days"
        city = min(cities.CITY_KEYS,
                   key=lambda c: abs(cities.CITIES[c].lat - params["location.latitude"]))
        import json
        return json.loads(
            (config.FIXTURES_DIR / "google_weather" / f"{kind}.{city}.json").read_text()
        )["response"]

    monkeypatch.setattr(google_weather, "fetch_json", _serve)
    body = _ask("what's the weather in Chennai")
    assert body["provenance"]["is_live"] is True
    assert body["grounding"]["ok"] is True


def test_rainfall_so_far_end_to_end_template_path(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("how much rain has Chennai had so far today?")
    assert body["intent"] == "rainfall_so_far_today"
    assert body["nlu"]["intent"] == "rainfall_so_far_today"
    assert body["grounding"]["narration"] == "template"
    assert set(body["provenance"]) == {"source", "issued", "is_live", "retrieved_at"}


def test_next_n_days_caps_and_grounds(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("5 day forecast for Chennai")
    assert body["nlu"]["days"] == 5
    assert body["grounding"]["ok"] is True


def test_day_after_tomorrow_resolves(monkeypatch):
    # With FORECAST_DAYS raised to 5, day_after_tomorrow (offset 2) is within the
    # fixture range and now answers instead of refusing.
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("day after tomorrow weather in Chennai")
    assert "response" in body
    assert set(body["provenance"]) == {"source", "issued", "is_live", "retrieved_at"}


def test_out_of_scope_cyclone_returns_message_no_response():
    body = _ask("is a cyclone hitting Chennai tomorrow")
    assert body["intent"] == "out_of_scope"
    assert "message" in body and "response" not in body


def test_unsupported_script_gets_notice(monkeypatch):
    monkeypatch.setattr(
        main.nlu, "_llm_parse",
        lambda text: main.nlu.ParsedQuery(
            intent="will_it_rain", city="chennai", time_window="tomorrow", days=None,
            parameter="rain", language=None, source="llm", confidence=0.9,
        ),
    )
    import narrate as narrate_module

    monkeypatch.setattr(narrate_module, "is_configured", lambda: True)
    body = _ask("ചെന്നൈയിൽ നാളെ മഴ പെയ്യുമോ?")
    assert "notice" in body


def test_regenerate_once_then_ok(monkeypatch):
    calls = {"n": 0}

    def _narrate(intent, city, facts, lang, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return "Chennai: 99°C, hallucinated."
        return "Chennai: cloudy, 28°C right now, humidity 81%."

    monkeypatch.setattr(main, "narrate", _narrate)
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["attempts"] == 2
    assert body["grounding"]["narration"] == "llm"
    assert body["grounding"]["fallback_used"] is False


def test_regenerate_twice_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: "Chennai: 99°C, hallucinated.")
    body = _ask("what's the weather in Chennai")
    assert body["grounding"]["attempts"] == 2
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["fallback_used"] is True


def test_legacy_keys_preserved(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = _ask("what's the weather in Chennai")
    assert {"intent", "city", "day", "response", "provenance", "grounding"} <= set(body)


def test_facts_endpoint_current_and_forecast():
    cur = client.get("/facts", params={"city": "Chennai", "lang": "ta"}).json()
    assert cur["city"] == "chennai" and cur["city_name"] == "சென்னை"
    assert cur["condition_label"] and "temp_c" in cur["facts"] and "wind_kmh" in cur["facts"]
    fc = client.get("/facts", params={"city": "madurai", "intent": "will_it_rain",
                                      "day": "tomorrow"}).json()
    assert "rain_probability_pct" in fc["facts"] and "high_c" in fc["facts"]
    assert "message" in client.get("/facts", params={"city": "mumbai"}).json()


def test_asr_endpoint_returns_transcript(monkeypatch):
    monkeypatch.setattr(main.bhashini, "speech_to_text",
                        lambda audio, lang, rate: "chennai weather")
    body = client.post("/asr", json={"audio": "base64wav", "lang": "en"}).json()
    assert body == {"text": "chennai weather"}


def test_asr_endpoint_unavailable_returns_message(monkeypatch):
    monkeypatch.setattr(main.bhashini, "speech_to_text", lambda audio, lang, rate: None)
    body = client.post("/asr", json={"audio": "base64wav", "lang": "ta"}).json()
    assert body["text"] is None
    assert body["message"] == main._msg("voice_unavailable", "ta")


def test_tts_endpoint_returns_audio(monkeypatch):
    monkeypatch.setattr(main.bhashini, "text_to_speech", lambda text, lang: "UklGRi4=")
    body = client.post("/tts", json={"text": "Chennai: 28°C.", "lang": "en"}).json()
    assert body == {"audio": "UklGRi4=", "format": "wav"}


def test_tts_endpoint_unavailable_returns_null_audio(monkeypatch):
    monkeypatch.setattr(main.bhashini, "text_to_speech", lambda text, lang: None)
    body = client.post("/tts", json={"text": "hello", "lang": "en"}).json()
    assert body == {"audio": None}


@pytest.mark.parametrize("lang", ["ta", "hi", "te", "mr"])
def test_non_english_without_bhashini_skips_narration_entirely(monkeypatch, lang):
    monkeypatch.setattr(main.bhashini, "is_configured", lambda: False)
    monkeypatch.setattr(main, "narrate", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    body = _ask("what's the weather in Chennai", lang=lang)
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["attempts"] == 0
    assert body["grounding"]["ok"] is True
