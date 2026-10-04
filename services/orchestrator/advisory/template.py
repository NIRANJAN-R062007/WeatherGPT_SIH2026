"""The rule-based answer for travel and farming: no model, no network (plan.md §11.3 tier 3).

Used when the agent is off (`ADVISORY_AGENT_ENABLED=0`), offline (`OFFLINE_MODE=1`),
out of time, or its answer fails the guardrail. The verdict is `rubric.reference_verdict`
and every sentence is built from a value in the facts, so the answer grounds by
construction. English only for now, like the other templated answers.

`finish` is what runs after the agent: the hard override (whatever it returned, a red
IMD warning, a thunderstorm METAR (§11.6) or a mode's avoid-level wind (TFA-7) means
"avoid"; a crop the file gives no thresholds for is "not_available", and one outside
its sowing months "not_suitable", TFA-11), then the unreviewed-crop caveat.
"""

from __future__ import annotations

from advisory import rubric, schema

CROP_NOT_REVIEWED = "The crop thresholds have not yet been reviewed by an agronomist."


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
        forecast = raw.get("location", {}).get("forecast")
        cons += rubric.crop_gaps(crop)
        if not (forecast or {}).get("days"):
            cons.append("The forecast is not available.")
        elif not rubric.crop_gaps(crop):
            season = rubric.out_of_season(crop, forecast)
            if season:
                cons.append(season)
            elif crop.get("sowing_months"):
                pros.append(f"The forecast falls within the crop file's sowing months "
                            f"({' and '.join(crop['sowing_months'])}).")
            else:
                cons.append("The crop file gives no sowing months, so the season was not "
                            "checked.")
            i = rubric.breaching_day(crop, forecast)
            day = forecast["days"][0 if i is None else i]
            k = 0 if i is None else i
            when = day["label"] if day["label"] in ("today", "tomorrow") else f"on {day['label']}"
            (pros if i is None else cons).append(
                f"Rain chance {when} is {day['rain_probability_pct']}%, with a high of "
                f"{day['high_c']}°C and a low of {day['low_c']}°C.")
            cites += [f"location.forecast.days[{k}].{f}"
                      for f in ("rain_probability_pct", "high_c", "low_c")]
            cites.append("crop.entry")
        if crop and not crop.get("reviewed"):
            cons.append(CROP_NOT_REVIEWED)

    window = _window(facts)
    if facts.kind == "farming" and verdict != "suitable":
        window = None  # no time to sow is suggested when sowing is not advised
    return {"verdict": verdict, "pros": pros[:schema.MAX_ITEMS], "cons": cons[:schema.MAX_ITEMS],
            "window": window, "cites": cites[:schema.MAX_ITEMS]}


def apply_override(facts, answer: dict) -> dict:
    """`answer` with the hard override applied (rubric.hard_override). When it changes
    the verdict, the reason is added to `cons` from the facts, so the sentences still
    say why; a farming answer forced off "suitable" loses its window."""
    verdict = rubric.hard_override(facts)
    if verdict is None or answer.get("verdict") == verdict:
        return answer
    reason = [r for r in rubric.override_reasons(facts) if r not in answer.get("cons", [])]
    cons = [*reason, *answer.get("cons", [])][:schema.MAX_ITEMS]
    out = {**answer, "verdict": verdict, "cons": cons}
    if facts.kind == "farming":
        out["window"] = None
    return out


def add_caveats(facts, answer: dict) -> dict:
    """What every farming answer must say, whoever wrote it: an unreviewed crop entry
    is named as such (plan.md §11.7: "the answer says so")."""
    crop = facts.raw().get("crop", {}).get("entry")
    if facts.kind != "farming" or not crop or crop.get("reviewed"):
        return answer
    cons = answer.get("cons", [])
    if CROP_NOT_REVIEWED in cons:
        return answer
    # Last, after the reasons for the verdict, but never the one trimmed off.
    return {**answer, "cons": [*cons[:schema.MAX_ITEMS - 1], CROP_NOT_REVIEWED]}


def finish(facts, answer: dict) -> dict:
    """The rules the code applies to an agent's answer, in order: the override, then
    the caveats. The template answer already carries both."""
    return add_caveats(facts, apply_override(facts, answer))
