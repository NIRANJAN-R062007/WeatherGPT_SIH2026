"""The Strands agent behind the travel and sowing advisories (plan.md §11.2a, TFA-17).

    slots (resolved, TFA-3)
      -> core facts, collected before any model call (facts.py: no round trips)
      -> agent (Gemini, then Groq): reads the facts, may call a few fact tools, returns JSON
      -> hard override (rubric.hard_override): a red warning, a thunderstorm METAR or a
         mode's avoid-level wind is "avoid"
      -> guardrail.check_advisory: nothing outside the facts
      -> on any failure: the rule-based template answer (template.py), no model

The agent adds judgement and the choice of extra facts; it adds no facts of its own.
Every fact it can fetch comes from the same gatherers as the core ones, is recorded in
the same `AdvisoryFacts` the guardrail checks, and is restricted to the roles and days
the slots already name, so the model cannot send the tools anywhere the user did not ask.

Latency design (plan.md §11.2a): core facts first so the usual answer is one model call;
a tool-call cap and a wall-clock budget; one attempt per provider (Strands' default retry
is six attempts with a 4 s backoff, which on a Gemini 503 would spend the whole budget
before Groq is tried); an agent that is offline, disabled or out of time never blocks the
template answer.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable

import cities
import config
import guardrail
from weather_intelligence.window_analyzer import find_best_window

from advisory import facts as facts_module
from advisory import prompt, schema, template
from advisory import slots as slots_module
from advisory.facts import AdvisoryFacts, FactSection

_LOG = logging.getLogger("weathergpt.advisory")

COLLECTORS = {
    "travel": facts_module.TravelFactsCollector(),
    "farming": facts_module.FarmingFactsCollector(),
}
DAYS = slots_module.DAYS
MAX_OUTPUT_TOKENS = 700

Fetch = Callable[[str, str, str], FactSection]  # (role, kind, day) -> the section


class AgentError(Exception):
    """The agent could not give a usable reply (provider error, timeout, no JSON)."""


@dataclass
class Advice:
    kind: str
    answer: dict
    facts: AdvisoryFacts
    path: str                       # "agent:gemini" | "agent:groq" | "template"
    fallback_reason: str | None     # why the agent path was not used, if it wasn't
    tool_calls: int
    latency_s: float


# --- the fact tools ------------------------------------------------------------------


def _roles(kind: str, slots: dict) -> dict[str, str | None]:
    """role -> the city key the slots name for it (None if it does not resolve)."""
    if kind == "travel":
        return {r: cities.resolve(slots.get(r)) for r in ("origin", "destination")}
    return {"location": cities.resolve(slots.get("district"))}


def live_fetch(kind: str, slots: dict) -> Fetch:
    """The production fetch: the same gatherers the core collectors use."""
    roles = _roles(kind, slots)
    crop = (facts_module.crop_entry(slots.get("crop") or "",
                                    slots.get("region") or slots.get("district") or "")
            if kind == "farming" else None)

    def fetch(role: str, what: str, day: str) -> FactSection:
        city = roles.get(role)
        if city is None:
            return facts_module._unavailable(role, what, f"no city for role {role!r}")
        if what == "forecast":
            return facts_module.daily_forecast(role, city, day)
        if what == "hourly":
            return facts_module.hourly_forecast(role, city, day)
        if what == "rain":
            return facts_module.rain_so_far(role, city)
        if what == "aviation":
            return facts_module.aviation_reports(role, city)
        if what == "window":
            hourly = facts_module.hourly_forecast(role, city, day)
            if not hourly.available:
                return facts_module._unavailable(role, "window", hourly.reason or "no hourly")
            if kind == "farming":  # the crop's own thresholds (TFA-11), never generic ones
                window = facts_module.sowing_window(crop, hourly)
                return replace(window, role=role)
            found = find_best_window(hourly.data["hours"], "travel")
            if found is None:
                return facts_module._unavailable(role, "window", "no suitable window")
            data = {k: found[k] for k in ("start_local", "end_local", "avg_temp_c",
                                          "max_rain_probability_pct", "max_wind_kmh")}
            data.update(source=hourly.source, is_live=hourly.is_live)
            return FactSection(role, "window", True, data, source=hourly.source,
                               is_live=hourly.is_live)
        return facts_module._unavailable(role, what, "unknown fact")

    return fetch


def no_fetch(role: str, what: str, day: str) -> FactSection:
    """A fetch with nothing to add, for runs whose facts are pinned (the eval harness):
    the tools then only return what the core facts already hold."""
    return facts_module._unavailable(role, what, "not available in this run")


class Toolbox:
    """The tools one agent run may call. They record what they fetch into `facts`
    (so the guardrail sees it), count against a cap, and stop once cancelled."""

    def __init__(self, facts: AdvisoryFacts, fetch: Fetch, max_calls: int):
        self.facts = facts
        self.fetch = fetch
        self.max_calls = max_calls
        self.calls = 0
        self.cancelled = False
        self._lock = threading.Lock()

    def _key(self, what: str, day: str) -> str:
        """The section kind a fetch is stored under. The core sections are the ones the
        verdict rests on, so a tool call never lands on their key unless it asks for the
        same thing: another day is stored as `forecast_tomorrow`, not over `forecast`."""
        if what in ("rain", "aviation"):
            return what
        farming = self.facts.kind == "farming"
        core_day = "today" if farming else self.facts.subject.get("day", "today")
        if what == "forecast" and farming:
            return f"forecast_{day}"  # the core farming forecast is the multi-day one
        return what if day == core_day else f"{what}_{day}"

    def _run(self, role: str, what: str, day: str = "today") -> str:
        with self._lock:
            if self.cancelled:
                return json.dumps({"error": "out of time; answer from the facts you have"})
            if self.calls >= self.max_calls:
                return json.dumps({"error": "tool budget reached; answer from the facts you have"})
            self.calls += 1
        if day not in DAYS:
            return json.dumps({"error": f"day must be one of {list(DAYS)}"})
        if role not in self.roles():
            return json.dumps({"error": f"role must be one of {self.roles()}"})
        key = self._key(what, day)
        have = self.facts.section(role, key)
        if have is not None and have.available:
            return json.dumps(prompt.slim(have.data), ensure_ascii=False, separators=(",", ":"))
        section = replace(self.fetch(role, what, day), kind=key)
        with self._lock:
            for i, old in enumerate(self.facts.sections):
                if (old.role, old.kind) == (role, key):
                    self.facts.sections[i] = section
                    break
            else:
                self.facts.sections.append(section)
        if not section.available:
            return json.dumps({"not_available": section.reason})
        return json.dumps(prompt.slim(section.data), ensure_ascii=False, separators=(",", ":"))

    def roles(self) -> list[str]:
        return sorted({s.role for s in self.facts.sections if s.role != "crop"})

    def tools(self) -> list:
        from strands import tool

        box = self

        @tool
        def get_forecast(role: str, day: str = "today") -> str:
            """Daily forecast (temperature, rain chance, wind) for one place in the request.
            role: the place, e.g. "origin", "destination" or "location".
            day: "today", "tomorrow" or "day_after_tomorrow"."""
            return box._run(role, "forecast", day)

        @tool
        def get_hourly(role: str, day: str = "today") -> str:
            """Hour-by-hour forecast for one place in the request.
            role: "origin", "destination" or "location". day: "today", "tomorrow" or
            "day_after_tomorrow"."""
            return box._run(role, "hourly", day)

        @tool
        def get_rain_so_far(role: str) -> str:
            """Rainfall so far today for one place in the request.
            role: "origin", "destination" or "location"."""
            return box._run(role, "rain")

        @tool
        def get_metar_taf(role: str) -> str:
            """The airport weather report (METAR) and forecast (TAF) for one place, if it has
            an airport we cover. role: "origin" or "destination"."""
            return box._run(role, "aviation")

        @tool
        def get_best_window(role: str, day: str = "today") -> str:
            """The best contiguous time window of the day by the weather rules, or not available
            if no hour qualifies. Use it when the answer needs a time to go or to sow.
            role: "origin", "destination" or "location". day: "today", "tomorrow" or
            "day_after_tomorrow"."""
            return box._run(role, "window", day)

        return [get_forecast, get_hourly, get_rain_so_far, get_metar_taf, get_best_window]


# --- the models ------------------------------------------------------------------------


def providers() -> list[str]:
    """The agent's try-order. Offline mode and a disabled agent have none."""
    if config.OFFLINE_MODE or not config.ADVISORY_AGENT_ENABLED:
        return []
    out = []
    if config.GEMINI_API_KEY:
        out.append("gemini")
    if config.GROQ_API_KEY:
        out.append("groq")
    return out


