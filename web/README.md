# `web/` — WeatherGPT web frontend (Phase 3, real product)

Standalone, multi-page web frontend for the real WeatherGPT product (plan.md §8
Phase 3 "Web dashboard", §11 repo layout). Not the hackathon prototype — that
stays frozen in `prototype/frontend/`.

## Stack

Vanilla HTML + CSS + JS (ES modules, `<script type="module">`). No bundler, no
framework, no npm. The only external resource is Google Fonts (already used by
the prototype). A build step would have to earn its place against "keep it
minimal", and nothing here needs one.

## Pages — each one a different layout, not one template

| Page | File | Layout idea | Backend calls |
|---|---|---|---|
| Ask | `index.html` | Narrow reading column: query bar + transcript; every answer ends in a receipt-style provenance strip (source · issued IST · live/snapshot · validator m/n) with an expandable evidence table (figure → matched reading) | `GET /cities`, `GET /ask` |
| Dashboard | `dashboard.html` | Dark monitoring board, three city columns side by side: hero temperature, stat tiles (feels-like / humidity / wind / UV), chance-of-rain meter, tomorrow high/low, IMD status chip | `GET /cities`, `GET /facts` ×3 per city, `GET /warnings` per city |
| Warnings | `warnings.html` | Bulletin: colour-code legend, then one full-width severity band per city (stripe + icon + colour label, headline, category, advice, validity window in IST, issuing authority), sorted red → green; quiet empty state when nothing is in force | `GET /cities`, `GET /warnings` per city |
| Settings | `settings.html` | Small two-column form: language (5), °C/°F, backend connection check, and a four-step grounding explainer for the jury | `GET /livez` |

Shared: `css/base.css` (tokens, fonts per language, nav shell, state
components), `js/api.js` (backend base URL + fetch with timeout), `js/prefs.js`
(language + unit in `localStorage`), `js/i18n.js` (all UI strings in
en/hi/ta/te/mr), `js/shell.js` (nav, language switcher, `<html>` font class),
`js/format.js` (IST timestamps, °C/°F, IMD status vocabulary).

## Data flow

- **Backend pointing, config-free.** `js/api.js` uses the same origin by default
  (relative `/facts`, `/ask`, …) and `?apiBase=http://host:port` overrides it, the
  same idea as the prototype's `baseUrl()`. Nav links carry `apiBase` along so
  the override survives page changes. The orchestrator serves this folder at
  `/web/` so `http://127.0.0.1:8001/web/` works with no override at all.
- **No mock data.** Every figure on every page comes from the running backend.
  Fields in `/facts` are absent (not null) when unavailable — every access is
  guarded and renders as "not available".
- **Grounding on the Ask page is never hidden.** Each grounded answer shows
  source, issue time (IST), live/snapshot badge, validator matched/total and the
  per-figure evidence table. Message-only shapes (unrecognised, unsupported
  city, no data, guardrail refusal) render the backend's own localised message.
- **Units.** The backend is metric-only. °F is a client-side display conversion on
  the Dashboard only; answer text on the Ask page is shown verbatim.
- **IMD status = icon + label + colour**, never colour alone, on every surface.

## Languages and fonts

All five (`en`, `hi`, `ta`, `te`, `mr`) — `SUPPORTED_LANGUAGES` in
`services/orchestrator/i18n.py`. Google Fonts Plus Jakarta Sans (Latin) plus
Noto Sans Tamil / Devanagari / Telugu, applied per language exactly like the
prototype (`.ta`, `.hi,.mr`, `.te` classes, set on `<html>`). Strings reused from
the prototype were native-speaker reviewed; strings new to this frontend are
careful direct translations flagged `nativeQa: false` in `js/i18n.js` and
should get the same QA pass as `data/i18n/glossary.json`.

## Run locally

```sh
# backend (fixtures mode, warning fixtures on)
cd services/orchestrator
WEATHER_MODE=fixtures WARNINGS_ENABLED=1 ../../.venv/Scripts/python -m uvicorn main:app --port 8001
# then open http://127.0.0.1:8001/web/            (same origin, no override)
# or serve the folder separately:
cd web && python -m http.server 5173
# and open http://127.0.0.1:5173/?apiBase=http://127.0.0.1:8001
```

## Verification

- `web/tests_e2e_web.py` — pytest + Playwright: spawns the orchestrator in
  fixtures mode with `WARNINGS_ENABLED=1`, serves `web/` with `http.server`,
  drives every page through `?apiBase=` (all http, so no route proxying).
  `.venv/Scripts/python -m pytest web/tests_e2e_web.py -v`
- Screenshots at 1280 px and 390 px in en/hi/te for all four pages were taken
  with headless Chromium and inspected for overflow, clipped Indic script and
  contrast (see the PR/report; they are not committed).
- `ruff check web/tests_e2e_web.py` (line length 100).

## Out of scope for v1

Voice (`/asr`, `/tts`) and Supabase sign-in / history (`/me`, `/history`) — both
remain available in the prototype page and can be ported once the Flutter app
settles the shared auth flow.
