# WeatherGPT — Team Techtonics

**Smart India Hackathon 2026 · PS ID SIH26068 · MoES / India Meteorological Department · Disaster Management**

[![CI](https://github.com/NIRANJAN-R062007/WeatherGPT_SIH2026/actions/workflows/ci.yml/badge.svg)](https://github.com/NIRANJAN-R062007/WeatherGPT_SIH2026/actions/workflows/ci.yml)
[![Security](https://github.com/NIRANJAN-R062007/WeatherGPT_SIH2026/actions/workflows/security.yml/badge.svg)](https://github.com/NIRANJAN-R062007/WeatherGPT_SIH2026/actions/workflows/security.yml)

WeatherGPT is a multilingual weather assistant you can talk to. Ask it about the weather in **English, Hindi, Tamil, Telugu or Marathi** from the mobile app, the web app or a phone call, and it answers in plain language.

The key rule: **the LLM routes questions, the data answers them.** Every number in an answer comes from a real Google Weather API response, and a validator rejects any answer that contains a number the data doesn't back up.

> Example: "Will it rain in Madurai tomorrow?" → *"Tomorrow in Madurai there is a 70% chance of rain, with a high of 34°C."*
> Source: Google Weather API — Daily Forecast, issued 08:30 IST · Validator: 2/2 figures matched

---

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Project status](#project-status)
- [Team](#team)
- [Further reading](#further-reading)

---

## Features

| Feature | What it does |
|---|---|
| **Grounded answers** | Every figure is checked against the raw weather data before it reaches the user. If the LLM's answer doesn't match, it is regenerated once, then replaced with a fixed template answer. |
| **Provenance on every answer** | Each answer says which data product it came from, when it was issued, and whether it is live or cached. |
| **Five languages** | English, Hindi, Tamil, Telugu and Marathi as text, with voice input and output through [Bhashini](https://bhashini.gov.in). |
| **Many channels** | Flutter mobile app, React web dashboard, HTML demo page, and an IVR phone line (Exotel). |
| **Weather Intelligence Engine** | Rule-based, no LLM: finds the **best time window** for an activity, compares **what-if** times ("5 PM vs 9 AM"), and gives **persona advice** (farmer, traveller, general…). |
| **Personas** | General citizen, farmer, fisherman, aviation, city official and traveller. Same data, framed for each user. Each persona also sets the app's colour theme. |
| **IMD-style warnings** | Red / Orange / Yellow / Green warning levels with official category text in all five languages. |
| **Aviation briefing** | Decodes live METAR and TAF reports for the eight demo airports into plain language. |
| **Accounts** | Email sign-in, Google sign-in (mobile), password reset, profile editing and guest mode, using Supabase. |
| **Works without the network** | `OFFLINE_MODE=1` uses saved weather snapshots, a local Llama model and template answers, as a backup if the venue network fails. |

Supported cities: Chennai, Madurai, Coimbatore, Bengaluru, Hyderabad, Mumbai, Delhi, Thiruvananthapuram.

---

## How it works

```
User (app · web · phone call)
   ↓
API gateway (FastAPI) — rate limits, request size cap, proxy
   ↓
Orchestrator
   1. NLU         question → { intent, city, day, language }   (rules first, LLM if needed)
   2. Router      intent → the right Google Weather API call   (cached in Redis)
   3. Engine      best window / what-if / persona rules         (no LLM)
   4. Narration   LLM writes a sentence from the facts only     (Gemini → Groq → local Llama)
   5. Guardrail   every number must exist in the facts          (fail → retry → template)
   6. Translate   Bhashini, then the guardrail checks again
   ↓
Answer + provenance + "n/n figures matched"
```

If every LLM is down, the user still gets a correct template answer. If the weather API is down, the user gets cached data labelled with its age, never presented as current.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI (gateway + orchestrator) |
| LLMs | Gemini (primary), Groq `gpt-oss-120b` (fallback), Ollama `llama3.2:3b` (offline) |
| Languages and voice | Bhashini ASR / TTS / translation |
| Weather data | Google Weather API (current, hourly, daily, recent history); NOAA aviationweather.gov (METAR/TAF) |
| Storage | Redis (cache, shared rate limits), PostgreSQL (weather snapshots, alert subscriptions), Supabase (accounts, history) |
| Mobile | Flutter (Android / iOS) |
| Web | Vite + React + TypeScript + Tailwind |
| Phone | Exotel IVR |
| Infrastructure | Docker Compose, Kubernetes (kustomize), Prometheus + Grafana, k6 load tests |
| CI | GitHub Actions: ruff, pytest, web type-check/lint/build, manifest checks, gitleaks, pip-audit, npm audit, Trivy |

---

## Repository layout

```
.
├── services/
│   ├── gateway/            FastAPI reverse proxy (port 8000)
│   └── orchestrator/       the core: NLU, router, guardrail, narration, Bhashini,
│                           weather_intelligence/, IVR, alerts, aviation (port 8001)
├── mobile/                 Flutter app
├── web/                    React dashboard
├── prototype/frontend/     the HTML demo page (deployed on AWS Amplify)
├── data/                   cities, decoders, i18n glossary, IMD reference text, fixtures
├── ml/                     NLU evaluation set (5 languages) and Bhashini checks
├── k8s/                    Kubernetes manifests
├── monitoring/             Prometheus config and Grafana dashboard
├── loadtest/               k6 load and abuse tests, with results
├── discord-notifier/       Amplify build status → Discord
├── docker-compose.yml
└── plan.md                 full project plan, task list and decisions
```

Each of `mobile/`, `web/`, `prototype/`, `k8s/` and `loadtest/` has its own README with more detail.

---

## Getting started

### Prerequisites

- Python 3.11+
- Docker (optional, for the full stack)
- Node.js 22 (for `web/`)
- Flutter 3.47.x (for `mobile/`)
- API keys: Google Weather API (required for live data), plus Gemini, Groq and Bhashini (optional; without them answers use templates)

### 1. Configure

```bash
cp .env.example .env
# fill in GOOGLE_WEATHER_API_KEY and any LLM / Bhashini keys you have
```

No keys? Set `WEATHER_MODE=fixtures` to use the saved weather snapshots in `data/fixtures/`.

### 2a. Run with Docker

```bash
docker compose up --build
```

Starts Postgres, Redis, the orchestrator and the gateway. Optional profiles:

```bash
docker compose --profile offline up      # adds a local Ollama model
docker compose --profile monitoring up   # adds Prometheus (:9090) and Grafana (:3000)
```

### 2b. Run with Python

```bash
python -m venv .venv
.venv/bin/pip install -r services/orchestrator/requirements.txt -r services/gateway/requirements.txt

# terminal 1: orchestrator, also serves the demo page at /
cd services/orchestrator
FRONTEND_DIR=../../prototype/frontend ../../.venv/bin/uvicorn main:app --reload --port 8001 --no-proxy-headers

# terminal 2: gateway
cd services/gateway
../../.venv/bin/uvicorn main:app --reload --port 8000 --no-proxy-headers
```

(On Windows, use `.venv\Scripts\` instead of `.venv/bin/`.)

Open <http://localhost:8000/>, or try the API:

```bash
curl "http://localhost:8001/health"
curl "http://localhost:8001/ask?text=what's the weather in Chennai&lang=en"
curl "http://localhost:8001/ask?text=will it rain in Madurai tomorrow&lang=ta"
curl "http://localhost:8001/intelligence/best-window?city=chennai&day=tomorrow&activity=outdoor"
```

### 3. Web app

```bash
cd web
npm ci
npm run dev        # VITE_API_BASE_URL defaults to http://localhost:8001
```

### 4. Mobile app

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001   # Android emulator → local orchestrator
```

---

## Configuration

All settings live in `.env` (see `.env.example` for the full list with comments). The main ones:

| Variable | Purpose |
|---|---|
| `GOOGLE_WEATHER_API_KEY` | Live weather data |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | LLM narration and NLU |
| `OLLAMA_BASE`, `OLLAMA_MODEL` | Local fallback model |
| `BHASHINI_USER_ID`, `BHASHINI_ULCA_API_KEY` | Translation and voice |
| `WEATHER_MODE` | `auto` (live, falls back to fixtures) · `live` · `fixtures` |
| `OFFLINE_MODE` | `1` = fixtures + local Ollama only (demo backup) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Accounts and query history |
| `ALLOWED_ORIGINS` | CORS allow-list |
| `RATE_LIMIT_PER_MINUTE`, `TRUSTED_PROXY_HOPS` | Per-client rate limiting |
| `WARNINGS_ENABLED`, `IVR_ENABLED`, `ALERT_ENGINE_ENABLED` | Feature switches (off by default) |

Never commit `.env`; it is gitignored, and CI runs gitleaks on every push.

---

## Testing

```bash
.venv/bin/pytest services/orchestrator/tests/ -v
.venv/bin/pytest services/gateway/tests/ -v
python ml/nlu/run_eval.py                 # NLU accuracy over the 5-language eval set

cd web && npm run build && npm run lint
cd mobile && flutter analyze && flutter test
```

Tests block real network calls and use the saved fixtures, so they run without API keys.

---

## Deployment

| Part | Where |
|---|---|
| Demo page (`prototype/frontend/`) | AWS Amplify (`amplify.yml`) |
| Backend (gateway + orchestrator) | Live at `https://3-108-52-61.sslip.io` |
| Container images | Published to GHCR by CI on every push to `main` |
| Kubernetes | `k8s/base/` (validated in CI; see `k8s/README.md` for a kind quick-start) |

---

## Project status

**Working:** grounded `/ask` in five languages, voice (ASR/TTS), the guardrail and provenance, best window / what-if / persona advice, aviation briefing, mobile and web apps with accounts, monitoring, load tests, security CI.

**Limitations, stated openly:**

- **Warnings use simulated data.** The official NDMA/SACHET CAP feed isn't connected yet, so warnings come from fixtures and are labelled *"Simulated data — pending official feed access"*.
- **IVR is built but not live.** The Exotel number is waiting on KYC; a simulated call path (`ivr_simulate.py`) is used for demos.
- **Forecast change detection** ("what changed since this morning?") is not built yet.
- **WhatsApp bot, cyclone map and climate trends** are on the roadmap.
- **LLM-path latency:** p95 measured at 8.3 s on free-tier keys (target 2 s). The template path is p95 16 ms at 150 req/s.

The full task list and history are in [`plan.md`](plan.md).

---

## Team

**Team Techtonics**

| Role | Member |
|---|---|
| Team Lead | Surya Deepthi |
| Backend Architect · Language / Voice Engineer | Niranjan |
| Data / Met Engineers | Syed, Deepthi |
| AI / LLM Engineer | Mahesh |
| Mobile Developer | Chelsea |
| Frontend / Web | Mahesh, Chelsea |
| DevOps | Mahesh, Niranjan |
| Security Engineer | Abel |

---

## Further reading

- [`plan.md`](plan.md): architecture, design principles, task list and risks
- [`prototype/README.md`](prototype/README.md): backend internals, `/ask` response format, offline mode, monitoring
- [`mobile/README.md`](mobile/README.md) · [`web/README.md`](web/README.md) · [`k8s/README.md`](k8s/README.md) · [`loadtest/README.md`](loadtest/README.md)

Weather data: Google Weather API. Language services: Bhashini, Government of India.