def make_model(provider: str, model_id: str | None = None):
    """A Strands model for `provider`. Groq goes through the OpenAI-compatible client."""
    params = {"temperature": 0}
    if provider == "gemini":
        from strands.models.gemini import GeminiModel
        # Flash is a thinking model and its thoughts count against max_output_tokens:
        # without a budget of 0 most live runs (TFA-18, 2026-10-04) stopped with
        # MaxTokensReachedException before writing any JSON. narrate.py does the same.
        return GeminiModel(client_args={"api_key": config.GEMINI_API_KEY},
                           model_id=model_id or config.GEMINI_MODEL,
                           params={**params, "max_output_tokens": MAX_OUTPUT_TOKENS,
                                   "thinking_config": {"thinking_budget": 0}})
    if provider == "groq":
        from strands.models.openai import OpenAIModel
        # gpt-oss is a reasoning model: its reasoning counts against max_tokens and
        # slows every turn. "low" is what narrate.py sends for the same model; on the
        # live TFA-18 run without it, replies stopped at max tokens or ran out of time.
        # max_retries 0: the OpenAI client retries a 429 twice with backoff on its own,
        # which spent the whole budget on rate limits in the live run and hid them as
        # timeouts. One attempt per provider is the design (see run_agent).
        return OpenAIModel(client_args={"api_key": config.GROQ_API_KEY,
                                        "base_url": config.GROQ_BASE,
                                        "max_retries": 0},
                           model_id=model_id or config.GROQ_MODEL,
                           params={**params, "max_tokens": MAX_OUTPUT_TOKENS,
                                   "reasoning_effort": "low"})
    if provider == "ollama":  # the eval harness only; offline mode never runs the agent
        from strands.models.ollama import OllamaModel
        return OllamaModel(config.OLLAMA_BASE, model_id=model_id or config.OLLAMA_MODEL,
                           temperature=0, max_tokens=MAX_OUTPUT_TOKENS)
    raise ValueError(f"unknown provider {provider!r}")


