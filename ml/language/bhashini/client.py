"""Bhashini ULCA client: pipeline config + compute calls for ASR, translation, TTS.

Two-stage flow (per bhashini.gitbook.io/bhashini-apis):
  1. Config call -> meity-auth.ulcacontrib.org, authed with userID + ulcaApiKey,
     returns a per-call inferenceApiKey + the compute endpoint + serviceId per task.
  2. Compute call -> dhruva-api.bhashini.gov.in, authed with that inferenceApiKey.

Credentials come from env: BHASHINI_USER_ID, BHASHINI_ULCA_API_KEY.
"""
import os

import requests

CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
COMPUTE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

USER_ID = os.getenv("BHASHINI_USER_ID")
ULCA_API_KEY = os.getenv("BHASHINI_ULCA_API_KEY")


class BhashiniError(RuntimeError):
    pass


def _config_headers():
    if not USER_ID or not ULCA_API_KEY:
        raise BhashiniError("BHASHINI_USER_ID / BHASHINI_ULCA_API_KEY not set in environment")
    return {"userID": USER_ID, "ulcaApiKey": ULCA_API_KEY, "Content-Type": "application/json"}


def get_pipeline(task_type: str, source_language: str, target_language: str | None = None):
    """Resolve a serviceId + inference key + compute endpoint for one task.

    task_type: "asr" | "translation" | "tts"
    """
    language = {"sourceLanguage": source_language}
    if target_language:
        language["targetLanguage"] = target_language

    body = {
        "pipelineTasks": [{"taskType": task_type, "config": {"language": language}}],
        "pipelineRequestConfig": {"pipelineId": "64392f96daac500b55c543cd"},
    }
    resp = requests.post(CONFIG_URL, json=body, headers=_config_headers(), timeout=15)
    if resp.status_code != 200:
        raise BhashiniError(f"config call failed [{resp.status_code}]: {resp.text}")
    return resp.json()


def compute(task_type: str, pipeline_response: dict, input_data: dict):
    """Run the actual ASR/translation/TTS inference using a resolved pipeline config."""
    inference_key = pipeline_response["pipelineInferenceAPIEndPoint"]["inferenceApiKey"]
    task_config = pipeline_response["pipelineResponseConfig"][0]["config"][0]

    body = {
        "pipelineTasks": [{"taskType": task_type, "config": task_config}],
        "inputData": input_data,
    }
    headers = {
        inference_key["name"]: inference_key["value"],
        "Content-Type": "application/json",
    }
    resp = requests.post(COMPUTE_URL, json=body, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise BhashiniError(f"compute call failed [{resp.status_code}]: {resp.text}")
    return resp.json()


def translate(text: str, source_language: str, target_language: str) -> str:
    pipeline = get_pipeline("translation", source_language, target_language)
    result = compute(
        "translation",
        pipeline,
        {"input": [{"source": text}]},
    )
    return result["pipelineResponse"][0]["output"][0]["target"]
