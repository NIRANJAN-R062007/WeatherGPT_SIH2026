"""Bhashini ULCA integration for /ask: EN -> TA translation on top of Gemini
narration, plus ASR (speech-to-text for voice input) and TTS (text-to-speech
for answer playback) — plan.md §14 voice track.

Two-stage flow throughout: a config call resolves the task's pipeline
(serviceId), then a compute call runs it. Two credential shapes are handled:

- classic ULCA: config authed with userID + ulcaApiKey; the config response
  carries a per-call inferenceApiKey used on compute.
- Udyat (newer): config authed with ulcaApiKey alone; the config response has
  no inferenceApiKey, so compute uses the separately issued
  BHASHINI_INFERENCE_KEY as the Authorization header.

Any failure — no credentials, timeout, HTTP error, malformed response — returns
None so callers fall back (main.py's i18n template for translation, typed
input/silent playback for ASR/TTS), same safety pattern as narrate.py. Demo
keys are quota-limited: each task's pipeline config is cached per process
(translation globally since it's EN->TA only; ASR/TTS per language), so
steady state is one compute call per request.
"""

import array
import base64
import binascii
import logging
import struct

import config
import httpx

CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
COMPUTE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
PIPELINE_ID = "64392f96daac500b55c543cd"
TIMEOUT = 10.0
_LOG = logging.getLogger("weathergpt.bhashini")

_pipeline_cache: dict | None = None
_asr_pipeline_cache: dict[str, dict] = {}
_tts_pipeline_cache: dict[str, dict] = {}


def is_configured() -> bool:
    # OFFLINE_MODE (plan.md §8 Phase 6): no network for voice/translation at
    # all, so callers fall straight through to typed input / the i18n template.
    if config.OFFLINE_MODE:
        return False
    # ulcaApiKey is always required; then either a userID (classic, the config
    # call returns the inference key) or an Udyat inference key.
    return bool(config.BHASHINI_ULCA_API_KEY
                and (config.BHASHINI_USER_ID or config.BHASHINI_INFERENCE_KEY))


def cache_clear() -> None:
    global _pipeline_cache
    _pipeline_cache = None
    _asr_pipeline_cache.clear()
    _tts_pipeline_cache.clear()


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


