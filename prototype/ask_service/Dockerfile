# Build from the repo root, not this directory — config.py's REPO_ROOT is
# derived from this file's own path depth (parents[2]) and reads
# data/cities.json, data/decoders/ and data/fixtures/google_weather/, all of
# which live outside prototype/ask_service/. Building from ask_service/ alone
# breaks that path and every DATA_DIR-relative lookup at startup.
#
#   docker build -f prototype/ask_service/Dockerfile -t weathergpt-ask-service .
#   docker run --env-file .env -p 8001:8001 weathergpt-ask-service

FROM python:3.11-slim

WORKDIR /app

COPY prototype/ask_service/requirements.txt prototype/ask_service/requirements.txt
RUN pip install --no-cache-dir -r prototype/ask_service/requirements.txt

COPY prototype/ask_service prototype/ask_service
COPY data data

WORKDIR /app/prototype/ask_service

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
