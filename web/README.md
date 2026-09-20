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
messages, glossary text) is already native-QA'd upstream and rendered
verbatim — the frontend does not re-translate it. The ~25 UI-chrome strings
below were authored directly in `src/i18n/strings.ts` (nav labels, form
labels, error/notice copy, settings copy) and are flagged `nativeQa: false`
for hi/te/mr pending native-speaker review, matching the convention used in
`services/orchestrator/i18n.py` and `data/i18n/glossary.json`:

- Nav labels: Ask, Dashboard, Warnings, Settings
- `askTitle`, `askPlaceholder`, `askSubmit`, `cityFromQuestion`, `city`
- `wind`, `alert`, `noWarningBody`, `valid`, `unknownCity`
- `loading`, `retry`, `errNetwork`, `errTimeout`, `errRate`, `errHttp`
- `templateAnswer`, `fixtureData`, `liveData`, `notReported`
- `language`, `defaultCity`, `saved`, `aboutData`, `cityImage`, `notFound`

Tamil (`ta`) is marked `nativeQa: true` since it follows the same
hand-checked convention as the Tamil strings in `i18n.py`. All other
strings in `strings.ts` (condition-table labels, glossary colour text,
example queries) are copied verbatim from already-reviewed backend source
files, cited inline as comments.
