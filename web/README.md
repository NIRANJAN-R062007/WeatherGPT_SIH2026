# WeatherGPT — Web (Stitch import)

The main WeatherGPT website UI, imported from the team's Google Stitch project
("WeatherGPT AI Weather Assistant") via the Stitch MCP server and rebuilt as a
proper Vite + React + TypeScript + Tailwind app.

**Status (2026-10-03): live, and level with the mobile app.** Every page
reads the orchestrator (`VITE_API_BASE_URL`), in the five app languages;
the Stitch sample content is gone from the main pages (History is still
the static mock, reachable from the sidebar only).

## Personas, themes and accounts (2026-09-29)

The site now mirrors the mobile app (`mobile/`), and the look follows
the pics/ persona mockups:

- **Persona = app-wide theme.** The persona picked on `/persona` sets
  every colour through CSS custom properties. General Citizen is blue,
  Farmer green, Fisherman ocean blue, Aviation purple and pink, and City
  Official teal. The palettes are in `src/theme/personaTheme.ts`, and
  `tailwind.config.js` maps the colour names onto the variables. Every
  persona has a light and a dark palette, switched under Settings >
  Appearance (Light / Dark / System). Persona and appearance are kept in
  localStorage.
- **Painted scenery.** City, fields, sea, airport and civic scenes are
  drawn on `<canvas>` by `src/components/scenery/`, a port of mobile's
  `scenery.dart` painters.
- **Accounts.** Email and password sign-in on the team's Supabase
  project (`src/lib/auth.ts`, overridable with `VITE_SUPABASE_URL` /
  `VITE_SUPABASE_ANON_KEY`). There is a landing page, sign in / create
  account (name, email, phone, occupation), a Profile page with Sign out,
  and "Continue as guest". The session is kept in localStorage.
- **Live data.** Home and Forecast read `GET /facts`, `/forecast/daily`
  and `/forecast/hourly`. Chat asks `/ask` with the persona. Alerts reads
  `/warnings`, `/glossary` and `/hotlines`.

## Mobile parity (2026-10-03)

The site caught up with the app's work since 2026-10-01:

- **Forecast detail.** Forecast is "Days | Hourly": up to 10 days (open a
  day for rain, rainfall, wind, humidity, UV, daylight, sun times and its
  night) and the next 24 hours under a temperature curve. Home has Rain so
  far and Daylight cards and a five-day strip. A backend without the
  forecast routes still gets the /facts rows.
- **Alerts.** Emergency numbers from `/hotlines` as tel: links (112
  always), and the colour legend from `/glossary`, marked when a
  translation hasn't had native review.
- **Travel and Sowing advice** (`/travel` for everyone, `/sowing` for the
  Farmer persona), a short conversation over `POST /advisory/*`.
- **Location answers.** "Place not found" offers the nearest place, "which
  place?" offers Use my location; the browser fix is sent snapped to the
  0.05° grid (~5 km).
- **Offline.** Public replies are saved in localStorage
  (`src/lib/responseCache.ts`, never /ask or History) and shown under a
  "Showing saved data" banner when the backend can't be reached, trimmed
  to what still holds; the weather data retries every minute.
- **Accessibility.** axe-core (WCAG 2.1 AA) is clean on Home, Forecast,
  Alerts, Travel and Chat for all five personas, light (Hindi) and dark:
  the idle bottom-bar colours were darkened as on mobile, and `text-outline`
  is no longer used for text. Nothing overflows at 320 px (200% zoom) in
  Tamil. Forecast rows and hours have spoken sentences; the hotlines read
  "Call …, …". Every font falls back to the self-hosted Noto Indic faces,
  so mono and headline text no longer shows empty boxes in hi/mr/te/ta.
- **Tests.** Vitest covers the lib/ logic (`npm test`, 23 tests), and the
  CI web job runs it.

## Pages

