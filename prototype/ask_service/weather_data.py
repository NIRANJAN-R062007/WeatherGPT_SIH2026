"""STUB — stand-in for the real Google Weather API ingestion module.

Replace get_weather() with the live ingestion module (+ decoder tables +
cache) once it lands. Numbers here are transcribed from the committed
snapshots in data/fixtures/google_weather/ (2026-09-10), so wiring the
frontend to this stub shows plausible data and the live swap is seamless.

The stub ignores `day`: temp_c is current, rain_probability_pct is
tomorrow's daytime probability. The real module will be day-aware.

`condition` values are the canonical decoder keys (see i18n.CONDITION_EN) —
lowercased Google Weather API weatherCondition.type. data/decoders/ must
map raw type -> these keys.
"""

_SOURCE = "Google Weather API (snapshot 2026-09-10, not live)"

_DEMO_DATA = {
    "chennai": {
        "condition": "cloudy",
        "temp_c": 28,
        "rain_probability_pct": 20,
        "source": _SOURCE,
    },
    "madurai": {
        "condition": "cloudy",
        "temp_c": 27,
        "rain_probability_pct": 35,
        "source": _SOURCE,
    },
    "coimbatore": {
        "condition": "scattered_thunderstorms",
        "temp_c": 24.6,
        "rain_probability_pct": 50,
        "source": _SOURCE,
    },
}


def get_weather(city: str) -> dict | None:
    if not city:
        return None
    return _DEMO_DATA.get(city.lower())