def run_agent(model, box: Toolbox, system_prompt: str, timeout_s: float) -> str:
    """One agent run with a wall-clock budget. One attempt only: a provider error
    falls through to the next provider, not into Strands' backoff."""
    from strands import Agent
    from strands.event_loop._retry import ModelRetryStrategy

    agent = Agent(model=model, tools=box.tools(), system_prompt=system_prompt,
                  callback_handler=None, retry_strategy=ModelRetryStrategy(max_attempts=1))
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(agent, "Give the advisory for the request and facts in the system prompt.")
    try:
        return str(future.result(timeout=timeout_s))
    except concurrent.futures.TimeoutError as exc:
        box.cancelled = True
        agent.cancel()
        raise AgentError(f"no reply within {timeout_s:g}s") from exc
    except Exception as exc:  # noqa: BLE001 — every provider failure is a fallthrough
        raise AgentError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


# --- the entry point -----------------------------------------------------------------


def _agent_answer(
    kind: str, slots: dict, lang: str, facts: AdvisoryFacts, fetch: Fetch,
    models: list[tuple[str, object]], budget_s: float,
) -> tuple[dict, str, int, str | None]:
    """The first provider whose answer is valid and grounded: (answer, path, tool calls,
    why not, if none). Each failure is noted and the next provider is tried."""
    deadline = time.monotonic() + budget_s
    reason: str | None = None
    calls = 0
    for name, model in models:
        left = deadline - time.monotonic()
        if left <= 0.5:
            reason = reason or "out of time"
            break
        box = Toolbox(facts, fetch, config.ADVISORY_AGENT_MAX_TOOL_CALLS)
        system = prompt.build(kind, slots, lang, facts, tools=True)
        try:
            reply = run_agent(model, box, system, left)
        except AgentError as exc:
            calls += box.calls
            reason = f"{name}: {exc}"
            _LOG.warning("advisory agent %s failed: %s", name, exc)
            continue
        calls += box.calls
        parsed = schema.parse(reply)
        if parsed is None:
            reason = f"{name}: reply was not a JSON object"
            continue
        answer = template.finish(facts, schema.trim_cites(parsed))
        report = guardrail.check_advisory(answer, facts)
        if not report.ok:
            reason = f"{name}: guardrail: {'; '.join(report.problems)[:200]}"
            continue
        return answer, f"agent:{name}", calls, None
    return {}, "", calls, reason


def advise(kind: str, slots: dict, lang: str = "en", *, models=None, fetch: Fetch | None = None,
           timeout_s: float | None = None) -> Advice:
    """The answer for resolved `slots`. `models` ([(name, strands model)]) and `fetch`
    are injectable for tests and for the eval harness; production leaves them None."""
    started = time.perf_counter()
    facts = COLLECTORS[kind].collect(slots)

    if models is None:
        models = [(name, make_model(name)) for name in providers()]
    reason = None if models else "agent disabled, offline, or no provider key"
    answer: dict = {}
    path = "template"
    calls = 0

    if models:
        answer, got_path, calls, reason = _agent_answer(
            kind, slots, lang, facts, fetch or live_fetch(kind, slots), models,
            timeout_s if timeout_s is not None else config.ADVISORY_AGENT_TIMEOUT_S)
        if answer:
            path = got_path

    if path == "template":
        answer = template.template_answer(facts)  # its verdict already carries the override

    return Advice(kind, answer, facts, path, reason, calls,
                  round(time.perf_counter() - started, 3))