| Route | Screen | Stitch source |
|---|---|---|
| `/` | Home dashboard | Home Dashboard - WeatherGPT |
| `/chat` | Chat & Evidence | Chat & Evidence - WeatherGPT |
| `/forecast` | Forecast | Forecast - WeatherGPT |
| `/alerts` | Alerts & Warnings | Alerts & Warnings - WeatherGPT |
| `/history` | History | History - WeatherGPT |
| `/best-window` | Best Time & What-if | hand-built |
| `/travel` | Travel advice | hand-built (mobile advisory_page.dart) |
| `/sowing` | Sowing advice (Farmer only) | hand-built (mobile advisory_page.dart) |
| `/aviation` | Airport weather (Aviation only) | hand-built |
| `/settings` | Settings | hand-built — no Settings screen existed in the Stitch project yet, so this one only reuses the shared design tokens/components |

## Design system

Colors, type scale, spacing and radii in `tailwind.config.js` are copied
verbatim from the Stitch project's generated Tailwind config (a Material
Design 3 token set — `primary`, `on-surface`, `surface-container-*`, etc.),
so any screen pulled from Stitch later drops in without a palette mismatch.
Icons are Google's Material Symbols Outlined font. Every font (Inter,
Plus Jakarta Sans, JetBrains Mono, Material Symbols Outlined) and every
hero/illustrative photo is self-hosted under `public/fonts/` and
`public/images/` rather than fetched from `fonts.googleapis.com` or
Stitch's `lh3.googleusercontent.com/aida...` asset URLs at runtime — those
Stitch preview URLs aren't guaranteed to stay up long-term, and a
same-origin app has no external font/image dependency at all (plan.md
§2.5, "offline-degradable"). The sidebar logo and header avatar were
replaced with plain CSS placeholders rather than downloaded, since those
are brand-identity elements worth designing on purpose rather than
inheriting from a generated mockup. `public/fonts/material-symbols-outlined.woff2`
is the full ~4 MB variable icon font (every icon, every axis); worth
subsetting to just the icons this app uses before a real production ship.

Each Stitch export also shipped a page-specific vanilla-JS `<script>` block
(DOM `querySelector`/`addEventListener` wiring for things like the evidence
toggle or the SOS button). Those don't fit a React tree and were dropped;
the static markup they targeted is preserved, so a future pass replaces
them with real React state instead of re-adding raw DOM scripts.

## Density pass (first round)

Stitch's export leaned maximalist — every page surfaced verification
badges, station metadata, and debug-style telemetry (SHA-256 hashes, JSON
field paths, session IDs) all at once, at equal visual weight to the actual
answer. First cleanup pass:

- **Chat & Evidence**: the "Telemetry Inspector" / "Verified Observation
  Pipeline" panel (hashes, JSON paths, station IDs) is now hidden by
  default and opens via the "View Raw JSON Evidence" button
  (`showEvidence` state in `ChatPage.tsx`) instead of always rendering in
  the sidebar.
- **Alerts & Warnings**: the "Why am I receiving this alert?" accordion
  now actually toggles (`showGeofence` state in `AlertsPage.tsx`) — it
  was dead markup before (`id`-based DOM script Stitch generated was
  dropped when this became React, per the note above).
- Redundant badges collapsed across Home/Chat/Alerts (e.g. station
  ID/lat-lon/session ID that repeated info already in the page, or
  4 stacked verification pills where 1-2 said the same thing); the
  detail isn't gone, it moved to a `title` tooltip.
- Home hero's six-stat grid and top status line lost their always-on
  secondary caption text (dew point, heading, swell band, etc.) the same
  way — tooltip on hover instead of permanent small print.
- Home's right rail lost a static "AI synthesizing..." preview card that
  duplicated the actual Chat page's job, and one of three quick-inquiry
  buttons.

Not yet touched: rewriting the bold-heavy answer prose in Chat's response
text, and the Forecast/History pages (same Stitch-generated density likely
applies — carry the same pattern over on the next pass).

## Run it

```bash
cd web
npm install
npm run dev      # http://localhost:5181 (API_PROXY_TARGET to proxy /api)
npm run build    # tsc -b && vite build
npm test         # Vitest, the lib/ unit tests
npm run lint     # oxlint
```
