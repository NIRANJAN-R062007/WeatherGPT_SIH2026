"""STUB — stand-in for the real Google Weather API ingestion module.

Owned by Syed + Deepthi in plan.md §14. Swap get_weather() for their module
once it lands; this only exists so the /ask endpoint has something to call.
"""

_DEMO_DATA = {
    "chennai": {
        "condition": "partly_cloudy",
        "temp_c": 31,
        "rain_probability_pct": 20,
        "source": "Google Weather API (demo fixture, not live)",
    },
}


def get_weather(city: str) -> dict | None:
    return _DEMO_DATA.get(city.lower())
