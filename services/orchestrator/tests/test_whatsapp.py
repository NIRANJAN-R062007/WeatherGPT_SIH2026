"""whatsapp.py: the WhatsApp channel (plan.md §8 Phase 5). Routes are mounted
on a fresh FastAPI app with config patched, since main.py's own mount() ran at
import time with WHATSAPP_ENABLED unset. Network is blocked by conftest, so
every Graph API call is mocked.
"""

import hashlib
import hmac
import json
import logging
import threading

import config
import httpx
import ivr_sowing
import pytest
import whatsapp
from fastapi import FastAPI
from fastapi.testclient import TestClient

SECRET = "app-secret"
VERIFY = "verify-me"


@pytest.fixture(autouse=True)
def _channel(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(config, "WHATSAPP_APP_SECRET", SECRET)
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", VERIFY)
    monkeypatch.setattr(config, "WHATSAPP_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(config, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(config, "WHATSAPP_SENDER_RATE_PER_MIN", 6)
    whatsapp.reset()
    ivr_sowing._pending_whatsapp.clear()
    yield
    whatsapp.reset()
    ivr_sowing._pending_whatsapp.clear()


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _payload(*messages: dict, number_id: str = "123") -> dict:
    return {"object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"metadata": {"phone_number_id": number_id},
                                              "messages": list(messages)}}]}]}


def _text(body: str, mid: str = "m1", sender: str = "919876543210") -> dict:
    return {"from": sender, "id": mid, "type": "text", "text": {"body": body}}


def _msg(key: str, lang: str, **fields) -> str:
    return f"[{key}:{lang}]"


class _Sent:
    def __init__(self):
        self.out: list[tuple[str, str]] = []

    def __call__(self, to: str, body: str) -> bool:
        self.out.append((to, body))
        return True


def _ask_recorder(response: str = "It is sunny."):
    calls: list[dict] = []

    def ask(**kwargs):
        calls.append(kwargs)
        return {"response": response}

    return ask, calls


def _run(message: dict, ask=None, send=None):
    ask = ask or _ask_recorder()[0]
    send = send or _Sent()
    whatsapp.handle_message(message, ask, _msg, send_fn=send)
    return send


# --- webhook routes ---------------------------------------------------------

def _client(ask=None) -> tuple[TestClient, list]:
    app = FastAPI()
    ask_fn, calls = (ask, []) if ask else _ask_recorder()
    whatsapp.mount(app, ask_fn, _msg)
    return TestClient(app), calls


def test_handshake_echoes_challenge():
    client, _ = _client()
    r = client.get("/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"})
    assert r.status_code == 200 and r.text == "12345"


