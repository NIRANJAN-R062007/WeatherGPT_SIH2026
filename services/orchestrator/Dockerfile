# Build from the repo root, not this directory — config.py's REPO_ROOT is
# derived from this file's own path depth (parents[2]) and reads
# data/cities.json, data/decoders/ and data/fixtures/google_weather/, all of
# which live outside services/orchestrator/. Building from orchestrator/ alone
# breaks that path and every DATA_DIR-relative lookup at startup.
#
#   docker build -f services/orchestrator/Dockerfile -t weathergpt-orchestrator .
#   docker run --env-file .env -p 8001:8001 weathergpt-orchestrator

FROM python:3.11-slim

WORKDIR /app

COPY services/orchestrator/requirements.txt services/orchestrator/requirements.txt
RUN pip install --no-cache-dir -r services/orchestrator/requirements.txt

COPY services/orchestrator services/orchestrator
COPY data data

WORKDIR /app/services/orchestrator

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
