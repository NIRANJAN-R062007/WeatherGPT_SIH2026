import os

import redis
from fastapi import FastAPI
from sqlalchemy import create_engine, text

app = FastAPI(title="WeatherGPT Gateway", version="0.0.1")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://weathergpt:weathergpt_dev@localhost:5432/weathergpt")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

engine = create_engine(DATABASE_URL)
redis_client = redis.Redis.from_url(REDIS_URL)


@app.get("/")
def root():
    return {"service": "WeatherGPT Gateway", "status": "running"}


@app.get("/health")
def health():
    """Verifies the gateway can reach Postgres+PostGIS and Redis.
    This is the Phase 0 smoke test — if this returns all 'ok', the skeleton is real."""
    status = {"postgres": "unknown", "postgis": "unknown", "redis": "unknown"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            status["postgres"] = "ok"
            postgis_version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            status["postgis"] = f"ok ({postgis_version})"
    except Exception as e:
        status["postgres"] = f"error: {e}"
        status["postgis"] = "error"

    try:
        redis_client.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"

    return status
