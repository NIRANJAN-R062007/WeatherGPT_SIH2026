"""The rule-based answer for travel and farming: no model, no network (plan.md §11.3 tier 3).

Used when the agent is off (`ADVISORY_AGENT_ENABLED=0`), offline (`OFFLINE_MODE=1`),
out of time, or its answer fails the guardrail. The verdict is `rubric.reference_verdict`
and every sentence is built from a value in the facts, so the answer grounds by
construction. English only for now, like the other templated answers.

`apply_override` is the §11.6 hard override that runs after the agent: whatever it
returned, a red IMD warning or a thunderstorm METAR means "avoid".
"""

from __future__ import annotations

from advisory import rubric, schema


def _window(facts) -> dict | None:
    for section in facts.sections:
        if section.kind == "window" and section.available:
            return {k: section.data[k] for k in ("start_local", "end_local")}
    return None


def template_answer(facts) -> dict:
    """The `advisory.schema` answer for `facts`, from the rules alone."""
    verdict = rubric.reference_verdict(facts)
    pros: list[str] = []
    cons: list[str] = []
    cites: list[str] = []
    raw = facts.raw()

    if facts.kind == "travel":
        for role in ("origin", "destination"):
            if "forecast" not in raw.get(role, {}):
                cons.append(f"The forecast for the {role} is not available.")
                continue
            pct = raw[role]["forecast"]["rain_probability_pct"]
            (cons if pct >= rubric.RAIN_CAUTION_PCT else pros).append(
                f"Rain chance at the {role} is {pct}%.")
            cites.append(f"{role}.forecast.rain_probability_pct")
            wind = (raw[role].get("current") or {}).get("wind_kmh")
            if wind is not None:
                (cons if wind >= rubric.WIND_CAUTION_KMH else pros).append(
                    f"Wind at the {role} is {wind} km/h.")
                cites.append(f"{role}.current.wind_kmh")
            warning = raw[role].get("warnings")
            if warning is None:
                cons.append(f"The IMD warning for the {role} is not available.")
            elif warning["colour"] == "green":
                pros.append(f"No IMD warning is in force at the {role}.")
            else:
                cons.append(f"An {warning['colour']} IMD warning is in force at the {role}.")
            aviation = raw[role].get("aviation")
            if aviation and "thunderstorm" in aviation["metar"]["briefing"]:
                cons.append(f"The {role} airport report shows a thunderstorm.")
    else:
        crop = raw.get("crop", {}).get("entry")
        days = (raw.get("location", {}).get("forecast") or {}).get("days")
        if crop is None:
            cons.append("The crop file has no entry for this crop.")
        if not days:
            cons.append("The forecast is not available.")
        if crop and days:
            day = days[0]
            ok = verdict == "suitable"
            (pros if ok else cons).append(
                f"Rain chance is {day['rain_probability_pct']}% with a high of {day['high_c']}°C.")
            cites += ["location.forecast.days[0].rain_probability_pct",
                      "location.forecast.days[0].high_c"]

    return {"verdict": verdict, "pros": pros, "cons": cons, "window": _window(facts),
            "cites": cites}


def apply_override(facts, answer: dict) -> dict:
    """`answer` with the hard override applied. When it changes the verdict, the
    reason is added to `cons` from the facts, so the sentences still say why."""
    if rubric.hard_override(facts) is None or answer.get("verdict") == "avoid":
        return answer
    reason = [c for c in template_answer(facts)["cons"] if "warning is in force" in c
              or "thunderstorm" in c]
    cons = [*reason, *answer.get("cons", [])][:schema.MAX_ITEMS]
    return {**answer, "verdict": "avoid", "cons": cons}
