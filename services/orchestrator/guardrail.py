"""Grounding guardrail + numeric validator for `/ask` narration.

plan.md §14 calls this "non-negotiable, even in minimal form": every numeric
token the narration emits must trace back to a raw field the weather source
actually returned, under a unit-aware match. See plan.md §4 for the pipeline
this gate sits in (narrate -> validate -> fall back to template on failure).
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
        ("மி.மீ", "millimetres"),
    ],
    # Reviewed by a native speaker — confirmed accurate (plan.md §13).
    "hi": [
        ("डिग्री सेल्सियस", "celsius"),
        ("प्रतिशत", "percent"),
        ("किमी", "speed_kmh"),
        ("मिमी", "millimetres"),
    ],
    "te": [
        ("డిగ్రీల సెల్సియస్", "celsius"),
        ("శాతం", "percent"),
        ("కిమీ", "speed_kmh"),
        ("మి.మీ", "millimetres"),
    ],
    "mr": [
        ("अंश सेल्सिअस", "celsius"),
        ("टक्के", "percent"),
        ("किमी", "speed_kmh"),
        ("मिमी", "millimetres"),
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

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


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
    """
    index = _index(raw)

    figures = _extract(answer)
    total = len(figures)
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

    return Report(ok=(matched == total), matched=matched, total=total, figures=reports)


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
