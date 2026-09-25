# WeatherGPT — Web (Stitch import)

The main WeatherGPT website UI, imported from the team's Google Stitch project
("WeatherGPT AI Weather Assistant") via the Stitch MCP server and rebuilt as a
proper Vite + React + TypeScript + Tailwind app.

**Status: frontend only.** Every screen renders with the realistic sample
content Stitch generated inline (city, forecast figures, alerts, history —
literal text in each page component, not fetched). Nothing calls the
orchestrator's `/ask` API yet — that wiring (real weather data, the
grounding/evidence panel backed by real tool responses, language switching
backed by `data/i18n/`) is a follow-up pass, not part of this import.

Navigation is real (`react-router-dom`, one route per sidebar item). The
language pills and °C/°F toggle in the top bar and Settings are wired to
real React state (`src/state/UiPrefsContext.tsx`) and visibly track a
selection — but every temperature/figure on the Stitch-sourced pages is
still literal mock text, so toggling °F doesn't yet recompute the "29°" on
the Home hero or any other number. Wiring that (and real translation) needs
the pages to read from live data instead of hardcoded strings, which is the
same follow-up pass as the `/ask` integration above.

## Pages

| Route | Screen | Stitch source |
|---|---|---|
| `/` | Home dashboard | Home Dashboard - WeatherGPT |
| `/chat` | Chat & Evidence | Chat & Evidence - WeatherGPT |
| `/forecast` | Forecast | Forecast - WeatherGPT |
| `/alerts` | Alerts & Warnings | Alerts & Warnings - WeatherGPT |
| `/history` | History | History - WeatherGPT |
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
npm run dev      # http://localhost:5181
npm run build    # tsc -b && vite build
```
