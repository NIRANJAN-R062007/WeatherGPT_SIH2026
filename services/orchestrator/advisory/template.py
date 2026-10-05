"""The rule-based answer for travel and farming: no model, no network (plan.md §11.3 tier 3).

Used when the agent is off (`ADVISORY_AGENT_ENABLED=0`), offline (`OFFLINE_MODE=1`),
out of time, or its answer fails the guardrail. The verdict is `rubric.reference_verdict`
and every sentence is built from a value in the facts, so the answer grounds by
construction. Sentences come from `wording.py` in the request's language (TFA-23).

`finish` is what runs after the agent: the hard override (whatever it returned, a red
IMD warning, a thunderstorm METAR (§11.6) or a mode's avoid-level wind (TFA-7) means
"avoid"; a crop the file gives no thresholds for is "not_available", and one outside
its sowing months "not_suitable", TFA-11), then the floor (TFA-26: never a verdict less
cautious than the rule table's own, so a model can't turn an orange warning into "go"),
then the unreviewed-crop caveat.
"""

from __future__ import annotations

from advisory import rubric, schema, wording

CROP_NOT_REVIEWED = wording.say("crop_not_reviewed")  # English; crop_not_reviewed(lang)


def crop_not_reviewed(lang: str = "en") -> str:
    return wording.say("crop_not_reviewed", lang)


def _window(facts) -> dict | None:
    for section in facts.sections:
        if section.kind == "window" and section.available:
            return {k: section.data[k] for k in ("start_local", "end_local")}
    return None


def _strongest_wind(facts, role: str) -> tuple[float | None, str | None]:
    """The trip day's highest wind at `role` and its path — the same figure
    rubric.max_wind() judges, so the sentence says what decided."""
    readings = rubric.wind_readings(facts, role)
    return max(readings, key=lambda r: r[0]) if readings else (None, None)


def template_answer(facts, lang: str = "en") -> dict:
    """The `advisory.schema` answer for `facts`, from the rules alone, in `lang`."""
    say = wording.say
    verdict = rubric.reference_verdict(facts)
    pros: list[str] = []
    cons: list[str] = []
    cites: list[str] = []
    raw = facts.raw()

    if facts.kind == "travel":
        rules = rubric.mode_rules(facts.subject.get("mode"))
        for role in ("origin", "destination"):
            place = wording.role(role, lang)
            if "forecast" not in raw.get(role, {}):
                cons.append(say("forecast_unavailable_role", lang, role=place))
                continue
            pct = raw[role]["forecast"].get("rain_probability_pct")
            if pct is None:  # the feed gave none: not read as dry, so nothing to quote
                cons.append(say("no_rain_chance_role", lang, role=place))
            else:
                (cons if pct >= rules.rain_caution_pct else pros).append(
                    say("rain_chance_role", lang, role=place, pct=pct))
                cites.append(f"{role}.forecast.rain_probability_pct")
            wind, path = _strongest_wind(facts, role)
            if wind is None:
                cons.append(say("no_wind_role", lang, role=place))
            else:
                (cons if wind >= rules.wind_caution_kmh else pros).append(
                    say("wind_role", lang, role=place, wind=wind))
                cites.append(path)
            warning = raw[role].get("warnings")
            if warning is None:
                cons.append(say("warning_unavailable_role", lang, role=place))
            elif warning["colour"] == "green":
                pros.append(say("no_warning_role", lang, role=place))
            else:
                cons.append(rubric.warning_sentence(role, warning["colour"], lang))
            storm = rubric.thunderstorm_source(facts, role)
            if storm:
                cons.append(rubric.thunderstorm_sentence(role, storm, lang))
        if rules.needs_marine:
            cons.append(say("sea_unknown", lang))
    else:
        crop = raw.get("crop", {}).get("entry")
        forecast = raw.get("location", {}).get("forecast")
        cons += rubric.crop_gaps(crop, lang)
        gaps = rubric.forecast_gaps(crop, forecast, lang)
        if not (forecast or {}).get("days"):
            cons.append(say("forecast_unavailable", lang))
        elif gaps:
            cons += gaps
        elif not rubric.crop_gaps(crop):
            season = rubric.out_of_season(crop, forecast, lang)
            if season:
                cons.append(season)
            elif crop.get("sowing_months"):
                pros.append(say("in_season", lang,
                                months=wording.months(crop["sowing_months"], lang)))
            else:
                cons.append(say("no_sowing_months", lang))
            i = rubric.breaching_day(crop, forecast)
            day = forecast["days"][0 if i is None else i]
            k = 0 if i is None else i
            when = wording.when(day["label"], lang)
            if i is not None and rubric.is_heavy_rain(day):
                cons.append(say("heavy_rain", lang, when=when, mm=day["rain_mm"]))
            pct = day.get("rain_probability_pct")  # judged only if the crop file gives a limit
            figures = {"mm": day["rain_mm"], "high": day["high_c"], "low": day["low_c"]}
            (pros if i is None else cons).append(
                say("rain_amount_day", lang, when=when, **figures) if pct is None
                else say("rain_day", lang, when=when, pct=pct, **figures))
            if pct is None:
                cons.append(say("no_rain_chance", lang, day=wording.day(day["label"], lang)))
            cites += [f"location.forecast.days[{k}].{f}"
                      for f in ("rain_probability_pct", "rain_mm", "high_c", "low_c")
                      if day.get(f) is not None]
            cites.append("crop.entry")
        if crop and not crop.get("reviewed"):
            cons.append(crop_not_reviewed(lang))

    window = _window(facts)
    if facts.kind == "farming" and verdict != "suitable":
        window = None  # no time to sow is suggested when sowing is not advised
    return {"verdict": verdict, "pros": pros[:schema.MAX_ITEMS], "cons": cons[:schema.MAX_ITEMS],
            "window": window, "cites": cites[:schema.MAX_ITEMS]}


