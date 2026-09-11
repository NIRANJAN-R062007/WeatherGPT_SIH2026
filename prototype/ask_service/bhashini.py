"""Bhashini ULCA translation for /ask: EN -> TA on top of Gemini narration.

Two-stage ULCA flow: a config call (authed with userID + ulcaApiKey) resolves
the translation pipeline and a per-call inference key, then a compute call
(authed with that inference key) runs the actual translation. Any failure —
no credentials, timeout, HTTP error, malformed response — returns None so
main.py falls back to the hand-written i18n template, same safety pattern as
narrate.py.

Credentials: BHASHINI_USER_ID, BHASHINI_ULCA_API_KEY (see .env.example).
"""

import logging

import config
import httpx

CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
COMPUTE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
PIPELINE_ID = "64392f96daac500b55c543cd"
TIMEOUT = 10.0
_LOG = logging.getLogger("weathergpt.bhashini")

_pipeline_cache: dict | None = None


def is_configured() -> bool:
    return bool(config.BHASHINI_USER_ID and config.BHASHINI_ULCA_API_KEY)


def cache_clear() -> None:
    global _pipeline_cache
    _pipeline_cache = None


def _config_headers() -> dict:
    return {
        "userID": config.BHASHINI_USER_ID,
        "ulcaApiKey": config.BHASHINI_ULCA_API_KEY,
        "Content-Type": "application/json",
    }


def _get_pipeline() -> dict:
    """Resolve (and cache) the EN->TA translation pipeline for this process."""
    global _pipeline_cache
    if _pipeline_cache is not None:
        return _pipeline_cache
    body = {
        "pipelineTasks": [{
            "taskType": "translation",
            "config": {"language": {"sourceLanguage": "en", "targetLanguage": "ta"}},
        }],
        "pipelineRequestConfig": {"pipelineId": PIPELINE_ID},
    }
    resp = httpx.post(CONFIG_URL, json=body, headers=_config_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    _pipeline_cache = resp.json()
    return _pipeline_cache


def translate_to_tamil(text: str) -> str | None:
    """EN -> TA via Bhashini. None on no credentials, no text, or any failure."""
    if not is_configured() or not text:
        return None
    try:
        pipeline = _get_pipeline()
        inference_key = pipeline["pipelineInferenceAPIEndPoint"]["inferenceApiKey"]
        task_config = pipeline["pipelineResponseConfig"][0]["config"][0]
        body = {
            "pipelineTasks": [{"taskType": "translation", "config": task_config}],
            "inputData": {"input": [{"source": text}]},
        }
        headers = {
            inference_key["name"]: inference_key["value"],
            "Content-Type": "application/json",
        }
        resp = httpx.post(COMPUTE_URL, json=body, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        target = resp.json()["pipelineResponse"][0]["output"][0]["target"]
        return target.strip() or None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        _LOG.warning("bhashini translation failed (%s); falling back to template", exc)
        return None
