# WeatherGPT web

A dense, IMD-bulletin-style frontend for the WeatherGPT orchestrator API —
current weather, forecasts, warnings and a free-text ask box for Chennai,
Madurai and Coimbatore, in English, Tamil, Hindi, Telugu and Marathi.

## Run

```sh
npm install
npm run dev
```

## Build

```sh
npm run build   # tsc -b && vite build
npm run preview
```

## Lint

```sh
npm run lint    # oxlint
```

## Configuration

- `VITE_API_BASE` — base URL of the orchestrator API. `.env.development`
  points at `http://localhost:8001` for local work; `.env.example` documents
  the key for other environments. The production value is injected at build
  time by the host and is never committed. `src/config.ts` is the only file
  that reads this variable.

## Deployment status

Not deployed, by decision (2026-09-21): `prototype/frontend/WeatherGPT.dc.html`
on Amplify remains the shipped UI, and this app is hosted locally until it is
finished. CI type-checks, lints and builds it on every push (`web` job in
`.github/workflows/ci.yml`). Point `VITE_API_BASE` at a backend per
`web/.env.example` — `http://localhost:8001` for a local orchestrator, or the
live bare deployment the Amplify page uses.

## Authored Indic strings awaiting native QA

Everything the API returns (condition names, warning headlines, refusal
messages, glossary text) is rendered verbatim — the frontend does not
re-translate it, and it does not keep its own copy: the warning colour
words, colour meanings and category labels come from
`data/i18n/glossary.json` via `/warnings` (`legend`, `warning.colour_label`,
`warning.category_label`) and `/glossary`, so that text has one source, not
three. Whether the API's own text has been reviewed is tracked at its
source: the `# TODO: native_qa` markers in `services/orchestrator/i18n.py`
and the per-entry `native_qa` flags the `/glossary` and `/warnings` legend
payloads carry (all `false` for ta/hi/te/mr today).

The only native-speaker review of this project's Indic text happened on
Sep 13 (commit `fce2ad9`) and covered the hi/te/mr strings that
`services/orchestrator/i18n.py` and `main.py` held at that commit. Nothing
in `src/i18n/strings.ts` existed then — the file was authored on Sep 20 —
so **every non-English bundle in it is flagged `nativeQa: false`, Tamil
included** (audit item 4.2; an earlier revision marked Tamil `true` on the
grounds that it followed the same hand-checked convention as the `i18n.py`
Tamil strings, but those were reverse-engineered from real Bhashini output
and these were not). The flag is metadata only; no component reads it. The
~26 UI-chrome strings authored directly in `strings.ts` (nav labels, form
labels, error/notice copy, settings copy) are:

- Nav labels: Ask, Dashboard, Warnings, Settings
- `askTitle`, `askPlaceholder`, `askSubmit`, `cityFromQuestion`, `city`
- `wind`, `alert`, `warningsUnavailable`, `noWarningBody`, `valid`, `unknownCity`
- `loading`, `retry`, `errNetwork`, `errTimeout`, `errRate`, `errHttp`
- `templateAnswer`, `fixtureData`, `liveData`, `notReported`
- `language`, `defaultCity`, `saved`, `aboutData`, `cityImage`, `notFound`

The remaining strings are copied verbatim from backend sources, cited inline
as comments, and inherit those sources' status rather than any review of
their own: `feelsLike` and `humidity` come from `_CURRENT_PHRASES` strings
the Sep 13 review covered (hi/te/mr); `uvIndex` comes from the `uv` phrase
added on Sep 14, which is `# TODO: native_qa` in every non-English language; and
`exampleQueries` come from `ml/nlu/eval_set.jsonl` rows that are flagged
`native_qa: false` for every language but English. Set a bundle's
`nativeQa` to `true` only once a native speaker has confirmed that bundle's
exact text.

Known gap: a warning's `advice` is free text from the feed and arrives in
English whatever the UI language, so the Warnings page labels it
`lang="en"` rather than pretending otherwise.

## Warning states

`/warnings` answers with a `status` (see `imd_warnings.STATUS_*`):
`unavailable` (feed switched off — the default on every deploy — or no data
for the city), `clear` (checked, green) or `active` (yellow/orange/red).
The Warnings page shows `unavailable` as a neutral "warnings aren't
available" notice, never as a green all-clear, and treats a response with
no `status` at all (an older backend) the same way.
