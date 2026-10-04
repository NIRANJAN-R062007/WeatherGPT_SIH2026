# Crop file (`crops.json`)

The sowing advisory (`POST /advisory/sowing`, plan.md §11.7) reads its crop
thresholds from `crops.json` in this folder. The file is **TFA-9** (drafted
from TNAU Agritech, ICAR/KVK crop calendars and IMD GKMS advisories) and is
not written yet: until it is, every crop answers "not available".

The reader is `services/orchestrator/advisory/crops.py`. This is the format
it expects:

```json
{
  "entries": [
    {
      "crop": "groundnut",
      "region": "madurai",
      "reviewed": false,
      "values": {
        "sowing_months": {
          "value": [6, 7],
          "source": "TNAU Agritech Portal, Groundnut",
          "url": "https://...",
          "quote": "the exact sentence the value is taken from"
        },
        "temp_range_c": {
          "value": {"min": 20, "max": 30},
          "source": "...", "url": "...", "quote": "..."
        },
        "max_rain_probability_pct": {
          "value": null,
          "source": "...", "url": "...", "quote": "..."
        }
      }
    }
  ]
}
```

- `crop` is a key of `advisory/slots.py` `CROPS` (groundnut, rice, wheat,
  maize, cotton, sugarcane, ragi). Other crops are ignored.
- `region` is a district key from `data/cities.json` (`madurai`) or a state
  slug (`tamil_nadu`). A district entry wins over its state's entry.
- Every value needs a non-empty `source` and a verbatim `quote`. A value
  without them is ignored and logged. If a source does not give a value,
  write `null`: never fill one in.
- `sowing_months`: month numbers 1-12. Outside them the answer is "not
  suitable". If it is `null`, the season is not checked, and the answer says
  so.
- `temp_range_c`: for "suitable", the first three forecast days must stay
  inside the temperature range. **Required**: without it, the crop answers
  "not available" rather than guessing.
- `max_rain_probability_pct`: **optional**, since agronomy sources rarely give
  a rain-chance limit. When given, the first three days' rain chance must stay
  below it, and today's best sowing hours are scored against it and the
  temperature range; without it there is no hourly window.
- Heavy rain needs no entry: for every crop, a day in the first three whose
  rain is in IMD's "heavy" band or above (64.5 mm/day,
  `data/decoders/precipitation_categories.json`) is "not suitable", as IMD's
  agromet bulletins advise postponing sowing in heavy rain. A day with no
  rain amount is "not available".
- `reviewed`: `true` only after the agronomy sign-off (plan.md §11.9). Until
  then every answer says the thresholds have not been reviewed.

Checking each number against its quote is the validator's job (TFA-10).
