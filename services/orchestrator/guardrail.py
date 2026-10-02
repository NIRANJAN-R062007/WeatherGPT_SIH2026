"""Grounding guardrail + numeric validator for `/ask` narration.

plan.md §14 calls this "non-negotiable, even in minimal form": every numeric
token the narration emits must trace back to a raw field the weather source
actually returned, under a unit-aware match. See plan.md §4 for the pipeline
this gate sits in (narrate -> validate -> fall back to template on failure).

Clock times ("8 AM", "08:00") and time ranges ("8 AM–11 AM") are checked the
same way (WIE-5, plan.md §8 Phase 9): a time must be one the structured result
carries, and a range must be a start/end pair a window in the result actually
has — an answer can't stitch two real times into a window the engine never
produced. See `_extract_clock`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Declarative path -> unit map. Seeded with the current stub fields plus the
# nested paths Syed's real Google Weather API ingestion will use, so this
# doesn't need touching when the stub is swapped out. A path missing here
# gets unit None, which only matches unit-less readings — see _match.
FIELD_UNITS: dict[str, str] = {
    # flat facts keys emitted by weather_data.get_weather()
    "temp_c": "celsius",
    "feels_like_c": "celsius",
    "high_c": "celsius",
    "low_c": "celsius",
    "humidity_pct": "percent",
    "rain_probability_pct": "percent",
    "wind_kmh": "speed_kmh",
    # raw Google Weather API paths (fixture-level tests; _unit_for suffix-matches)
    "temperature.degrees": "celsius",
    "maxTemperature.degrees": "celsius",
    "minTemperature.degrees": "celsius",
    "relativeHumidity": "percent",
    "precipitation.probability.percent": "percent",
    "wind.speed.value": "speed_kmh",
    "rain_so_far_mm": "millimetres",
    "rain_last_24h_mm": "millimetres",
    "precipitation.qpf.quantity": "millimetres",
    # window_analyzer.find_best_window()'s aggregates (WIE-3/5): the figures a
    # narrated best window quotes besides its start/end times
    "avg_temp_c": "celsius",
    "max_rain_probability_pct": "percent",
    "max_wind_kmh": "speed_kmh",
}

# Unit markers checked (after optional whitespace) right after each number
# extracted from an answer. None is prefix of another, so order is free.
#
# Symbols (°C, %, km/h, mm) are language-neutral — Bhashini's live
# translation output tends to leave these as-is regardless of target
# language.
_SYMBOL_UNIT_MARKERS: list[tuple[str, str]] = [
    ("°C", "celsius"),
    ("°F", "fahrenheit"),
    ("%", "percent"),
    ("km/h", "speed_kmh"),
    ("mm", "millimetres"),
    ("millimetres", "millimetres"),
    ("millimeters", "millimetres"),
]

# Spelled-out unit words, per target language, for when Bhashini's live
# translation renders a unit as a word instead of a symbol (e.g. Tamil "28
# டிகிரி செல்சியஸ்", "81 சதவீதமாக", "14 கிமீ வேகத்தில்"). Without an entry here,
# a translated number carries no unit marker at all, and _match() refuses to
# ground it against any unit-bearing field — so the answer falls back to the
# template. A missing language entry below therefore means every translated
# answer in that language is rejected, not silently accepted — this table
# needs a new row before a language goes live with real Bhashini translation.
#
# "சதவீத" (not "சதவீதம்") is deliberately the bare stem: a case suffix elides
# the trailing pulli ("சதவீதம்" + "ஆக" -> "சதவீதமாக"), so matching the full
# word with pulli would miss that form. The Tamil entries were
# reverse-engineered from real translated /ask responses.
_WORD_UNIT_MARKERS: dict[str, list[tuple[str, str]]] = {
    "ta": [
        ("டிகிரி செல்சியஸ்", "celsius"),
        ("சதவீத", "percent"),
        ("கிமீ", "speed_kmh"),
        ("மி.மீ", "millimetres"),  # TODO: native_qa
    ],
    # celsius/percent/speed_kmh rows reviewed by a native speaker on Sep 13
    # (commit fce2ad9, plan.md §13). The millimetres rows came later (Sep 14)
    # and are unreviewed first drafts in every language, Tamil included.
    "hi": [
        ("डिग्री सेल्सियस", "celsius"),
        ("प्रतिशत", "percent"),
        ("किमी", "speed_kmh"),
        ("मिमी", "millimetres"),  # TODO: native_qa
    ],
    "te": [
        ("డిగ్రీల సెల్సియస్", "celsius"),
        ("శాతం", "percent"),
        ("కిమీ", "speed_kmh"),
        ("మి.మీ", "millimetres"),  # TODO: native_qa
    ],
    "mr": [
        ("अंश सेल्सिअस", "celsius"),
        ("टक्के", "percent"),
        ("किमी", "speed_kmh"),
        ("मिमी", "millimetres"),  # TODO: native_qa
    ],
}


def _all_unit_markers() -> list[tuple[str, str]]:
    """Flatten the per-language word tables into one list for `_extract`.

    `check()` doesn't know (and shouldn't need to know) what language its
    answer is in — the same guardrail validates English, Tamil, Hindi,
    Telugu, Marathi and hand-written template output alike. Flattening is
    safe here: markers across languages use different scripts, so none
    collides with, or is a prefix of, another (see the module-level note
    above this table).
    """
    markers = list(_SYMBOL_UNIT_MARKERS)
    for lang_markers in _WORD_UNIT_MARKERS.values():
        markers.extend(lang_markers)
    return markers


_UNIT_MARKERS: list[tuple[str, str]] = _all_unit_markers()

# (?<!\d) keeps a hyphenated range like "20-30%" from parsing as figures
# 20 and -30 — the lookbehind only lets `-` bind as a sign when it isn't
# itself glued onto a preceding digit, so "-30" only matches as negative
# when it's a real standalone negative number (e.g. "-5°C"), not the second
# half of a range the LLM wrote despite being told not to.
_NUMBER_RE = re.compile(r"(?<!\d)-?\d+(?:\.\d+)?")


@dataclass
class Report:
    ok: bool
    matched: int
    total: int
    figures: list[dict] = field(default_factory=list)


def check(answer: str, raw: dict) -> Report:
    """Validate every numeric token in `answer` against `raw`'s numeric leaves.

    Unit-aware: a figure only matches a field of a compatible unit (see
    _match), so `"20°C"` cannot pass by matching a `rain_probability_pct` of
    20, and a bare "65" cannot pass by matching humidity_pct. An answer with
    numbers but no matching raw data never passes vacuously. Never call this
    on the provenance footer — its timestamps aren't weather facts.

    Clock times and ranges are checked too (WIE-5): they are pulled out of the
    answer first, so their digits never reach the numeric matcher, and each
    must ground against the "HH:MM" strings / `start_local`+`end_local` pairs
    in `raw` — see `_extract_clock` and `_index_times`.
    """
    index = _index(raw)
    clock, remainder = _extract_clock(_normalize_digits(answer))
    times, windows = _index_times(raw)

    figures = _extract(remainder)
    total = len(figures) + len(clock)
    reports = []
    matched = 0
    for reading, value, unit, decimals in figures:
        path = _match(value, unit, decimals, index)
        if path is not None:
            matched += 1
        reports.append(
            {
                "reading": reading,
                "value": value,
                "unit": unit,
                "path": path,
                "matched": path is not None,
            }
        )

    for reading, start, end in clock:
        if end is None:
            path, unit = times.get(start), "clock"
        else:
            path, unit = windows.get((start, end)), "clock_range"
        if path is not None:
            matched += 1
        report = {
            "reading": reading,
            "value": start,  # minutes since midnight, city-local
            "unit": unit,
            "path": path,
            "matched": path is not None,
        }
        if end is not None:
            report["end_value"] = end
        reports.append(report)

    return Report(ok=(matched == total), matched=matched, total=total, figures=reports)


@dataclass
class AdvisoryReport:
    """Outcome of `check_advisory`. `ok` only if the output has the right shape
    and nothing in it is ungrounded; `problems` says why not, one line each.
    `grounding` is the figure-level report over every pros/cons sentence, each
    figure labelled with its `field` ("pros[0]")."""

    ok: bool
    problems: list[str] = field(default_factory=list)
    grounding: Report | None = None


def check_advisory(output, facts) -> AdvisoryReport:
    """Validate a travel/farming answer (TFA-5) against its `AdvisoryFacts`.

    Fails if the output isn't the strict `advisory.schema` shape, if a figure
    or clock time in `pros`/`cons` doesn't ground in `facts.raw()` (`check`,
    sentence by sentence, so clock times and ranges are covered), if `window`
    isn't a window the facts carry, or if a `cites` path isn't in the facts. A
    window or figure the engine didn't supply is rejected the same as one the
    model made up — the facts are the only source (plan.md §11.6). `output` may
    be the model's raw reply; a reply that isn't JSON fails.

    This does not judge whether the verdict is *right* for the facts (that is
    the rule table's job, TFA-7/11) — only that nothing in the answer is
    outside them. A caller falls back to the rule-based answer on `ok` False.
    """
    from advisory import schema  # local: guardrail stays importable on its own

    if isinstance(output, str):
        parsed = schema.parse(output)
        if parsed is None:
            return AdvisoryReport(False, ["output is not valid JSON"])
        output = parsed
    problems = schema.validate(output, facts.kind)
    if problems:
        return AdvisoryReport(False, problems)

    raw = facts.raw()
    _, windows = _index_times(raw)
    figures: list[dict] = []
    matched = 0
    for key in ("pros", "cons"):
        for i, sentence in enumerate(output[key]):
            report = check(sentence, raw)
            matched += report.matched
            for fig in report.figures:
                figures.append({**fig, "field": f"{key}[{i}]"})
                if not fig["matched"]:
                    problems.append(f"{key}[{i}]: {fig['reading']!r} is not in the facts")

    window = output.get("window")
    if window is not None:
        bounds = schema.window_bounds(window)
        if bounds not in windows:
            problems.append(
                f"window {window['start_local']}–{window['end_local']} is not a window in the facts"
            )

    for path in output.get("cites", []):
        if not _has_path(raw, path):
            problems.append(f"cites {path!r}, which is not in the facts")

    grounding = Report(ok=not any(not f["matched"] for f in figures), matched=matched,
                       total=len(figures), figures=figures)
    return AdvisoryReport(ok=not problems, problems=problems, grounding=grounding)


_PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")


def _has_path(raw, path: str) -> bool:
    """Whether a dotted/indexed path ("origin.current.temp_c",
    "origin.hourly.hours[0].temp_c" — the same spelling `_index` produces)
    leads to a present, non-null value in `raw`."""
    node = raw
    tokens = _PATH_TOKEN_RE.findall(path)
    if not tokens or ".." in path or path.startswith(".") or path.endswith("."):
        return False
    if "".join(tokens) != path.replace(".", ""):
        return False  # stray characters the tokeniser skipped
    for token in tokens:
        if token.startswith("["):
            i = int(token[1:-1])
            if not isinstance(node, list) or i >= len(node):
                return False
            node = node[i]
        else:
            if not isinstance(node, dict) or token not in node:
                return False
            node = node[token]
    return node is not None


def _index(raw, prefix: str = "") -> dict[str, float]:
    """Flatten nested dict/list structures to dotted-path -> numeric leaf.

    List elements use `foo[0].bar`. Strings are excluded so `source` and ISO
    timestamps never pollute the index. Walking nested structures now (vs.
    a flat dict) avoids a rewrite when Syed's real API response lands.
    """
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            path = f"{prefix}.{key}" if prefix else key
            out.update(_index(value, path))
    elif isinstance(raw, list):
        for i, value in enumerate(raw):
            out.update(_index(value, f"{prefix}[{i}]"))
    elif isinstance(raw, bool):
        pass  # bool is a numeric subtype in Python; not a real numeric leaf
    elif isinstance(raw, (int, float)):
        out[prefix] = float(raw)
    return out


def _normalize_digits(text: str) -> str:
    """ASCII-fy non-ASCII decimal digits (Tamil ௦-௯, Devanagari ०-९, ...).

    Today's templates emit ASCII digits in both languages, but Bhashini
    translation (a later task) may not, so the numeric regex below stays
    language-agnostic.
    """
    out = []
    for ch in text:
        if not ch.isascii() and ch.isdigit():
            try:
                out.append(str(unicodedata.digit(ch)))
                continue
            except (TypeError, ValueError):
                pass
        out.append(ch)
    return "".join(out)


def _extract(answer: str) -> list[tuple[str, float, str | None, int]]:
    """Pull `(reading, value, unit, decimals)` for every number in `answer`.

    `decimals` is the number of digits after the point as *written*, so the
    matching rule can reject false precision (`"31.5"` vs. raw `31.4`)
    without rejecting legitimate rounding (`"31"` vs. raw `31.4`).
    """
    normalized = _normalize_digits(answer)
    figures = []
    for m in _NUMBER_RE.finditer(normalized):
        text = m.group()
        value = float(text)
        decimals = len(text.split(".", 1)[1]) if "." in text else 0

        offset = m.end()
        while offset < len(normalized) and normalized[offset] == " ":
            offset += 1

        unit = None
        end = m.end()
        for marker, unit_name in _UNIT_MARKERS:
            if normalized[offset : offset + len(marker)] == marker:
                unit, end = unit_name, offset + len(marker)
                break

        figures.append((normalized[m.start() : end], value, unit, decimals))
    return figures


# A clock time is "H:MM" / "HH:MM" (24-hour unless am/pm follows) or "H am/pm"
# ("8 AM", "8pm", "8 a.m."). A bare "8" is deliberately not a time — it stays a
# number for the numeric matcher. The lookarounds keep "31.5", ISO timestamps
# ("T08:00:00") and "10:30:15" from being read as a time; a colon that
# merely follows one ("8 AM–11 AM: dry") is fine.
_CLOCK_RE = re.compile(
    r"""(?<![\d:.])
        (?: (?P<h1>\d{1,2}):(?P<m1>\d{2}) (?:\s*(?P<mer1>[ap])\.?m\b\.?)?
          | (?P<h2>\d{1,2}) \s*(?P<mer2>[ap])\.?m\b\.?
        )
        (?!\d|:\d)""",
    re.IGNORECASE | re.VERBOSE,
)

# "8–11 AM": one meridiem written for both ends, so the first end is not a
# clock time on its own and `_CLOCK_RE` would miss it.
_SHARED_MERIDIEM_RE = re.compile(
    r"""(?<![\d:.])
        (?P<h1>\d{1,2})(?::(?P<m1>\d{2}))?
        \s*(?:[-–—]|to|until|till)\s*
        (?P<h2>\d{1,2})(?::(?P<m2>\d{2}))?
        \s*(?P<mer>[ap])\.?m\b\.?
        (?!\d|:\d)""",
    re.IGNORECASE | re.VERBOSE,
)

# What may sit between two clock times for them to read as one range. "and"
# only counts after "between" ("between 8 AM and 11 AM"), so "at 8 AM and 11 AM
# it rains" stays two separate times.
_RANGE_GAP_RE = re.compile(r"\s*(?:[-–—]|to|until|till)\s*", re.IGNORECASE)
_AND_GAP_RE = re.compile(r"\s*and\s*", re.IGNORECASE)
_BETWEEN_RE = re.compile(r"between\s*$", re.IGNORECASE)

_HHMM_RE = re.compile(r"\d{1,2}:\d{2}")


def _clock_minutes(hour: int, minute: int, meridiem: str | None) -> int | None:
    """Minutes since midnight, or None if it isn't a valid time."""
    if minute > 59:
        return None
    if meridiem is None:  # 24-hour clock, as the engine writes it
        return hour * 60 + minute if hour <= 23 else None
    if not 1 <= hour <= 12:
        return None
    return (hour % 12 + (12 if meridiem.lower() == "p" else 0)) * 60 + minute


def _extract_clock(text: str) -> tuple[list[tuple[str, int, int | None]], str]:
    """Pull every clock time / range out of `text` (digits already ASCII).

    Returns `([(reading, start, end)], remainder)`: minutes since midnight,
    `end` None for a lone time, and `text` with those spans blanked out so the
    numeric extractor doesn't re-read their digits as unit-less numbers.
    A time that isn't valid ("25:00", "13 PM") is left in the remainder, where
    it fails numeric grounding rather than being waved through.
    """
    found: list[tuple[int, int, int, int | None, str]] = []  # (pos, end_pos, start, end, reading)
    blanked = text

    def blank(m: re.Match) -> None:
        nonlocal blanked
        blanked = blanked[: m.start()] + " " * (m.end() - m.start()) + blanked[m.end():]

    for m in _SHARED_MERIDIEM_RE.finditer(text):
        mer = m["mer"]
        h1, m1 = int(m["h1"]), int(m["m1"] or 0)
        start = _clock_minutes(h1, m1, mer)
        end = _clock_minutes(int(m["h2"]), int(m["m2"] or 0), mer)
        if start is not None and end is not None and start >= end:
            # "11–1 PM" is 11 AM–1 PM: the first end can't be after the second
            start = _clock_minutes(h1, m1, "a" if mer.lower() == "p" else "p")
        if start is None or end is None or start >= end:
            continue
        found.append((m.start(), m.end(), start, end, m.group()))
        blank(m)

    singles = []
    for m in _CLOCK_RE.finditer(blanked):
        minutes = _clock_minutes(
            int(m["h1"] or m["h2"]), int(m["m1"] or 0), m["mer1"] or m["mer2"],
        )
        if minutes is None:
            continue
        singles.append((m.start(), m.end(), minutes, m.group()))
        blank(m)

    # Join neighbouring lone times into a range when the text between them says so.
    i = 0
    while i < len(singles):
        pos, stop, minutes, reading = singles[i]
        if i + 1 < len(singles):
            n_pos, n_stop, n_minutes, _ = singles[i + 1]
            gap = text[stop:n_pos]
            if _RANGE_GAP_RE.fullmatch(gap) or (
                _AND_GAP_RE.fullmatch(gap) and _BETWEEN_RE.search(text[:pos])
            ):
                found.append((pos, n_stop, minutes, n_minutes, text[pos:n_stop]))
                i += 2
                continue
        found.append((pos, stop, minutes, None, reading))
        i += 1

    found.sort()
    return [(reading, start, end) for _, _, start, end, reading in found], blanked


def _index_times(raw) -> tuple[dict[int, str], dict[tuple[int, int], str]]:
    """Index the structured result's clock times, like `_index` does numbers.

    Returns `(times, windows)`: every "HH:MM" string leaf under a local-time
    key (an hour's `local_time`, a window's `start_local`/`end_local`) as
    minutes-since-midnight -> dotted path, and every dict carrying both
    `start_local` and `end_local` (window_analyzer's result) as `(start, end)`
    -> path. A range only grounds against `windows`, so two real hours can't be
    stitched into a window the engine didn't return.

    Only local-time keys count: an answer's times are city-local, and an
    "HH:MM" under another key — a METAR/TAF `time_utc` — is a different clock
    that must not ground a local time by coincidence.
    """
    times: dict[int, str] = {}
    windows: dict[tuple[int, int], str] = {}

    def minutes_of(value) -> int | None:
        if not isinstance(value, str) or not _HHMM_RE.fullmatch(value):
            return None
        hour, minute = value.split(":")
        return _clock_minutes(int(hour), int(minute), None)

    def is_local_key(key: str) -> bool:
        return key == "local_time" or key.endswith("_local")

    def walk(node, prefix: str, key: str = "") -> None:
        if isinstance(node, dict):
            start, end = minutes_of(node.get("start_local")), minutes_of(node.get("end_local"))
            if start is not None and end is not None:
                windows.setdefault((start, end), prefix or "<root>")
            for name, value in node.items():
                walk(value, f"{prefix}.{name}" if prefix else name, name)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{prefix}[{i}]", key)
        elif is_local_key(key):
            minutes = minutes_of(node)
            if minutes is not None:
                times.setdefault(minutes, prefix)

    walk(raw, "")
    return times, windows


def _unit_for(path: str) -> str | None:
    """Look up a path's unit in FIELD_UNITS.

    Real Google Weather JSON nests the fields FIELD_UNITS names (e.g.
    ``forecastDays[0].maxTemperature.degrees`` vs. the map's
    ``maxTemperature.degrees``), so after an exact miss, drop ``[i]`` list
    indices and match on the longest known path suffix.
    """
    if path in FIELD_UNITS:
        return FIELD_UNITS[path]
    bare = re.sub(r"\[\d+\]", "", path)
    if bare in FIELD_UNITS:
        return FIELD_UNITS[bare]
    parts = bare.split(".")
    for start in range(1, len(parts)):
        suffix = ".".join(parts[start:])
        if suffix in FIELD_UNITS:
            return FIELD_UNITS[suffix]
    return None


def _match(value: float, unit: str | None, decimals: int, index: dict[str, float]) -> str | None:
    """Return the dotted path of the first indexed field this figure grounds to.

    Units must agree exactly: a unit-less figure only grounds to a unit-less
    field (counts like hours_counted), never to a temperature/percent/speed
    field — otherwise "wind 65" would pass by matching humidity_pct=65.
    Values agree under answer-precision rounding — see `_extract`.
    """
    for path, raw_value in index.items():
        if _unit_for(path) != unit:
            continue
        if round(raw_value, decimals) == value:
            return path
    return None
