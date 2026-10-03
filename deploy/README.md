# Deploying and verifying the bare box (B4)

Target: `https://3-108-52-61.sslip.io`, the backend the Amplify page and the mobile
app talk to. plan.md Phase 7, B4 is done when **a fresh deploy is done, `/health` is
green, an `/ask` smoke test passes in all five languages, and Redis and Postgres
persist across a restart**, all logged in plan.md with the date.

This runbook was written without access to the box. What is known about it comes
from outside (its `/health`, its routes). Anything about how it is started is
marked **check**, and the deploy step (3) is finished only after step 2.

## 1. Record the "before" state (from any machine)

```bash
python deploy/smoke.py https://3-108-52-61.sslip.io
```

Baseline on 2026-10-02: the five `/ask` languages and `/health` pass; six checks
under `[current]` fail (`/cities` lists 3 of 8 cities, `/facts?city=mumbai` is
refused, `/warnings` has no `status`, `/aviation`, `/intelligence/best-window` and
`/glossary` are 404). The box runs an old build (`WeatherGPT /ask prototype 0.0.1`,
before the gateway and the `services/orchestrator` rename). Since 2026-10-03 the
script also checks `/forecast/daily`, `/forecast/hourly`, `/facts`' `rain_so_far`
and `/hotlines` (10 checks under `[current]`; all fail on the old build).

## 2. Look at what is running (on the box, read-only)

Run these and paste the output; none of them change anything.

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
docker compose ls
docker volume ls
ls -la ~ /opt 2>/dev/null
sudo ss -ltnp | grep -E ':(80|443|8000|8001|5432|6379)\b'
systemctl list-units --type=service --state=running | grep -i -E 'caddy|nginx|docker|weather|uvicorn'
```

The questions this answers: is the backend in containers or a bare Python process;
what terminates TLS for `3-108-52-61.sslip.io` (Caddy, nginx, something else) and
where its config is; where the `.env` lives; which of ports 5432 and 6379 are open
to the internet; and whether Postgres and Redis exist at all today.

## 3. Deploy a fresh build of `main` (finish after step 2)

Do not run the repo's `docker-compose.yml` as it is on an internet-facing host. It
is a development file:

- it publishes Postgres (5432) and Redis (6379) on every interface, and Redis has no password;
- the Postgres password is the literal `weathergpt_dev`;
- both services run `uvicorn --reload` and bind-mount the source tree;
- Redis is the stock image with no `appendonly`, so an unclean stop can lose recent keys.

A production file needs: no published database ports, a password from `.env`,
no `--reload` or bind mounts, named volumes for Postgres and Redis, Redis with
`--appendonly yes`, and the app ports bound to `127.0.0.1` behind whatever
terminates TLS. Which of those apply depends on step 2, so write it from that
output rather than from this list.

Before the cut-over:

1. Copy the current `.env` and any database to a safe place (`pg_dump` if one exists).
2. Compare the old `.env` with `.env.example`. New keys since the old build include
   `ALLOWED_ORIGINS`, `TRUSTED_PROXY_HOPS`, `METRICS_TOKEN`, the `DAILY_CAP_*` limits and
   `WARNINGS_ENABLED`. Set `TRUSTED_PROXY_HOPS` to the number of proxies in front of the
   orchestrator (the gateway counts as one), or the rate limiter keys on the wrong address.
3. `git fetch && git checkout main && git pull --ff-only`, then build and start.

## 4. Verify

```bash
# from any machine: all of it must pass
python deploy/smoke.py https://3-108-52-61.sslip.io

# on the box: Redis and Postgres survive a restart
deploy/persistence_check.sh
# the stronger version: containers destroyed and rebuilt, only named volumes survive
MODE=recreate COMPOSE_FILE=<the production compose file> deploy/persistence_check.sh

# from any machine again, after the restart
python deploy/smoke.py https://3-108-52-61.sslip.io
```

`smoke.py` reports Postgres, PostGIS and Redis as `ok` only when the gateway is in
front (the orchestrator's own `/health` does not report them). If the box serves
the orchestrator alone, that line is `INFO`, and `persistence_check.sh` is the
evidence for Redis and Postgres.

`persistence_check.sh` was tested against a stand-in `docker` command (a clean run
and four data-loss cases), not against a real Docker. Treat its first run on the box
as part of the verification.

## 5. Log it

Tick B4 in plan.md only after step 4 passes on the box, and paste in: the date, the
commit that was deployed (`git rev-parse --short HEAD`), the `smoke.py` summary line,
the `persistence_check.sh` result, and what was not checked.