def _get_asr_pipeline(lang: str) -> dict:
    """Resolve (and cache) the ASR pipeline for `lang`, one cache slot per language."""
    if lang in _asr_pipeline_cache:
        return _asr_pipeline_cache[lang]
    body = {
        "pipelineTasks": [{
            "taskType": "asr",
            "config": {"language": {"sourceLanguage": lang}},
        }],
        "pipelineRequestConfig": {"pipelineId": PIPELINE_ID},
    }
    resp = httpx.post(CONFIG_URL, json=body, headers=_config_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    pipeline = resp.json()
    _asr_pipeline_cache[lang] = pipeline
    return pipeline


def speech_to_text(audio_base64: str, lang: str, sampling_rate: int = 16000) -> str | None:
    """Base64 mono 16-bit PCM WAV -> transcript in `lang` via Bhashini ASR.
    None on no credentials, no audio, or any failure — caller falls back to
    typed input.
    """
    if not is_configured() or not audio_base64:
        return None
    try:
        pipeline = _get_asr_pipeline(lang)
        headers = _inference_headers(pipeline)
        task_config = pipeline["pipelineResponseConfig"][0]["config"][0]
        compute_url = (pipeline.get("pipelineInferenceAPIEndPoint") or {}).get("callbackUrl") \
            or COMPUTE_URL
        body = {
            "pipelineTasks": [{"taskType": "asr", "config": task_config}],
            "inputData": {
                "audio": [{"audioContent": audio_base64}],
                "config": {"audioFormat": "wav", "samplingRate": sampling_rate},
            },
        }
        resp = httpx.post(compute_url, json=body, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        transcript = resp.json()["pipelineResponse"][0]["output"][0]["source"]
        return transcript.strip() or None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        _LOG.warning("bhashini ASR failed (%s); voice input unavailable", exc)
        return None


def _wav_to_pcm16_base64(audio_b64: str) -> str:
    """Bhashini's TTS returns 32-bit float WAV — Chrome's <audio> decodes it
    "successfully" (play() resolves) but then never fires 'ended', hanging
    playback forever (confirmed: native players decode the same file fine in
    ~3s). Re-encode to 16-bit PCM WAV, which every browser handles, before
    handing audio to the frontend. 16-bit PCM input passes through unchanged;
    anything unparseable is returned as-is rather than dropped.
    """
    try:
        raw = base64.b64decode(audio_b64)
        if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
            return audio_b64

        pos, fmt, data = 12, None, None
        while pos + 8 <= len(raw):
            chunk_id = raw[pos:pos + 4]
            chunk_size = struct.unpack_from("<I", raw, pos + 4)[0]
            body_start = pos + 8
            if chunk_id == b"fmt ":
                fmt = struct.unpack_from("<HHIIHH", raw, body_start)
            elif chunk_id == b"data":
                data = raw[body_start:body_start + chunk_size]
            pos = body_start + chunk_size + (chunk_size % 2)  # chunks are word-aligned

        if fmt is None or data is None:
            return audio_b64

        audio_format, channels, sample_rate, _byte_rate, _block_align, bits_per_sample = fmt
        if audio_format == 1 and bits_per_sample == 16:
            return audio_b64  # already browser-safe

        if audio_format == 3 and bits_per_sample == 32:  # IEEE float
            floats = array.array("f")
            floats.frombytes(data[:len(data) - (len(data) % 4)])
            pcm = array.array("h", (max(-32768, min(32767, round(s * 32767))) for s in floats))
        elif audio_format == 1 and bits_per_sample == 8:  # unsigned 8-bit PCM
            pcm = array.array("h", ((b - 128) * 256 for b in data))
        elif audio_format == 1 and bits_per_sample == 24:  # 24-bit PCM, little-endian
            samples = []
            for i in range(0, len(data) - 2, 3):
                v = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
                if v & 0x800000:
                    v -= 0x1000000
                samples.append(max(-32768, min(32767, v >> 8)))
            pcm = array.array("h", samples)
        else:
            return audio_b64  # unrecognized format — hand back as-is

        pcm_bytes = pcm.tobytes()
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + len(pcm_bytes), b"WAVE",
            b"fmt ", 16, 1, channels, sample_rate,
            sample_rate * channels * 2, channels * 2, 16,
            b"data", len(pcm_bytes),
        )
        return base64.b64encode(header + pcm_bytes).decode("ascii")
    except (struct.error, binascii.Error, ValueError, IndexError) as exc:
        _LOG.warning("WAV re-encode to PCM16 failed (%s); using Bhashini's raw audio as-is", exc)
        return audio_b64


def _get_tts_pipeline(lang: str) -> dict:
    """Resolve (and cache) the TTS pipeline for `lang`, one cache slot per language."""
    if lang in _tts_pipeline_cache:
        return _tts_pipeline_cache[lang]
    body = {
        "pipelineTasks": [{
            "taskType": "tts",
            "config": {"language": {"sourceLanguage": lang}},
        }],
        "pipelineRequestConfig": {"pipelineId": PIPELINE_ID},
    }
    resp = httpx.post(CONFIG_URL, json=body, headers=_config_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    pipeline = resp.json()
    _tts_pipeline_cache[lang] = pipeline
    return pipeline


def text_to_speech(text: str, lang: str) -> str | None:
    """`text` (already in `lang`) -> base64 WAV audio via Bhashini TTS. None on
    no credentials, no text, or any failure — caller skips playback.
    """
    if not is_configured() or not text:
        return None
    try:
        pipeline = _get_tts_pipeline(lang)
        headers = _inference_headers(pipeline)
        # The config response lists supportedVoices but picks none; compute 500s
        # without an explicit gender choice.
        task_config = {**pipeline["pipelineResponseConfig"][0]["config"][0], "gender": "female"}
        compute_url = (pipeline.get("pipelineInferenceAPIEndPoint") or {}).get("callbackUrl") \
            or COMPUTE_URL
        body = {
            "pipelineTasks": [{"taskType": "tts", "config": task_config}],
            "inputData": {"input": [{"source": text}]},
        }
        resp = httpx.post(compute_url, json=body, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        audio_b64 = resp.json()["pipelineResponse"][0]["audio"][0]["audioContent"]
        if not audio_b64:
            return None
        return _wav_to_pcm16_base64(audio_b64)
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        _LOG.warning("bhashini TTS failed (%s); voice playback unavailable", exc)
        return None
