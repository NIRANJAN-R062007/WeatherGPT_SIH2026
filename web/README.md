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

## Authored Indic strings awaiting native QA

Everything the API returns (condition names, warning headlines, refusal
messages, glossary text) is rendered verbatim — the frontend does not
re-translate it, and it does not keep its own copy: the warning colour
words, colour meanings and category labels come from
`data/i18n/glossary.json` via `/warnings` (`legend`, `warning.colour_label`,
`warning.category_label`) and `/glossary`, so that text has one source, not
three. The ~26 UI-chrome strings below were authored directly in
`src/i18n/strings.ts` (nav labels, form labels, error/notice copy, settings
copy) and are flagged `nativeQa: false` for hi/te/mr pending native-speaker
review, matching the convention used in `services/orchestrator/i18n.py` and
`data/i18n/glossary.json`:

- Nav labels: Ask, Dashboard, Warnings, Settings
- `askTitle`, `askPlaceholder`, `askSubmit`, `cityFromQuestion`, `city`
- `wind`, `alert`, `warningsUnavailable`, `noWarningBody`, `valid`, `unknownCity`
- `loading`, `retry`, `errNetwork`, `errTimeout`, `errRate`, `errHttp`
- `templateAnswer`, `fixtureData`, `liveData`, `notReported`
- `language`, `defaultCity`, `saved`, `aboutData`, `cityImage`, `notFound`

Tamil (`ta`) is marked `nativeQa: true` since it follows the same
hand-checked convention as the Tamil strings in `i18n.py`; the one
exception is `warningsUnavailable`, authored later without that check. All
other strings in `strings.ts` (condition-table labels, example queries) are
copied verbatim from already-reviewed backend source files, cited inline as
comments.

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
