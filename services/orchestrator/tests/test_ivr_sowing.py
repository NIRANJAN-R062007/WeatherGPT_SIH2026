"""ivr_sowing.py: the sowing advisory over the IVR call (plan.md §8 TFA-14).

The advisory runs for real on the fixture forecast and the real crop file, with the
agent off (template answer), so the spoken text is the one a caller would hear.
Bhashini is mocked; conftest blocks the network."""

import base64

import config
import ivr
import ivr_sowing
import pytest

MADURAI = "when should I sow groundnut in Madurai"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", False)
    ivr_sowing._pending.clear()
    yield
    ivr_sowing._pending.clear()


@pytest.mark.parametrize("text", [
    "when should I sow groundnut in Madurai",
    "is it a good time for sowing ragi",
    "मदुरै में मूंगफली की बुवाई कब करूँ",
    "மதுரையில் நிலக்கடலை எப்போது விதைக்கலாம்",
    "మదురైలో వేరుశెనగ ఎప్పుడు విత్తాలి",
    "मदुराईत भुईमूग पेरणी कधी करावी",
])
def test_sowing_questions_are_recognised_in_every_language(text):
    assert ivr_sowing.is_sowing_question(text)


@pytest.mark.parametrize("text", ["will it rain on my paddy field today",
                                  "what is the weather in Madurai", ""])
def test_a_weather_question_naming_a_crop_is_not_a_sowing_question(text):
    assert not ivr_sowing.is_sowing_question(text)


def test_a_non_sowing_question_is_left_to_ask():
    assert ivr_sowing.reply("CA1", "will it rain in Chennai today", "en") is None


def test_a_full_sowing_question_is_answered_from_the_crop_file():
    text = ivr_sowing.reply("CA1", MADURAI, "en")
    # The fixture forecast is for September, outside TNAU's Madurai months.
    assert text.startswith("Conditions do not look suitable for sowing groundnut in Madurai now.")
    assert "sowing months are" in text
    assert "reviewed by an agronomist" in text
    assert text.endswith(ivr_sowing.DISCLAIMER)
    assert "CA1" not in ivr_sowing._pending


def test_a_missing_district_is_asked_for_and_the_next_recording_answers_it():
    question = ivr_sowing.reply("CA2", "when should I sow groundnut", "en")
    assert question == "Which district are you in? Name the nearest city."
    assert ivr_sowing._pending["CA2"][1] == {"crop": "groundnut"}
    # The reply has no sowing word in it: the open conversation carries it.
    text = ivr_sowing.reply("CA2", "Madurai", "en")
    assert text.startswith("Conditions do not look suitable for sowing groundnut in Madurai")
    assert "CA2" not in ivr_sowing._pending


def test_an_open_conversation_is_only_on_its_own_call():
    ivr_sowing.reply("CA3", "when should I sow groundnut", "en")
    assert ivr_sowing.reply("CA4", "Madurai", "en") is None


def test_an_open_conversation_expires(monkeypatch):
    ivr_sowing.reply("CA5", "when should I sow groundnut", "en")
    expires = ivr_sowing._pending["CA5"][0]
    monkeypatch.setattr(ivr_sowing.time, "monotonic", lambda: expires + 1)
    assert ivr_sowing.reply("CA5", "Madurai", "en") is None


def test_a_crop_the_file_does_not_cover_says_so():
    text = ivr_sowing.reply("CA6", "when should I sow rice in Madurai", "en")
    assert text.startswith("I can't judge sowing rice in Madurai.")
    assert "no entry for this crop" in text


def test_a_suitable_answer_says_its_window():
    answer = {"verdict": "suitable", "pros": ["Rain chance today is 10% (1.2 mm)."], "cons": [],
              "window": {"start_local": "08:00", "end_local": "11:00"}}
    text = ivr_sowing.english_text(answer, {"crop": "groundnut", "district": "madurai"})
    assert text == ("Conditions look suitable for sowing groundnut in Madurai. "
                    "Rain chance today is 10% (1.2 mm). Today's best hours are 08:00 to 11:00. "
                    + ivr_sowing.DISCLAIMER)