def apply_override(facts, answer: dict, lang: str = "en") -> dict:
    """`answer` with the hard override applied (rubric.hard_override). When it changes
    the verdict, the reason is added to `cons` from the facts, so the sentences still
    say why; a farming answer forced off "suitable" loses its window."""
    verdict = rubric.hard_override(facts)
    if verdict is None or answer.get("verdict") == verdict:
        return answer
    reason = [r for r in rubric.override_reasons(facts, lang) if r not in answer.get("cons", [])]
    cons = [*reason, *answer.get("cons", [])][:schema.MAX_ITEMS]
    out = {**answer, "verdict": verdict, "cons": cons}
    if facts.kind == "farming":
        out["window"] = None
    return out


# How cautious each verdict is. "not_available" is left alone: a model that says it can't
# judge isn't softer than the rules, and the rules' own "not_available" comes as an override.
_CAUTION = {
    "travel": {"go": 0, "caution": 1, "avoid": 2},
    "farming": {"suitable": 0, "not_suitable": 1},
}


def apply_floor(facts, answer: dict, lang: str = "en") -> dict:
    """`answer` raised to `rubric.reference_verdict` when the model's verdict is less
    cautious (TFA-26). The rule-based answer's `cons` go first so the sentences say why,
    and its `cites` with them; both are built from the facts, so the answer still grounds."""
    rank = _CAUTION[facts.kind]
    verdict, floor = answer.get("verdict"), rubric.reference_verdict(facts)
    if verdict not in rank or floor not in rank or rank[verdict] >= rank[floor]:
        return answer
    if not all(isinstance(answer.get(k, []), list) for k in ("cons", "cites")):
        return answer  # a malformed reply: left for the guardrail to reject, not repaired
    rules = template_answer(facts, lang)
    cons = list(dict.fromkeys([*rules["cons"], *answer.get("cons", [])]))[:schema.MAX_ITEMS]
    cites = list(dict.fromkeys([*rules["cites"], *answer.get("cites", [])]))[:schema.MAX_ITEMS]
    out = {**answer, "verdict": floor, "cons": cons, "cites": cites}
    if facts.kind == "farming":
        out["window"] = None  # no time to sow is suggested when sowing is not advised
    return out


def add_caveats(facts, answer: dict, lang: str = "en") -> dict:
    """What every farming answer must say, whoever wrote it: an unreviewed crop entry
    is named as such (plan.md §11.7: "the answer says so")."""
    crop = facts.raw().get("crop", {}).get("entry")
    if facts.kind != "farming" or not crop or crop.get("reviewed"):
        return answer
    cons = answer.get("cons", [])
    caveat = crop_not_reviewed(lang)
    if caveat in cons:
        return answer
    # Last, after the reasons for the verdict, but never the one trimmed off.
    return {**answer, "cons": [*cons[:schema.MAX_ITEMS - 1], caveat]}


def finish(facts, answer: dict, lang: str = "en") -> dict:
    """The rules the code applies to an agent's answer, in order: the override, the
    floor, then the caveats, worded in `lang`. The template answer already carries all three."""
    return add_caveats(facts, apply_floor(facts, apply_override(facts, answer, lang), lang), lang)
