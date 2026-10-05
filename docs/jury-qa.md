# Jury Q&A and pitch wording

Wording the whole team uses on the slides, in the jury Q&A and in the closing pitch.
Every claim here must stay true against `plan.md`; update this file when the plan changes.

## Data sources: "Google for weather, CAP/SACHET for alerts, by design" (Phase 7 B1)

Sources in `plan.md`: §3.1 (Google Weather API), §3.3 (alerts and the data-source split), R1b and R9 (§9).

### PPT slide (one line plus three bullets)

**Weather from Google. Warnings from the government. Never mixed.**

- **Weather facts** (current conditions, hourly and daily forecast, recent rain) come only from the Google Weather API.
- **Warnings and alerts** come only from CAP (Common Alerting Protocol) messages through NDMA's SACHET, India's official alert aggregator.
- Airport reports (METAR/TAF) come from NOAA's aviationweather.gov, decoded word for word.

### Jury Q&A

**Q: Why not take warnings from Google, since you already use its weather API?**
Google's weather API has no warnings product, and that's a deliberate boundary for us. A warning in India has to be the official one: the IMD category, the colour and the area NDMA sent. So we split the sources on purpose. Google answers "what will the weather be", and only the government's CAP feed answers "is there a warning". Our model never turns a forecast into a warning, and it never words a warning more loosely than the official text.

**Q: Are the warnings in the demo real?**
Not yet. The SACHET/NDMA access request is still open, so every warning in the demo comes from hand-written sample data. Each one is labelled on screen and in the API response with the exact text **"Simulated data — pending official feed access"**, and a test in CI fails if that label is ever missing. The CAP parser and the alert engine are built, so moving to real warnings means switching the source, not rebuilding the feature.

**Q: What happens if someone sends a fake warning?**
SACHET's CAP messages carry no digital signature, so we can't verify an alert by its signature. Instead we fetch alerts only over HTTPS from SACHET's own address and check every message before it can reach a user (Phase 8, SEC-A1/A2). A fake cyclone warning is the worst failure this product could have, so the alert engine stays off on public hosts until real feed access and these checks are in place.

**Q: What about cyclone tracks, floods and marine bulletins?**
Neither Google nor the warnings feed covers these as data we can use, so we don't answer them yet. The assistant says such questions are out of scope instead of guessing. We've listed candidate official sources (IMD RSMC cyclone bulletins, INCOIS ocean-state alerts, CWC flood forecasts) as roadmap items, not features.

### Closing pitch (about 20 seconds)

> Every number WeatherGPT says comes from a real Google Weather API response, and a validator checks it before the user hears it. Every warning comes only from the government's official alert channel, never from a forecast and never from the model. Until we have official access, our warnings say "Simulated data — pending official feed access" in plain sight. Where the data stops, we say so. That's the line we hold: the data answers, and the government warns.
