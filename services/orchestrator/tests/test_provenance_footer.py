"""The provenance footer (step 6): every weather answer names the place it is
for and the rounded point the data was fetched for — "Forecast for
Tiruchirappalli, Tamil Nadu (10.80°N, 78.70°E)." It is appended AFTER the
guardrail has validated the answer, so the numeric validator never sees the
footer's coordinates and its rules stay exactly as they were.
"""

import json

import config
import google_weather
import guardrail
import i18n
import main
import pytest
import weather_data
from fastapi.testclient import TestClient

client = TestClient(main.app)
_STEP6 = pytest.mark.xfail(strict=True, reason="step 6: provenance footer")
CHENNAI_FOOTER = "Forecast for Chennai (13.10°N, 80.25°E)."


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params}).json()


@_STEP6
def test_a_weather_answer_ends_with_the_place_and_rounded_point():
    body = _ask("what's the weather in Chennai")
    assert body["response"].endswith("\n" + CHENNAI_FOOTER)
    assert body["provenance"]["place"] == {"label": "Chennai", "lat": 13.10, "lon": 80.25}


@_STEP6
def test_a_gazetteer_answer_names_the_place_and_its_cell(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")

    def _serve(path, params, timeout=google_weather.TIMEOUT):
        kind = next(k for k, ep in google_weather.ENDPOINTS.items() if ep == path)
        env = config.FIXTURES_DIR / "google_weather" / f"{kind}.chennai.json"
        return json.loads(env.read_text(encoding="utf-8"))["response"]

    monkeypatch.setattr(google_weather, "fetch_json", _serve)
    body = _ask("what's the weather in Tiruchirappalli")
    assert body["response"].endswith(
        "\nForecast for Tiruchirappalli, Tamil Nadu (10.80°N, 78.70°E).")


@_STEP6
@pytest.mark.parametrize("lang", ["ta", "hi", "te", "mr"])
def test_the_footer_is_in_the_users_language(lang):
    body = _ask("what's the weather in Chennai", lang=lang)
    footer = i18n.place_footer(main.cities.display_name("chennai", lang), 13.10, 80.25, lang)
    assert body["response"].endswith("\n" + footer)


@_STEP6
def test_the_guardrail_never_sees_the_footer(monkeypatch):
    checked = []
    real = guardrail.check

    def _spy(text, data, *a, **k):
        checked.append(text)
        return real(text, data, *a, **k)

    monkeypatch.setattr(guardrail, "check", _spy)
    body = _ask("what's the weather in Chennai")
    assert checked and not any("°N" in t for t in checked)
    assert "°N" in body["response"] and body["grounding"]["ok"] is True


@_STEP6
def test_the_validator_still_rejects_an_invented_figure_with_a_footer_present(monkeypatch):
    monkeypatch.setattr(main, "narrate",
                        lambda *a, **k: "Chennai: 99°C and humidity 81% right now.")
    body = _ask("what's the weather in Chennai")
    assert "99" not in body["response"]                # the invented figure never ships
    assert body["grounding"]["fallback_used"] is True  # the validator rejected it
    assert body["response"].endswith(CHENNAI_FOOTER)
    # And on the validator itself: a footer does not launder a made-up number.
    data = weather_data.get_weather("chennai", "current_weather", "today")
    assert guardrail.check("Chennai: 99°C right now.\n" + CHENNAI_FOOTER, data).ok is False


@_STEP6
def test_an_ungrounded_refusal_still_names_the_place(monkeypatch):
    monkeypatch.setattr(guardrail, "check",
                        lambda *a, **k: guardrail.Report(ok=False, matched=0, total=1))
    body = _ask("what's the weather in Chennai")
    assert "response" not in body
    assert body["provenance"]["place"]["label"] == "Chennai"


def test_the_footer_carries_no_raw_gps(monkeypatch):
    body = _ask("what's the weather in Chennai", lat=10.790537, lon=78.704681)
    assert "10.790537" not in body["response"]