@pytest.mark.parametrize("params", [
    {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
    {"hub.mode": "unsubscribe", "hub.verify_token": VERIFY, "hub.challenge": "1"},
    {"hub.mode": "subscribe", "hub.verify_token": VERIFY},
    {},
])
def test_handshake_refuses_bad_requests(params):
    client, _ = _client()
    assert client.get("/whatsapp/webhook", params=params).status_code == 403


def test_inbound_rejects_missing_or_wrong_signature():
    client, calls = _client()
    body = json.dumps(_payload(_text("rain in Chennai"))).encode()
    assert client.post("/whatsapp/webhook", content=body).status_code == 403
    r = client.post("/whatsapp/webhook", content=body,
                    headers={"x-hub-signature-256": _sign(body, "other-secret")})
    assert r.status_code == 403
    assert calls == []


def test_inbound_signed_message_is_answered(monkeypatch):
    sent = _Sent()
    monkeypatch.setattr(whatsapp, "send_text", sent)
    client, calls = _client()
    body = json.dumps(_payload(_text("Will it rain in Chennai today?"))).encode()
    r = client.post("/whatsapp/webhook", content=body,
                    headers={"x-hub-signature-256": _sign(body)})
    assert r.status_code == 200
    assert sent.out == [("919876543210", "It is sunny.")]
    assert calls[0]["text"] == "Will it rain in Chennai today?" and calls[0]["lang"] == "en"


def test_inbound_garbage_body_is_ignored_after_signature_check():
    client, calls = _client()
    body = b"not json"
    r = client.post("/whatsapp/webhook", content=body,
                    headers={"x-hub-signature-256": _sign(body)})
    assert r.status_code == 200 and r.json() == {"status": "ignored"}
    assert calls == []


def test_mount_is_a_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_ENABLED", False)
    client, _ = _client()
    assert client.get("/whatsapp/webhook").status_code == 404


@pytest.mark.parametrize("name", ["WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN",
                                  "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"])
def test_mount_fails_closed_without_credentials(monkeypatch, name, caplog):
    monkeypatch.setattr(config, name, "")
    with caplog.at_level(logging.ERROR, logger="weathergpt.whatsapp"):
        client, _ = _client()
    assert client.get("/whatsapp/webhook").status_code == 404
    assert name in caplog.text


def test_messages_in_skips_receipts_and_junk():
    ours = {"phone_number_id": "123"}
    payload = {"entry": [
        {"changes": [{"value": {"metadata": ours,
                                "statuses": [{"id": "x", "status": "delivered"}]}}]},
        {"changes": [{"value": {"metadata": ours, "messages": [_text("hi"), "junk"]}}]},
        "junk", {"changes": "junk"}, {"changes": ["junk", {"value": "junk"}]},
    ]}
    assert [m["id"] for m in whatsapp.messages_in(payload, "123")] == ["m1"]
    assert whatsapp.messages_in(None, "123") == [] and whatsapp.messages_in([], "123") == []


@pytest.mark.parametrize("metadata", [{"phone_number_id": "999"}, {}, None, "123"])
def test_messages_in_keeps_only_messages_to_our_number(metadata):
    value = {"messages": [_text("rain in Chennai")]}
    if metadata is not None:
        value["metadata"] = metadata
    assert whatsapp.messages_in({"entry": [{"changes": [{"value": value}]}]}, "123") == []


def test_messages_in_without_our_number_finds_nothing():
    assert whatsapp.messages_in(_payload(_text("hi")), None) == []
    assert whatsapp.messages_in(_payload(_text("hi")), "") == []


def test_inbound_message_to_another_number_is_not_answered(monkeypatch):
    sent = _Sent()
    monkeypatch.setattr(whatsapp, "send_text", sent)
    client, calls = _client()
    body = json.dumps(_payload(_text("rain in Chennai"), number_id="999")).encode()
    r = client.post("/whatsapp/webhook", content=body,
                    headers={"x-hub-signature-256": _sign(body)})
    assert r.status_code == 200 and sent.out == [] and calls == []


# --- message handling -------------------------------------------------------

def test_text_question_goes_to_ask_in_english():
    ask, calls = _ask_recorder("Light rain, 28 degrees.")
    sent = _run(_text("Will it rain in Chennai today?"), ask=ask)
    assert sent.out == [("919876543210", "Light rain, 28 degrees.")]
    assert calls == [{"text": "Will it rain in Chennai today?", "lang": "en",
                      "city": None, "token": None}]


def test_script_picks_the_language():
    ask, calls = _ask_recorder()
    _run(_text("சென்னையில் மழை பெய்யுமா?", "a"), ask=ask)
    _run(_text("చెన్నైలో వర్షం పడుతుందా?", "b"), ask=ask)
    _run(_text("क्या आज चेन्नई में बारिश होगी?", "c"), ask=ask)
    assert [c["lang"] for c in calls] == ["ta", "te", "hi"]


def test_language_choice_sticks_and_covers_devanagari_and_latin():
    ask, calls = _ask_recorder()
    sent = _run(_text("marathi", "a"), ask=ask)
    assert sent.out[0][1] == whatsapp._LANG_SET["mr"] and calls == []
    _run(_text("पाऊस पडेल का चेन्नईत", "b"), ask=ask)
    _run(_text("rain in Chennai", "c"), ask=ask)
    assert [c["lang"] for c in calls] == ["mr", "mr"]


def test_language_choice_is_per_sender():
    ask, calls = _ask_recorder()
    _run(_text("3", "a", sender="911"), ask=ask)
    _run(_text("rain in Chennai", "b", sender="922"), ask=ask)
    _run(_text("rain in Chennai", "c", sender="911"), ask=ask)
    assert [c["lang"] for c in calls] == ["en", "ta"]


def test_language_choice_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    ask, calls = _ask_recorder()
    _run(_text("hindi", "a"), ask=ask)
    clock[0] += whatsapp._LANG_TTL_SECONDS + 1
    _run(_text("rain in Chennai", "b"), ask=ask)
    assert calls[0]["lang"] == "en"


def test_greeting_sends_help_without_asking():
    ask, calls = _ask_recorder()
    sent = _run(_text("Hello", "a"), ask=ask)
    assert sent.out[0][1] == whatsapp._HELP["en"] and calls == []


def test_duplicate_message_id_is_answered_once():
    ask, calls = _ask_recorder()
    sent = _Sent()
    _run(_text("rain in Chennai", "same"), ask=ask, send=sent)
    _run(_text("rain in Chennai", "same"), ask=ask, send=sent)
    assert len(sent.out) == 1 and len(calls) == 1


def test_dedupe_window_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(config, "WHATSAPP_SENDER_RATE_PER_MIN", 0)
    ask, calls = _ask_recorder()
    _run(_text("rain in Chennai", "same"), ask=ask)
    clock[0] += config.WHATSAPP_DEDUPE_TTL_SECONDS + 1
    _run(_text("rain in Chennai", "same"), ask=ask)
    assert len(calls) == 2


def test_sender_over_the_limit_is_dropped_then_recovers(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(config, "WHATSAPP_SENDER_RATE_PER_MIN", 2)
    ask, calls = _ask_recorder()
    for i in range(4):
        _run(_text("rain in Chennai", f"m{i}"), ask=ask)
    assert len(calls) == 2
    _run(_text("rain in Chennai", "other", sender="922"), ask=ask)
    assert len(calls) == 3  # another sender is unaffected
    clock[0] += 61
    _run(_text("rain in Chennai", "later"), ask=ask)
    assert len(calls) == 4


def test_ask_failure_still_gets_a_reply():
    def boom(**_):
        raise RuntimeError("llm down")

    sent = _run(_text("rain in Chennai"), ask=boom)
    assert sent.out == [("919876543210", "[no_data:en]")]


def test_ask_message_is_used_when_there_is_no_response():
    sent = _run(_text("rain in Chennai"), ask=lambda **_: {"message": "Which city?"})
    assert sent.out[0][1] == "Which city?"


def test_sowing_question_uses_the_advisory(monkeypatch):
    seen = {}

    def reply(key, text, lang, channel="ivr"):
        seen.update(key=key, text=text, lang=lang, channel=channel)
        return "Which crop?"

    monkeypatch.setattr(whatsapp.ivr_sowing, "reply", reply)
    ask, calls = _ask_recorder()
    sent = _run(_text("when should I sow", "a"), ask=ask)
    assert sent.out[0][1] == "Which crop?" and calls == []
    assert seen["key"] == "wa:" + whatsapp.sender_key("919876543210")
    assert seen["channel"] == "whatsapp"
    assert "919876543210" not in seen["key"]


@pytest.mark.parametrize("kind", ["audio", "image", "sticker", "interactive"])
def test_other_message_types_get_a_hint(kind):
    sent = _run({"from": "919876543210", "id": "x", "type": kind})
    assert sent.out == [("919876543210", whatsapp._UNSUPPORTED["en"])]


def test_malformed_messages_are_ignored_and_never_raise():
    ask, calls = _ask_recorder()
    for bad in ({}, {"from": 5, "id": "a"}, {"from": "9", "id": 7}, {"from": "", "id": "b"},
                {"from": "9", "id": "c", "type": "text", "text": "str"},
                {"from": "9", "id": "d", "type": "text", "text": {"body": "  "}}):
        _run(bad, ask=ask)
    assert calls == []


# --- place choice, shared location, sowing ask-back --------------------------

PUTTUR = [
    {"place_id": "gn:1259123", "label": "Puttūr, Andhra Pradesh", "district": "Tirupati",
     "state": "Andhra Pradesh"},
    {"place_id": "gn:1259124", "label": "Puttūr, Karnataka", "district": "Dakshina Kannada",
     "state": "Karnataka"},
]


def _scripted_ask(*outcomes: dict):
    """ask() returning `outcomes` in turn, recording every call's arguments."""
    calls: list[dict] = []
    queue = list(outcomes)

    def ask(**kwargs):
        calls.append(kwargs)
        return queue.pop(0) if queue else {"response": "It is sunny."}

    return ask, calls


AMBIGUOUS = {"message": "Which one did you mean?", "ambiguous": PUTTUR}


def test_ambiguous_place_lists_numbered_choices():
    ask, _ = _scripted_ask(AMBIGUOUS)
    sent = _run(_text("weather in Puttur", "a"), ask=ask)
    assert sent.out[0][1] == ("Which one did you mean?\n"
                              "1. Puttūr, Andhra Pradesh (Tirupati)\n"
                              "2. Puttūr, Karnataka (Dakshina Kannada)\n"
                              "Reply with the number.")


def test_number_reply_asks_again_for_the_chosen_place():
    ask, calls = _scripted_ask(AMBIGUOUS, {"response": "Puttur, Karnataka: light rain."})
    _run(_text("weather in Puttur", "a"), ask=ask)
    sent = _run(_text("2", "b"), ask=ask)
    assert sent.out == [("919876543210", "Puttur, Karnataka: light rain.")]
    assert calls[1] == {"text": "weather in Puttur", "lang": "en", "city": None,
                        "token": None, "place_id": "gn:1259124"}
    assert whatsapp._get(whatsapp._waiting, whatsapp.sender_key("919876543210")) is None


def test_number_reply_picks_a_place_not_a_language():
    ask, _ = _scripted_ask(AMBIGUOUS)
    _run(_text("weather in Puttur", "a"), ask=ask)
    _run(_text("2", "b"), ask=ask)
    assert whatsapp._get(whatsapp._lang_prefs, whatsapp.sender_key("919876543210")) is None


def test_choice_keeps_the_question_language():
    ask, calls = _scripted_ask({**AMBIGUOUS, "message": "किस जगह?"})
    sent = _run(_text("पुत्तूर में मौसम", "a"), ask=ask)
    assert sent.out[0][1].endswith(whatsapp._REPLY_WITH_NUMBER["hi"])
    _run(_text("1", "b"), ask=ask)
    assert calls[1]["lang"] == "hi" and calls[1]["place_id"] == "gn:1259123"


@pytest.mark.parametrize("reply", ["0", "3", "42"])
def test_out_of_range_number_asks_again_and_keeps_waiting(reply):
    ask, calls = _scripted_ask(AMBIGUOUS)
    _run(_text("weather in Puttur", "a"), ask=ask)
    sent = _run(_text(reply, "b"), ask=ask)
    assert sent.out == [("919876543210", "Reply with the number.")] and len(calls) == 1
    _run(_text("1", "c"), ask=ask)
    assert calls[1]["place_id"] == "gn:1259123"


def test_a_new_question_replaces_the_waiting_choice():
    ask, calls = _scripted_ask(AMBIGUOUS)
    _run(_text("weather in Puttur", "a"), ask=ask)
    _run(_text("rain in Chennai", "b"), ask=ask)
    sent = _run(_text("2", "c"), ask=ask)
    assert sent.out[0][1] == whatsapp._LANG_SET["hi"]  # a language again
    assert "place_id" not in calls[1] and len(calls) == 2


def test_waiting_choice_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    ask, _ = _scripted_ask(AMBIGUOUS)
    _run(_text("weather in Puttur", "a"), ask=ask)
    clock[0] += config.WHATSAPP_CONVERSATION_TTL_SECONDS + 1
    sent = _run(_text("2", "b"), ask=ask)
    assert sent.out[0][1] == whatsapp._LANG_SET["hi"]


def test_choice_list_skips_bad_entries_and_caps_at_nine():
    many = [{"place_id": f"gn:{i}", "label": f"Place {i}"} for i in range(12)]
    junk = ["x", {"label": "no id"}, {"place_id": "gn:1"}, {"place_id": 5, "label": "x"}]
    ask, _ = _scripted_ask({"message": "Which?", "ambiguous": junk + many})
    text = _run(_text("weather in X", "a"), ask=ask).out[0][1]
    assert "9. Place 8" in text and "10." not in text and "no id" not in text


def test_district_already_in_the_label_is_not_repeated():
    cands = [{"place_id": "gn:1", "label": "Madurai, Madurai", "district": "Madurai"},
             {"place_id": "gn:2", "label": "Madurai, Tamil Nadu", "district": ""}]
    ask, _ = _scripted_ask({"message": "Which?", "ambiguous": cands})
    text = _run(_text("weather in Madurai", "a"), ask=ask).out[0][1]
    assert "1. Madurai, Madurai\n2. Madurai, Tamil Nadu\n" in text


def _location(lat, lon, mid="loc"):
    return {"from": "919876543210", "id": mid, "type": "location",
            "location": {"latitude": lat, "longitude": lon, "name": "Home"}}


def test_shared_location_answers_the_waiting_question_snapped():
    ask, calls = _scripted_ask(
        {"message": "Which place? Name a town or city, or share your location.",
         "needs_location": True},
        {"response": "Here: clear skies."})
    _run(_text("will it rain here today", "a"), ask=ask)
    sent = _run(_location(13.0827, 80.2707), ask=ask)
    assert sent.out == [("919876543210", "Here: clear skies.")]
    assert calls[1] == {"text": "will it rain here today", "lang": "en", "city": None,
                        "token": None, "lat": 13.10, "lon": 80.25}


def test_shared_location_is_used_for_the_next_hour(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    ask, calls = _scripted_ask()
    sent = _run(_location(28.6139, 77.2090), ask=ask)
    assert sent.out[0][1] == whatsapp._HERE_SAVED["en"] and calls == []
    _run(_text("will it rain today", "a"), ask=ask)
    assert (calls[0]["lat"], calls[0]["lon"]) == (28.6, 77.2)
    clock[0] += config.WHATSAPP_LOCATION_TTL_SECONDS + 1
    _run(_text("will it rain today", "b"), ask=ask)
    assert "lat" not in calls[1]


def test_place_choice_does_not_send_the_shared_location_too():
    ask, calls = _scripted_ask(AMBIGUOUS)
    _run(_location(13.08, 80.27), ask=ask)
    _run(_text("weather in Puttur", "a"), ask=ask)
    _run(_text("1", "b"), ask=ask)
    assert calls[1]["place_id"] == "gn:1259123" and "lat" not in calls[1]


@pytest.mark.parametrize("location", [
    None, "13,80", {}, {"latitude": 13.0}, {"latitude": "13", "longitude": "80"},
    {"latitude": True, "longitude": 80.0}, {"latitude": float("nan"), "longitude": 80.0},
    {"latitude": 91.0, "longitude": 80.0}, {"latitude": 13.0, "longitude": 181.0},
])
def test_unusable_location_asks_again(location):
    ask, calls = _scripted_ask()
    msg = {"from": "919876543210", "id": "x", "type": "location", "location": location}
    sent = _run(msg, ask=ask)
    assert sent.out == [("919876543210", whatsapp._BAD_LOCATION["en"])] and calls == []


def test_location_is_never_logged(caplog):
    ask, _ = _scripted_ask({"message": "Which place?", "needs_location": True})
    with caplog.at_level(logging.DEBUG):
        _run(_text("will it rain here", "a"), ask=ask)
        _run(_location(13.0827, 80.2707), ask=ask)
    assert "13.08" not in caplog.text and "13.1" not in caplog.text


def test_sowing_ask_back_is_kept_in_the_whatsapp_table():
    ask, calls = _ask_recorder()
    sent = _run(_text("when should I sow groundnut", "a"), ask=ask)
    key = "wa:" + whatsapp.sender_key("919876543210")
    assert calls == [] and sent.out[0][1]  # asked back for the district, not /ask
    assert key in ivr_sowing._pending_whatsapp and key not in ivr_sowing._pending


def test_sowing_whatsapp_table_has_its_own_lifetime(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_CONVERSATION_TTL_SECONDS", 1234)
    monkeypatch.setattr(ivr_sowing.time, "monotonic", lambda: 0.0)
    ivr_sowing.reply("wa:k", "when should I sow groundnut", "en", channel="whatsapp")
    assert ivr_sowing._pending_whatsapp["wa:k"][0] == 1234


def test_sowing_rejects_an_unknown_channel():
    with pytest.raises(ValueError):
        ivr_sowing.reply("k", "when should I sow groundnut", "en", channel="sms")


# --- threads ----------------------------------------------------------------

def _hammer(fn, threads: int = 8) -> list[BaseException]:
    errors: list[BaseException] = []

    def worker(n):
        try:
            fn(n)
        except BaseException as exc:  # noqa: BLE001 - collected for the assert
            errors.append(exc)

    pool = [threading.Thread(target=worker, args=(n,)) for n in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    return errors


def test_dedupe_is_safe_across_threads():
    accepted = []

    def run(n):
        for i in range(3000):
            if whatsapp._first_time(f"m{i}"):  # every thread sends the same ids
                accepted.append(i)

    assert _hammer(run) == []
    assert sorted(accepted) == list(range(3000))  # each id exactly once


def test_sender_limit_is_exact_across_threads(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_SENDER_RATE_PER_MIN", 50)
    allowed = []

    def run(n):
        for _ in range(100):
            if whatsapp._within_sender_limit("same-sender"):
                allowed.append(1)

    assert _hammer(run) == []
    assert len(allowed) == 50


def test_state_tables_are_safe_across_threads():
    def run(n):
        for i in range(2000):
            key = f"k{n}-{i % 50}"
            whatsapp._put(whatsapp._here, key, 60, 1.0, 2.0)
            whatsapp._get(whatsapp._here, key)
            whatsapp._drop(whatsapp._here, key)

    assert _hammer(run) == []


def test_tables_stay_bounded(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_STATE_MAX", 10)
    for i in range(30):
        whatsapp._put(whatsapp._waiting, f"k{i}", 60, "location", "q", "en", None)
        whatsapp._first_time(f"m{i}")
        whatsapp._within_sender_limit(f"s{i}")
    assert len(whatsapp._waiting) == len(whatsapp._seen) == len(whatsapp._sender_hits) == 10
    assert "k29" in whatsapp._waiting and "s29" in whatsapp._sender_hits


def test_every_language_has_every_canned_string():
    for table in (whatsapp._HELP, whatsapp._LANG_SET, whatsapp._UNSUPPORTED,
                  whatsapp._REPLY_WITH_NUMBER, whatsapp._HERE_SAVED, whatsapp._BAD_LOCATION):
        assert set(table) == {"en", "hi", "ta", "te", "mr"}


def test_sender_key_is_not_the_number():
    key = whatsapp.sender_key("919876543210")
    assert "9876" not in key and len(key) == 16


# --- Graph API --------------------------------------------------------------

class _Resp:
    def __init__(self, status=200, payload=None, content=b""):
        self.status_code, self._payload, self.content = status, payload, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self):
        return self._payload

    def iter_bytes(self, chunk_size=65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_send_text_posts_to_the_graph_api(monkeypatch):
    seen = {}

    def post(url, **kw):
        seen.update(url=url, **kw)
        return _Resp()

    monkeypatch.setattr(httpx, "post", post)
    assert whatsapp.send_text("919876543210", "hello") is True
    assert seen["url"] == "https://graph.facebook.com/v21.0/123/messages"
    assert seen["headers"] == {"Authorization": "Bearer tok"}
    assert seen["json"] == {"messaging_product": "whatsapp", "to": "919876543210",
                            "type": "text", "text": {"preview_url": False, "body": "hello"}}


def test_send_text_truncates_and_swallows_failures(monkeypatch, caplog):
    seen = {}
    monkeypatch.setattr(httpx, "post", lambda url, **kw: seen.update(kw) or _Resp())
    whatsapp.send_text("9", "x" * 9000)
    assert len(seen["json"]["text"]["body"]) == whatsapp.MAX_REPLY_CHARS

    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(status=401))
    with caplog.at_level(logging.WARNING, logger="weathergpt.whatsapp"):
        assert whatsapp.send_text("919876543210", "hello") is False
    assert "401" in caplog.text and "919876543210" not in caplog.text
    assert "tok" not in caplog.text

    def down(url, **kw):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", down)
    assert whatsapp.send_text("9", "hello") is False


def test_rate_limit_rule_for_the_webhook():
    import limits

    assert limits._rule("/whatsapp/webhook") == (
        "whatsapp", config.WHATSAPP_GLOBAL_RATE_PER_MIN, False)


def test_handle_message_looks_up_send_text_at_call_time(monkeypatch):
    sent = _Sent()
    monkeypatch.setattr(whatsapp, "send_text", sent)
    whatsapp.handle_message(_text("rain in Chennai"), _ask_recorder()[0], _msg)
    assert sent.out == [("919876543210", "It is sunny.")]


# --- privacy fixes (2026-10-23 review) ----------------------------------------

def test_sender_key_is_an_hmac_with_the_app_secret(monkeypatch):
    expected = hmac.new(SECRET.encode(), b"919876543210", hashlib.sha256).hexdigest()[:16]
    assert whatsapp.sender_key("919876543210") == expected
    assert whatsapp.sender_key("919876543210") != (
        hashlib.sha256(b"919876543210").hexdigest()[:16])  # not a bare hash
    monkeypatch.setattr(config, "WHATSAPP_APP_SECRET", "another-secret")
    assert whatsapp.sender_key("919876543210") != expected


def test_expired_entries_are_dropped_on_the_next_write(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    whatsapp._put(whatsapp._here, "gone", 10, 13.1, 80.25)
    whatsapp._put(whatsapp._waiting, "gone", 10, "location", "q", "en", None)
    clock[0] += 11
    whatsapp._put(whatsapp._here, "other", 10, 1.0, 2.0)
    whatsapp._put(whatsapp._waiting, "other", 10, "location", "q", "en", None)
    assert "gone" not in whatsapp._here and "gone" not in whatsapp._waiting
    assert "other" in whatsapp._here and "other" in whatsapp._waiting


def test_idle_send_times_are_dropped(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(whatsapp, "_monotonic", lambda: clock[0])
    whatsapp._within_sender_limit("idle-sender")
    clock[0] += 61
    whatsapp._within_sender_limit("active-sender")
    assert "idle-sender" not in whatsapp._sender_hits
    assert "active-sender" in whatsapp._sender_hits


def test_marathi_greeting_gets_help():
    ask, calls = _ask_recorder()
    sent = _run(_text("नमस्कार", "a"), ask=ask)
    assert sent.out[0][1] == whatsapp._HELP["hi"] and calls == []  # Devanagari: Hindi first
    _run(_text("marathi", "b"), ask=ask)
    sent = _run(_text("नमस्कार", "c"), ask=ask)
    assert sent.out[0][1] == whatsapp._HELP["mr"]


def test_ivr_default_channel_leaves_the_whatsapp_table_alone():
    ivr_sowing._pending.clear()
    try:
        ivr_sowing.reply("CA-x", "when should I sow groundnut", "en")
        assert "CA-x" in ivr_sowing._pending and ivr_sowing._pending_whatsapp == {}
    finally:
        ivr_sowing._pending.clear()


def test_sowing_table_lookup_rejects_an_unknown_channel():
    with pytest.raises(ValueError):
        ivr_sowing._table("sms")


def test_expired_sowing_turns_are_dropped_on_the_next_write(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(ivr_sowing.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(config, "WHATSAPP_CONVERSATION_TTL_SECONDS", 10)
    ivr_sowing.reply("wa:old", "when should I sow groundnut", "en", channel="whatsapp")
    clock[0] = 11
    ivr_sowing.reply("wa:new", "when should I sow groundnut", "en", channel="whatsapp")
    assert "wa:old" not in ivr_sowing._pending_whatsapp
    assert "wa:new" in ivr_sowing._pending_whatsapp
