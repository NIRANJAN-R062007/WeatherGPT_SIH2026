# Deploying and verifying the bare box (B4)

Target: `https://3-108-52-61.sslip.io`, the backend the Amplify page and the mobile
app talk to. plan.md Phase 7, B4 is done when **a fresh deploy is done, `/health` is
green, an `/ask` smoke test passes in all five languages, and Redis and Postgres
persist across a restart**, all logged in plan.md with the date.

This runbook was written without access to the box. What is known about it comes
from outside (its `/health`, its routes, its headers, which ports answer). The
production stack itself, `docker-compose.prod.yml`, was run and checked end to end
on a laptop (see "Checked locally" at the end); only the cut-over on the box is
untested.

## 1. Record the "before" state (from any machine)

```bash
python3 deploy/smoke.py https://3-108-52-61.sslip.io
```

Baseline on 2026-10-04: `/health` and the five `/ask` languages pass; the Kochi
check and all ten checks under `[current]` fail (`/cities` lists 3 of 8 cities,
`/facts?city=mumbai` is refused, `/warnings`, `/aviation`, `/intelligence/best-window`,
`/glossary`, `/forecast/*` and `/hotlines` are 404, `/facts` has no `rain_so_far`).
The box runs an old build (`WeatherGPT /ask prototype 0.0.1`, before the gateway
and the `services/orchestrator` rename).

Also seen from outside on 2026-10-04:

- Caddy terminates TLS (`via: 1.1 Caddy`) and proxies straight to the orchestrator
  (`server: uvicorn`; `/health` has the orchestrator's shape, so no gateway).
- **Port 8001 answers from the internet** (`http://3.108.52.61:8001/health` is 200).
  That skips Caddy, and since the limiter trusts an X-Forwarded-For hop, a caller
  there picks its own rate-limit key. Close it (step 3.6).
- Ports 22, 5432, 6379 and 8000 do not answer from outside. SSH is presumably
  limited to the owner's address in the EC2 security group.

## 2. Look at what is running (on the box, read-only)

Run these and keep the output; none of them change anything.

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
docker compose ls
docker volume ls
ls -la ~ /opt 2>/dev/null
sudo ss -ltnp | grep -E ':(80|443|8000|8001|5432|6379)\b'
systemctl list-units --type=service --state=running | grep -i -E 'caddy|nginx|docker|weather|uvicorn'
cat /etc/caddy/Caddyfile 2>/dev/null
```

The questions this answers: is the old backend in a container or a bare Python
process; is Caddy a host service (`/etc/caddy/Caddyfile`) or a container; where the
current `.env` lives; and whether a Postgres with data exists today.

## 3. Deploy a fresh build of `main`

`docker-compose.prod.yml` is the production stack: Postgres + PostGIS, Redis, the
orchestrator and the gateway, plus an optional Caddy. Do not run `docker-compose.yml`
on the box; it is the development file (published database ports, a literal
password, `--reload`, bind mounts). The header of the production file lists what it
does differently and why.

The old backend can keep serving until step 3.5, so the cut-over is a Caddy reload.

**3.1 Back up.** Copy the current `.env` somewhere safe. If step 2 found a Postgres
with data, `pg_dump` it first: the production stack starts with new, empty volumes.

**3.2 Get the code.**

```bash
git fetch && git checkout main && git pull --ff-only
git rev-parse --short HEAD    # log this in step 5
```

**3.3 `.env` at the repo root.** Start from the old one and compare it with
`.env.example`. The production file needs two new values and refuses to start
without them:

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)" >> .env
echo "REDIS_PASSWORD=$(openssl rand -hex 24)" >> .env
```

Hex on purpose: both go into connection URLs, where `@ / : #` would break them.
Then check `ALLOWED_ORIGINS` (the Amplify origin only on a public box, no localhost
entries), the provider keys, and the newer keys the old build never read
(`METRICS_TOKEN`, the `DAILY_CAP_*` limits, `WARNINGS_ENABLED`). `TRUSTED_PROXY_HOPS`
and `FRONTEND_DIR` are set by the compose file (Caddy and the gateway = 2 hops);
values in `.env` are overridden.

**3.4 Build, start, seed.** From the repo root (both `.env` lookups depend on it):

```bash
docker compose -f docker-compose.prod.yml up -d --build --wait
docker compose -f docker-compose.prod.yml exec orchestrator python migrate.py --sync-places
docker compose -f docker-compose.prod.yml exec orchestrator python migrate.py --status
python3 deploy/smoke.py http://127.0.0.1:8000
```

`--sync-places` is not optional. The first database write creates an empty `cities`
table, and from then on location lookups go to Postgres instead of the gazetteer
file, so **every** named place fails, demo cities included ("I couldn't find
Chennai in India"). `--sync-places` loads the 7,115 places from
`data/gazetteer/in_places.json.gz`, which the image carries, in about 5 s; it is
idempotent. `--status` should print `gazetteer: 7115 places in cities`. The smoke
test's Kochi check catches a database that missed this step.

If the build stops with `unknown blob sha256:... in history`, that is a BuildKit
cache hiccup: run the same `up` again.

**3.5 Point TLS at the gateway.** Pick one, from step 2:

- *Caddy is a host service* (the likely case): in `/etc/caddy/Caddyfile`, change the
  site's upstream to `reverse_proxy 127.0.0.1:8000`, then `sudo systemctl reload
  caddy`. Add no `trusted_proxies`; Caddy must keep overwriting a client's own
  X-Forwarded-For.
- *No usable host proxy*: stop it, then let the stack run Caddy itself
  (`deploy/Caddyfile`; it gets the certificate on first start):

  ```bash
  echo "SITE_ADDRESS=3-108-52-61.sslip.io" >> .env
  echo "COMPOSE_PROFILES=caddy" >> .env
  docker compose -f docker-compose.prod.yml up -d --wait
  ```

  `COMPOSE_PROFILES` in `.env` keeps Caddy in every later `up`, `down` and
  `persistence_check.sh` run; without it, a recreate would leave the site down.

**3.6 Retire the old backend.** Stop it (the container or unit step 2 found), then
remove port 8001 from the EC2 security group's inbound rules. Inbound needs only
80 and 443 from anywhere and 22 from the owner's address. The new stack publishes
nothing but 127.0.0.1:8000 (and 80/443 with the `caddy` profile). Anything running
on the box itself can still reach 127.0.0.1:8000 and choose its own rate-limit key
that way, so nothing else on the box should talk to it.

## 4. Verify

```bash
# from any machine: all of it must pass
python3 deploy/smoke.py https://3-108-52-61.sslip.io

# on the box: Redis and Postgres survive a restart of their containers
COMPOSE_FILE=docker-compose.prod.yml deploy/persistence_check.sh
# the stronger version: containers destroyed and rebuilt, only named volumes survive
MODE=recreate COMPOSE_FILE=docker-compose.prod.yml deploy/persistence_check.sh

# from any machine again, after the restart
python3 deploy/smoke.py https://3-108-52-61.sslip.io
```

With the gateway in front, `smoke.py`'s `/health` line names Postgres, PostGIS, Redis
and the orchestrator, and each must be `ok`. `persistence_check.sh` finds the
containers through `COMPOSE_FILE`, and checks that `weather_facts`,
`schema_migrations` and `cities` did not shrink.

## 5. Log it

Tick B4 in plan.md only after step 4 passes on the box, and paste in: the date, the
commit that was deployed, the `smoke.py` summary line, the `persistence_check.sh`
result, and what was not checked.

## Checked locally (2026-10-04)

The production stack was run from this branch on a laptop (Docker 29.8.0, Compose
v5.5.1), with fresh volumes, real provider keys and test passwords:

- `docker compose -f docker-compose.prod.yml config` refuses to start without
  `POSTGRES_PASSWORD` / `REDIS_PASSWORD`. The rendered config publishes only
  127.0.0.1:8000, has no bind mounts and no `--reload`, and runs both app
  containers read-only.
- `up -d --build --wait`: all four containers healthy. From the laptop's LAN address,
  ports 8000, 8001, 5432 and 6379 refuse connections. Redis refuses a client without
  the password (`NOAUTH`) and reports `appendonly yes`.
- Before `--sync-places`, `/ask` for Chennai in all five languages, and for Kochi,
  answered "not found" once the first write had created the empty table. After it,
  `smoke.py http://127.0.0.1:8000`: **17 passed, 0 failed**, gateway `/health` with
  postgres, postgis, redis and orchestrator `ok`.
- `persistence_check.sh` against real Docker for the first time (it had only been
  run against a stand-in): restart mode **OK**, recreate mode **OK** (markers kept;
  `weather_facts` 11 → 11, `schema_migrations` 7 → 7, `cities` 7115 → 7115). Smoke
  17/17 again after the recreate.
- `caddy` profile with `SITE_ADDRESS=localhost` (Caddy 2.11.6, its local CA): HTTP
  redirects to HTTPS (308), smoke over `https://localhost` 17/17. 140 requests to
  `/cities` (limit 120/min), each with a different forged X-Forwarded-For, through
  Caddy: 112 × 200 then 28 × 429, so a forged header does not get a new budget. The
  same 140 sent straight to 127.0.0.1:8000: all 200, which is why that port is bound
  to localhost.

Not checked: anything on the box itself (step 2's discovery, the host Caddy edit,
a Let's Encrypt certificate for the real host name, the security group), and the
box's own Docker and disk.
