"""Verify GEMINI_API_KEY authenticates and pick a model.

    python services/orchestrator/verify_gemini.py

Step 1 lists the models the key can reach (filtered to `flash`); step 2 runs a
one-token generateContent smoke test. Prints redacted values only.

A standard AI Studio key looks like `AIza...`. An `AQ.` prefix is the shape of
a short-lived / ephemeral token — it may authenticate now and stop working
later, so re-run this at the start of each work session and on demo morning.
Exit codes: 0 verified, 2 auth rejected, 3 network/other.
"""

import sys
import time

import config
import httpx

PREFERRED = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-2.5-flash"]


def _headers(key: str) -> dict:
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def list_models(key: str) -> list[dict]:
    r = httpx.get(f"{config.GEMINI_BASE}/models", headers=_headers(key), timeout=15)
    r.raise_for_status()
    return r.json().get("models", [])


def smoke(key: str, model: str) -> tuple[float, str]:
    body = {"contents": [{"parts": [{"text": "Reply with the single word OK"}]}]}
    start = time.monotonic()
    r = httpx.post(f"{config.GEMINI_BASE}/models/{model}:generateContent",
                   headers=_headers(key), json=body, timeout=30)
    r.raise_for_status()
    elapsed = time.monotonic() - start
    parts = r.json()["candidates"][0]["content"]["parts"]
    return elapsed, "".join(p.get("text", "") for p in parts).strip()


def _pick(models: list[dict]) -> str | None:
    usable = {
        m["name"].split("/")[-1]
        for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
    }
    for name in PREFERRED:
        if name in usable:
            return name
    return next((n for n in sorted(usable) if "flash" in n), None)


def main() -> int:
    key = config.GEMINI_API_KEY
    print(f"key={config.redact(key)}  base={config.GEMINI_BASE}\n")
    if not key:
        print("RESULT: GEMINI KEY MISSING — set GEMINI_API_KEY in .env")
        return 2

    try:
        models = list_models(key)
    except httpx.HTTPStatusError as e:
        print(f"RESULT: GEMINI KEY REJECTED — {e.response.status_code} {e.response.text[:300]}")
        print("Fix: mint a standard AIza... key at https://aistudio.google.com/apikey")
        return 2
    except httpx.HTTPError as e:
        print(f"RESULT: NETWORK ERROR — {e}")
        return 3

    flash = [m for m in models if "flash" in m["name"]]
    print(f"{'model':<34}methods")
    for m in flash:
        print(f"{m['name'].split('/')[-1]:<34}{','.join(m.get('supportedGenerationMethods', []))}")

    model = _pick(models)
    if not model:
        print("\nRESULT: NO USABLE flash MODEL for this key")
        return 2

    try:
        elapsed, text = smoke(key, model)
    except httpx.HTTPError as e:
        print(f"\nRESULT: GEMINI KEY REJECTED — generateContent failed: {e}")
        return 2

    print(f"\nsmoke  model={model}  {elapsed:.2f}s  reply={text!r}")
    print(f"RESULT: GEMINI KEY AUTHENTICATES (model={model})")
    print(f"Set GEMINI_MODEL={model} in .env and .env.example.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
