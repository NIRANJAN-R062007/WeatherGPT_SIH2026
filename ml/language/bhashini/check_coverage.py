"""Phase 0 coverage check: confirm Bhashini has ASR + TTS + translation models
for each of en/hi/ta/te/mr, and print which languages/tasks need to fall back
to self-hosted IndicTrans2/IndicConformer.

Run once BHASHINI_USER_ID / BHASHINI_ULCA_API_KEY are in .env:
    python ml/language/bhashini/check_coverage.py

For ASR/TTS this only resolves the pipeline (proves a serviceId/model exists
for that language) rather than running a full audio round trip — that's the
coverage question Phase 0 needs answered before anyone builds against a
language that has no model. A live translate() call is also run per language
pair since text round trips are cheap and give a real quality sample.
"""
from client import BhashiniError, get_pipeline, translate

LANGUAGES = ["en", "hi", "ta", "te", "mr"]


def check_task(task_type: str, lang: str, target: str | None = None):
    try:
        get_pipeline(task_type, lang, target)
        return "OK"
    except BhashiniError as e:
        return f"MISSING/ERROR: {e}"


def main():
    print(f"{'lang':<6}{'asr':<28}{'tts':<28}translation (en<->lang)")
    for lang in LANGUAGES:
        asr = check_task("asr", lang) if lang != "en" else "n/a (english ASR optional)"
        tts = check_task("tts", lang)

        if lang == "en":
            nmt = "n/a"
        else:
            try:
                hi_text = translate("Heavy rainfall expected tomorrow.", "en", lang)
                nmt = f"OK -> {hi_text[:40]}"
            except BhashiniError as e:
                nmt = f"MISSING/ERROR: {e}"

        print(f"{lang:<6}{asr:<28}{tts:<28}{nmt}")

    print(
        "\nAny MISSING/ERROR above -> route that language+task through the "
        "self-hosted IndicTrans2 (translation) / IndicConformer (ASR) fallback "
        "per plan.md R3."
    )


if __name__ == "__main__":
    main()
