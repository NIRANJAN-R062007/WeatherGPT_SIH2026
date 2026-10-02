"""TFA-5: the JSON shape a travel or farming answer must have.

The model reads an `AdvisoryFacts` (facts.py) and a rubric and returns this and
nothing else (plan.md §11.6/§11.7):

    {
      "verdict": "go" | "caution" | "avoid"          # travel
                 "suitable" | "not_suitable"         # farming
                 "not_available",                    # either: the facts don't cover it
      "pros":    ["short sentence quoting the facts", ...],
      "cons":    ["...", ...],
      "window":  {"start_local": "08:00", "end_local": "11:00"} | null,
      "cites":   ["origin.current.temp_c", ...]       # optional: fact paths relied on
    }

The shape is strict on purpose: every key outside this list is rejected, so no
free-text field exists for an uncited claim to hide in. Checking *what the
text says* against the facts is `guardrail.check_advisory()`; this module only
says whether the output has the right shape.
"""

from __future__ import annotations

import json
import re

NOT_AVAILABLE = "not_available"

# Per feature. TFA-7 (travel rule table) and TFA-11 (farming) own the meaning of
# these; the farming words avoid "sow now" / a safety claim (§11.7, R17).
VERDICTS: dict[str, tuple[str, ...]] = {
    "travel": ("go", "caution", "avoid", NOT_AVAILABLE),
    "farming": ("suitable", "not_suitable", NOT_AVAILABLE),
}

KEYS = frozenset({"verdict", "pros", "cons", "window", "cites"})
REQUIRED = ("verdict", "pros", "cons")
MAX_ITEMS = 8
MAX_ITEM_CHARS = 300

_HHMM = re.compile(r"(\d{1,2}):(\d{2})")
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def parse(text: str) -> dict | None:
    """The JSON object in a model's reply (a ```json fence is tolerated), or
    None if it is not a JSON object."""
    if not isinstance(text, str):
        return None
    m = _FENCE.match(text)
    try:
        value = json.loads(m.group(1) if m else text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def minutes(value) -> int | None:
    """"HH:MM" -> minutes since midnight, or None if it isn't a valid time."""
    if not isinstance(value, str):
        return None
    m = _HHMM.fullmatch(value)
    if m is None or int(m[1]) > 23 or int(m[2]) > 59:
        return None
    return int(m[1]) * 60 + int(m[2])


def window_bounds(window) -> tuple[int, int] | None:
    """`(start, end)` minutes of a well-formed window dict, else None."""
    if not isinstance(window, dict) or set(window) != {"start_local", "end_local"}:
        return None
    start, end = minutes(window["start_local"]), minutes(window["end_local"])
    if start is None or end is None or start > end:
        return None
    return start, end


def validate(output, kind: str) -> list[str]:
    """Why `output` is not a valid `kind` answer; empty when it is."""
    if not isinstance(output, dict):
        return ["output is not a JSON object"]
    if kind not in VERDICTS:
        return [f"unknown advisory kind {kind!r}"]

    problems: list[str] = []
    for key in sorted(set(output) - KEYS):
        problems.append(f"unexpected key {key!r}")
    for key in REQUIRED:
        if key not in output:
            problems.append(f"missing key {key!r}")

    verdict = output.get("verdict")
    if "verdict" in output and verdict not in VERDICTS[kind]:
        problems.append(f"verdict {verdict!r} is not one of {list(VERDICTS[kind])}")

    for key in ("pros", "cons", "cites"):
        if key not in output:
            continue
        items = output[key]
        if not isinstance(items, list):
            problems.append(f"{key} is not a list")
            continue
        if len(items) > MAX_ITEMS:
            problems.append(f"{key} has more than {MAX_ITEMS} items")
        for i, item in enumerate(items):
            if not isinstance(item, str) or not item.strip():
                problems.append(f"{key}[{i}] is not a non-empty string")
            elif len(item) > MAX_ITEM_CHARS:
                problems.append(f"{key}[{i}] is longer than {MAX_ITEM_CHARS} characters")

    window = output.get("window")
    if window is not None and window_bounds(window) is None:
        problems.append("window must be null or {start_local, end_local} as HH:MM, start <= end")
    return problems
