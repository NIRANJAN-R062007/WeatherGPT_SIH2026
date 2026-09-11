"""The full /ask narration chain: LLM answer -> guardrail -> template fallback
-> refuse. The guardrail runs on whatever the LLM produces.
"""

import cities
import config
import google_weather
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


def test_tamil_uses_bhashini_translation_of_grounded_english(monkeypatch):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    monkeypatch.setattr(main.bhashini, "is_configured", lambda: True)
    monkeypatch.setattr(main.bhashini, "translate_to_tamil",
                        lambda text: "சென்னை: 28°C, ஈரப்பதம் 81%.")
    body = _ask("what's the weather in Chennai", lang="ta")
    assert body["response"] == "சென்னை: 28°C, ஈரப்பதம் 81%."
    assert body["grounding"]["narration"] == "llm+bhashini"
    assert body["grounding"]["fallback_used"] is False
    assert body["grounding"]["ok"] is True


def test_tamil_falls_back_to_template_when_bhashini_unconfigured(monkeypatch):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    monkeypatch.setattr(main.bhashini, "translate_to_tamil", lambda text: None)
    body = _ask("what's the weather in Chennai", lang="ta")
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["fallback_used"] is True  # LLM grounded in EN, translation failed


def test_tamil_falls_back_to_template_when_translation_hallucinates(monkeypatch):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: cloudy, 28°C right now, humidity 81%.")
    monkeypatch.setattr(main.bhashini, "translate_to_tamil",
                        lambda text: "சென்னை: 99°C.")  # bad translation, doesn't ground
    body = _ask("what's the weather in Chennai", lang="ta")
    assert body["grounding"]["narration"] == "template"
    assert "99" not in body["response"]


@pytest.mark.parametrize("key", sorted(["chennai", "madurai", "coimbatore"]))
@pytest.mark.parametrize("lang", ["en", "ta"])
@pytest.mark.parametrize("intent_text", [
    "what's the weather in {c}", "will it rain in {c} tomorrow",
])
def test_all_combos_ground_with_llm_stub(monkeypatch, key, lang, intent_text):
    # EN narration returns a grounded sentence; TA path uses the template
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
