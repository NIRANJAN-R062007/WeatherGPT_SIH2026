"""Persona-aware advisories (plan.md §8 Phase 4, P1 item 9): "farmer /
fisherman / aviation / city-official — same data, different framing, driven
by a user profile flag."

Split two ways in plan.md, deliberately: **this file plus the plumbing
through main.py/narrate.py is the profile-flag path — Niranjan's item**.
The actual persona-specific wording (what a farmer vs. a fisherman advisory
should say, tuned and QA'd) is Mahesh's separate "Persona prompt/template
logic" item. `_HINTS` below is a first-pass, functional-but-basic default
set so the plumbing is real and testable end to end rather than an inert
no-op — treat it as a starting point Mahesh's narration-layer pass replaces
or extends, not a finished product.

Narration-layer only, per plan.md: a persona changes *framing*, never the
facts. The hint text below is injected into the English prompt build_prompt()
sends the LLM (narrate.py's PERSONA_BLOCK), same guardrail as always checks
every number in the output against the raw facts afterward — a persona
cannot make the LLM say a number that isn't there, only talk about the
existing numbers differently. It has no effect on the i18n template fallback
path (narrate.py's LLM chain is the only place persona framing can apply —
the fallback template is generic by design).
"""

DEFAULT = "general"

PERSONAS = frozenset({DEFAULT, "farmer", "fisherman", "aviation", "city_official"})

# English-only: these feed the pre-translation prompt (narrate.py's pipeline
# always narrates in English first, then Bhashini translates — see
# narrate.narrate()'s docstring), so there is exactly one copy, not five.
_HINTS: dict[str, str] = {
    "farmer": (
        "The reader is a farmer. Where relevant, note whether conditions favor "
        "or disfavor field work like spraying or harvesting — using only the "
        "given facts, never inventing an agricultural detail not present."
    ),
    "fisherman": (
        "The reader is a fisherman going out to sea. Where relevant, note wind "
        "and rain conditions as they affect going out — using only the given "
        "facts, never inventing a marine detail (wave height, sea state) not "
        "present."
    ),
    "aviation": (
        "The reader is a pilot or aviation ground staff. Where relevant, note "
        "wind and visibility-affecting conditions in the given facts; never "
        "invent an aviation-specific figure (ceiling, visibility distance) "
        "that isn't present."
    ),
    "city_official": (
        "The reader is a city/disaster-management official. Be direct and "
        "operational; where relevant, note conditions that would affect public "
        "safety or infrastructure, using only the given facts."
    ),
}


def is_valid(value: str | None) -> bool:
    return value in PERSONAS


def hint(persona: str) -> str:
    """The English prompt-hint text for `persona`, or "" for "general"/unknown
    (unknown shouldn't reach here — main.py validates against PERSONAS first
    — but this stays a safe no-op rather than raising, same defensiveness as
    narrate.py's other optional prompt fragments)."""
    return _HINTS.get(persona, "")
