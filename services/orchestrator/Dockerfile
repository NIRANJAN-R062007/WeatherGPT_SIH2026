# Build from the repo root, not this directory — config.py's REPO_ROOT is
# derived from this file's own path depth (parents[2]) and reads
# data/cities.json, data/decoders/ and data/fixtures/google_weather/, all of
# which live outside services/orchestrator/. Building from orchestrator/ alone
# breaks that path and every DATA_DIR-relative lookup at startup.
#
#   docker build -f services/orchestrator/Dockerfile -t weathergpt-orchestrator .
#   docker run --env-file .env -p 8001:8001 weathergpt-orchestrator   # API only
#   docker run --env-file .env -e FRONTEND_DIR=/app/prototype/frontend \
#     -p 8001:8001 weathergpt-orchestrator                             # + the demo page at /

FROM python:3.11-slim

WORKDIR /app

COPY services/orchestrator/requirements.txt services/orchestrator/requirements.txt
RUN pip install --no-cache-dir -r services/orchestrator/requirements.txt

COPY services/orchestrator services/orchestrator
COPY data data
# The demo page main.py serves at `/` — only when FRONTEND_DIR points here
# (docker-compose.yml, render.yaml and k8s/base/configmap.yaml all do); the
# image is API-only without it.
COPY prototype/frontend prototype/frontend

WORKDIR /app/services/orchestrator

EXPOSE 8001

# --no-proxy-headers: a container never sees a 127.0.0.1 peer, so uvicorn's
# default X-Forwarded-For rewrite can't fire here anyway — belt and braces for
# the limiter (limits.py), which reads the header itself.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--no-proxy-headers"]
