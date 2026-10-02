"""WIE-7: persona-aware framing over the same deterministic window (WIE-3).

This module never scores an hour or picks a window itself — it only maps a
persona to an advisory label and, through rules.py, to the activity
find_best_window() scores hours against. "farm" (farmer), "travel"
(traveller) and "outdoor" (general, city_official) share the exact same
Thresholds in rules.py today, so the window's numbers — start, end, average
temperature, max rain chance, max wind — are identical across every persona
that gets one, for the same facts. plan.md's WIE-7 done-when is exactly
this: "farmer, traveller and general give different framing from identical
facts in tests, with identical numbers." Only the label differs; any
further wording is the caller's job, same as every other deterministic
/intelligence/* route (plan.md §2 principle 7 — no LLM here at all).

fisherman and aviation get no window verdict (R17): the facts are a city
forecast with no sea state or aerodrome data to back a go/no-go
recommendation for either, exactly as persona.py's narration hints already
say. `wants_window()` is False for both, and callers are expected to fall
back to reporting the plain hourly forecast instead — this module hands
back a short, static caveat for that case so a caller doesn't have to
duplicate persona.py's fisherman/aviation wording. The caveat is plain,
non-LLM text (never "safe"/"unsafe", never claims a warning is in force),
not persona.hint()'s LLM prompt text, which is shaped for a narration
prompt and always ends in the shared _RULES clause.
"""

from .window_analyzer import find_best_window

# Advisory label per persona. Only "farm", "travel" and "outdoor" are named
# in plan.md's WIE-7 line ("per-persona rule weights and an advisory label
# (farm / travel / outdoor)") and its feature-table example (farmer: field
# work; traveller: travel; general: outdoor walk) — city_official isn't
# mentioned there, and isn't in the no-window list either (unlike fisherman
# and aviation, a city-official's facts are still a plain city forecast, not
# a sea state or aerodrome one), so it defaults to the same "outdoor" label
# as general rather than inventing an unspecified fourth one.
LABELS: dict[str, str | None] = {
    "general": "outdoor",
    "farmer": "farm",
    "traveller": "travel",
    "city_official": "outdoor",
    "fisherman": None,
    "aviation": None,
}

_ACTIVITY_FOR_LABEL = {"outdoor": "outdoor", "farm": "farm", "travel": "travel"}

# Short, static, non-LLM caveats for the two personas with no window verdict
# — the same facts persona.py's hints already state, kept to one sentence
# since nothing here is validated by the numeric guardrail (there is no LLM
# step on this path to validate).
CAVEATS: dict[str, str] = {
    "fisherman": (
        "This is a city forecast, not sea conditions — always check the "
        "official IMD fishermen warning before going out."
    ),
    "aviation": (
        "This is a city forecast, not an airport observation — it has no "
        "visibility, cloud base or runway data."
    ),
}


def wants_window(persona: str) -> bool:
    """False for fisherman/aviation (R17): no sea state or aerodrome data to
    back a window recommendation for either. True for every other persona
    in persona.PERSONAS, including an unrecognised one — callers validate
    `persona` against persona.PERSONAS before reaching this module."""
    return LABELS.get(persona, "outdoor") is not None


def advise(hours: list[dict], persona: str) -> dict:
    """The advisory for `persona` from `hours` (weather_data.hourly_facts()'s
    `hours` list, already time-ordered).

    `label`/`window` for a window persona (e.g. farmer -> {"label": "farm",
    "window": {...} or None for "no suitable window"}); `caveat` for
    fisherman/aviation instead (`label` and `window` both None) — the
    caller is expected to report the plain `hours` itself alongside it,
    since this module only ever returns the advisory, never the facts.
    """
    label = LABELS.get(persona, "outdoor")
    if label is None:
        return {"label": None, "window": None, "caveat": CAVEATS[persona]}
    activity = _ACTIVITY_FOR_LABEL[label]
    return {"label": label, "window": find_best_window(hours, activity), "caveat": None}
