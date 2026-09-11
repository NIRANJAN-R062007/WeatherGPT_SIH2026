"""translate_to_tamil(): returns the translated string on success, None on
anything else, and never raises. Network is blocked by conftest, so every
"success" path here mocks httpx.post directly.
"""

import bhashini
import config
import httpx
import pytest


def _pipeline_response():
    return {
        "pipelineInferenceAPIEndPoint": {
            "inferenceApiKey": {"name": "Authorization", "value": "Bearer xyz"},
        },
        "pipelineResponseConfig": [{"config": [{"serviceId": "ai4bharat/x"}]}],
    }


def _compute_response(text: str):
    return {"pipelineResponse": [{"output": [{"target": text}]}]}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_no_credentials_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", None)
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", None)
    assert bhashini.translate_to_tamil("hello") is None


def test_empty_text_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    assert bhashini.translate_to_tamil("") is None


def test_happy_path(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    calls = []

    def _post(url, **kw):
        calls.append(url)
        if url == bhashini.CONFIG_URL:
            return _Resp(_pipeline_response())
        return _Resp(_compute_response("சென்னை: 28°C."))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.translate_to_tamil("Chennai: 28°C.") == "சென்னை: 28°C."
    assert calls == [bhashini.CONFIG_URL, bhashini.COMPUTE_URL]


def test_pipeline_is_cached_across_calls(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    config_calls = []

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            config_calls.append(1)
            return _Resp(_pipeline_response())
        return _Resp(_compute_response("x"))

    monkeypatch.setattr(httpx, "post", _post)
    bhashini.translate_to_tamil("a")
    bhashini.translate_to_tamil("b")
    assert len(config_calls) == 1


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("t"), httpx.ConnectError("c")])
def test_http_error_returns_none(monkeypatch, caplog, exc):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(exc))
    with caplog.at_level("WARNING"):
        assert bhashini.translate_to_tamil("hello") is None
    assert any("bhashini translation failed" in r.message for r in caplog.records)


def test_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp({"unexpected": True}))
    assert bhashini.translate_to_tamil("hello") is None


def test_empty_target_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            return _Resp(_pipeline_response())
        return _Resp(_compute_response(""))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.translate_to_tamil("hello") is None
