"""A short-lived cache of finished advisory answers (plan.md §8 TFA-20, §11.4).

Many callers ask the same district question ("can I sow groundnut in Madurai",
"Chennai to Madurai tomorrow"), and each answer costs a model call. The answer
for one (kind, slots, lang) is the same until the facts behind it change, so it
is stored in Redis (intelligence_cache's connection and fail-open handling) and
served to the next caller.

**TTL.** Never longer than the hourly forecast behind it: the shortest
remaining life of the answer's hourly sections, as WIE-15 does. Then capped at
the shortest product TTL among the other live parts it may quote: current
conditions always (wind now), and METAR/TAF when an aviation section is
present. Those parts don't carry their retrieval time, so the cap bounds their
age at twice their TTL in the worst case, not exactly at one.

**Not stored:**
- an answer whose hourly sections aren't all live (a fixture or an outage
  replay, as in WIE-15);
- an answer where the agent was tried and failed (a template fallback after a
  429 shouldn't be pinned for an hour); with the agent off, the template is
  the normal answer and is stored;
- anything in WEATHER_MODE=fixtures, or while Redis is parked.

Slots are only ever values the slot parser produced (city keys, known days,
crops, modes), so a client can't fill Redis with made-up keys.
"""

from __future__ import annotations

import config
import intelligence_cache

from advisory.agent import AGENT_OFF, Advice

PREFIX = "weathergpt:advisory"


def key(kind: str, slots: dict, lang: str) -> str:
    parts = [f"{name}={value}" for name, value in sorted(slots.items())]
    return ":".join([PREFIX, kind, lang, *parts])


def ttl_seconds(advice: Advice) -> int:
    """How long `advice` may be served again; 0 when it must not be stored."""
    if advice.path == "template" and advice.fallback_reason != AGENT_OFF:
        return 0  # the agent failed: don't pin the fallback
    hourly = [s for s in advice.facts.sections if s.kind == "hourly"]
    if not hourly or not all(s.available and s.is_live for s in hourly):
        return 0
    ttl = min(intelligence_cache.remaining_seconds(s.data.get("retrieved_at")) for s in hourly)
    ttl = min(ttl, config.TTL_CURRENT_CONDITIONS)
    if any(s.kind == "aviation" and s.available for s in advice.facts.sections):
        ttl = min(ttl, config.TTL_METAR, config.TTL_TAF)
    return max(ttl, 0)


def get(cache_key: str) -> dict | None:
    return intelligence_cache.get(cache_key)


def put(cache_key: str, response: dict, advice: Advice) -> None:
    intelligence_cache.store(cache_key, response, ttl_seconds(advice))
