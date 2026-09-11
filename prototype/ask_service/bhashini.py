"""Bhashini ULCA translation for /ask: EN -> TA on top of Gemini narration.

Two-stage flow: a config call resolves the translation pipeline (serviceId),
then a compute call runs the translation. Two credential shapes are handled:

- classic ULCA: config authed with userID + ulcaApiKey; the config response
  carries a per-call inferenceApiKey used on compute.
- Udyat (newer): config authed with ulcaApiKey alone; the config response has
  no inferenceApiKey, so compute uses the separately issued
  BHASHINI_INFERENCE_KEY as the Authorization header.

Any failure — no credentials, timeout, HTTP error, malformed response — returns
None so main.py falls back to the hand-written i18n template, same safety
pattern as narrate.py. Demo keys are quota-limited: the pipeline config is
cached per process, so steady state is one compute call per Tamil answer.
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
    # ulcaApiKey is always required; then either a userID (classic, the config
    # call returns the inference key) or an Udyat inference key.
    return bool(config.BHASHINI_ULCA_API_KEY
                and (config.BHASHINI_USER_ID or config.BHASHINI_INFERENCE_KEY))


def cache_clear() -> None:
    global _pipeline_cache
    _pipeline_cache = None


def _config_headers() -> dict:
    headers = {"ulcaApiKey": config.BHASHINI_ULCA_API_KEY, "Content-Type": "application/json"}
    if config.BHASHINI_USER_ID:
        headers["userID"] = config.BHASHINI_USER_ID
    return headers


def _inference_headers(pipeline: dict) -> dict:
    """Per-call key from the config response (classic), else the Udyat key."""
    endpoint = pipeline.get("pipelineInferenceAPIEndPoint") or {}
    key = endpoint.get("inferenceApiKey")
    if key and key.get("name") and key.get("value"):
        return {key["name"]: key["value"], "Content-Type": "application/json"}
    if config.BHASHINI_INFERENCE_KEY:
        return {"Authorization": config.BHASHINI_INFERENCE_KEY, "Content-Type": "application/json"}
    raise KeyError("no inference key: config response had none and BHASHINI_INFERENCE_KEY unset")


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
        headers = _inference_headers(pipeline)
        task_config = pipeline["pipelineResponseConfig"][0]["config"][0]
        compute_url = (pipeline.get("pipelineInferenceAPIEndPoint") or {}).get("callbackUrl") \
            or COMPUTE_URL
        body = {
            "pipelineTasks": [{"taskType": "translation", "config": task_config}],
            "inputData": {"input": [{"source": text}]},
        }
        resp = httpx.post(compute_url, json=body, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        target = resp.json()["pipelineResponse"][0]["output"][0]["target"]
        return target.strip() or None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        _LOG.warning("bhashini translation failed (%s); falling back to template", exc)
        return None
