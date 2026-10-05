"""WIE-12: write a labelled sample "earlier forecast" per demo city into
data/fixtures/forecast_snapshots/, so forecast change detection can be shown
offline (WEATHER_MODE=fixtures), where the committed hourly fixture is the only
forecast there is.

Each sample is the city's committed forecast_hours fixture, retrieved 6 hours
earlier, with the chance of rain moved by 30 points over its 5th to 7th hours
(down where today's figure is 30% or more, so the answer says it "rose"; up
otherwise, so it "fell"). Every other figure is copied unchanged. The file says
it is a sample, and so does every answer built on it (forecast_snapshots.sample).

Rerun after refreshing the hourly fixtures (snapshot_google_weather.py), since a
sample only compares against the hours it shares with the fixture:

    python services/orchestrator/seed_sample_snapshots.py
"""

import json
from datetime import datetime, timedelta, timezone

import cities
import config
import forecast_snapshots

HOURS_BACK = 6           # how much earlier the sample claims to be
RAIN_SHIFT = 30          # points; above rules.CHANGE_THRESHOLDS' 20
EDITED = slice(4, 7)     # the fixture's 5th to 7th hours: still "today" in every city

LABEL = "SAMPLE: a made-up earlier forecast for offline demos, not a real past forecast"


def build(city_key: str) -> dict:
    path = config.FIXTURES_DIR / "google_weather" / f"forecast_hours.{city_key}.json"
    env = json.loads(path.read_text(encoding="utf-8"))
    rows = forecast_snapshots.rows_from_payload(env["response"])
    edited = []
    for row in rows[EDITED]:
        rain = row["rain_probability_pct"]
        if rain is None:
            continue
        row["rain_probability_pct"] = rain - RAIN_SHIFT if rain >= RAIN_SHIFT else rain + RAIN_SHIFT
        edited.append(row["forecast_time"])
    retrieved = datetime.fromisoformat(env["_meta"]["retrieved_at"]) - timedelta(hours=HOURS_BACK)
    return {
        "_meta": {
            "sample": True,
            "label": LABEL,
            "city": city_key,
            "derived_from": path.name,
            "retrieved_at": retrieved.astimezone(timezone.utc).isoformat(),
            "edited": {"metric": "rain_probability_pct", "shift": RAIN_SHIFT,
                       "forecast_times": edited},
            "produced_by": "services/orchestrator/seed_sample_snapshots.py",
        },
        "rows": rows,
    }


def main() -> None:
    forecast_snapshots.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for key in sorted(cities.CITY_KEYS):
        out = forecast_snapshots.sample_path(key)
        out.write_text(json.dumps(build(key), ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"wrote {out.relative_to(config.DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
