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

## Run it

```bash
cd web
npm install
npm run dev      # http://localhost:5181
npm run build    # tsc -b && vite build
```