def test_only_the_first_reasons_are_read_out():
    answer = {"verdict": "not_suitable", "pros": [], "cons": ["One.", "Two.", "Three."]}
    text = ivr_sowing.english_text(answer, {"crop": "ragi", "district": "chennai"})
    assert "Two." in text and "Three." not in text


# --- other languages ------------------------------------------------------------------


def _bhashini(monkeypatch, translate):
    monkeypatch.setattr("bhashini.is_configured", lambda: True)
    monkeypatch.setattr("bhashini.translate", translate)


def test_a_translation_that_keeps_the_numbers_is_said(monkeypatch):
    seen = []
    _bhashini(monkeypatch, lambda text, lang: seen.append(text) or f"[{lang}] {text}")
    text = ivr_sowing.reply("CA7", MADURAI, "ta")
    assert text.startswith("[ta] Conditions do not look suitable")
    assert seen and "Madurai" in seen[0]


def test_a_translation_with_a_wrong_number_falls_back_to_the_verdict(monkeypatch):
    _bhashini(monkeypatch, lambda text, lang: "மழை வாய்ப்பு 99% ஆகும்.")
    assert ivr_sowing.reply("CA8", MADURAI, "ta") == ivr_sowing.fallback_text("not_suitable", "ta")


def test_no_bhashini_falls_back_to_the_verdict(monkeypatch):
    monkeypatch.setattr("bhashini.is_configured", lambda: False)
    text = ivr_sowing.reply("CA9", MADURAI, "hi")
    assert text == ivr_sowing.fallback_text("not_suitable", "hi")
    assert "KVK" in text


@pytest.mark.parametrize("lang", ["en", "hi", "ta", "te", "mr"])
def test_every_verdict_has_a_fallback_in_every_language(lang):
    for verdict in ("suitable", "not_suitable", "not_available"):
        assert ivr_sowing.fallback_text(verdict, lang)
    assert ivr_sowing.fallback_text(None, lang) == ivr_sowing.fallback_text("not_available", lang)


def test_the_ask_back_question_is_in_the_callers_language():
    question = ivr_sowing.reply("CA10", "मूंगफली की बुवाई कब करूँ", "hi")
    assert question and not question.isascii()


# --- through ivr.process_recording ----------------------------------------------------


def _call(monkeypatch, transcript):
    ivr._answer_cache.clear()
    monkeypatch.setattr(ivr, "_download_recording", lambda url: b"RIFF")
    monkeypatch.setattr("bhashini.speech_to_text", lambda *a, **k: transcript)
    spoken = []

    def tts(text, lang):
        spoken.append(text)
        return base64.b64encode(b"wav").decode()

    monkeypatch.setattr("bhashini.text_to_speech", tts)
    return spoken


def test_a_sowing_call_is_answered_by_the_advisory_not_ask(monkeypatch):
    spoken = _call(monkeypatch, MADURAI)

    def ask(**kw):
        raise AssertionError("a sowing question must not reach /ask")

    ivr.process_recording("SIM-1", "en", "https://example.test/r.wav", ask, lambda k, lg: k)
    assert spoken and spoken[0].startswith("Conditions do not look suitable for sowing groundnut")
    assert ivr._cache_get("SIM-1") == b"wav"


def test_any_other_call_still_goes_to_ask(monkeypatch):
    spoken = _call(monkeypatch, "will it rain in Chennai")
    ivr.process_recording("SIM-2", "en", "https://example.test/r.wav",
                          lambda **kw: {"response": "Light rain today."}, lambda k, lg: k)
    assert spoken == ["Light rain today."]


def test_a_failing_advisory_still_answers_the_call(monkeypatch):
    spoken = _call(monkeypatch, MADURAI)

    def boom(*a, **k):
        raise RuntimeError("agent down")

    monkeypatch.setattr(ivr_sowing.advisory_agent, "advise", boom)
    ivr.process_recording("SIM-3", "ta", "https://example.test/r.wav",
                          lambda **kw: {}, lambda k, lg: f"[{k}:{lg}]")
    assert spoken == ["[no_data:ta]"]
