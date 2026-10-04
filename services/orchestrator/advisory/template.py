"""The rule-based answer for travel and farming: no model, no network (plan.md §11.3 tier 3).

Used when the agent is off (`ADVISORY_AGENT_ENABLED=0`), offline (`OFFLINE_MODE=1`),
out of time, or its answer fails the guardrail. The verdict is `rubric.reference_verdict`
and every sentence is built from a value in the facts, so the answer grounds by
construction. English only for now, like the other templated answers.

`apply_override` is the hard override that runs after the agent: whatever it returned,
a red IMD warning, a thunderstorm METAR (§11.6) or a mode's avoid-level wind (TFA-7)
means "avoid".
"""

from __future__ import annotations

from advisory import rubric, schema


def _window(facts) -> dict | None:
    for section in facts.sections:
        if section.kind == "window" and section.available:
            return {k: section.data[k] for k in ("start_local", "end_local")}
    return None


def _strongest_wind(role_facts: dict, role: str) -> tuple[float | None, str | None]:
    """The highest wind the role's facts give (now or any hour) and its path — the
    same figure rubric.max_wind() judges, so the sentence says what decided."""
    best: tuple[float | None, str | None] = (None, None)
    now = (role_facts.get("current") or {}).get("wind_kmh")
    if now is not None:
        best = (now, f"{role}.current.wind_kmh")
    for i, hour in enumerate((role_facts.get("hourly") or {}).get("hours", [])):
        w = hour.get("wind_kmh")
        if w is not None and (best[0] is None or w > best[0]):
            best = (w, f"{role}.hourly.hours[{i}].wind_kmh")
    return best


def template_answer(facts) -> dict:
    """The `advisory.schema` answer for `facts`, from the rules alone."""
    verdict = rubric.reference_verdict(facts)
    pros: list[str] = []
    cons: list[str] = []
    cites: list[str] = []
    raw = facts.raw()

    if facts.kind == "travel":
        rules = rubric.mode_rules(facts.subject.get("mode"))
        for role in ("origin", "destination"):
            if "forecast" not in raw.get(role, {}):
                cons.append(f"The forecast for the {role} is not available.")
                continue
            pct = raw[role]["forecast"]["rain_probability_pct"]
            (cons if pct >= rules.rain_caution_pct else pros).append(
                f"Rain chance at the {role} is {pct}%.")
            cites.append(f"{role}.forecast.rain_probability_pct")
            wind, path = _strongest_wind(raw[role], role)
            if wind is not None:
                (cons if wind >= rules.wind_caution_kmh else pros).append(
                    f"Wind at the {role} reaches {wind} km/h.")
                cites.append(path)
            warning = raw[role].get("warnings")
            if warning is None:
                cons.append(f"The IMD warning for the {role} is not available.")
            elif warning["colour"] == "green":
                pros.append(f"No IMD warning is in force at the {role}.")
            else:
                article = "An" if warning["colour"][:1] in "aeiou" else "A"
                cons.append(f"{article} {warning['colour']} IMD warning is in force at the {role}.")
            aviation = raw[role].get("aviation")
            if aviation and "thunderstorm" in aviation["metar"]["briefing"]:
                cons.append(f"The {role} airport report shows a thunderstorm.")
        if rules.needs_marine:
            cons.append("Sea conditions are not in the facts, so the crossing cannot be "
                        "confirmed; check the ferry operator.")
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
    reason = [r for r in rubric.override_reasons(facts) if r not in answer.get("cons", [])]
    cons = [*reason, *answer.get("cons", [])][:schema.MAX_ITEMS]
    return {**answer, "verdict": "avoid", "cons": cons}
