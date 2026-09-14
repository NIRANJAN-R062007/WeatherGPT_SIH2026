# WeatherGPT on Kubernetes

Kustomize base for `gateway` and `orchestrator` (plan.md §4). Deployments,
Services, an Ingress, and HPAs — see `k8s/base/`.

## Apply to a real cluster

```
cp k8s/base/secret.example.yaml k8s/base/secret.yaml
# fill in real values in k8s/base/secret.yaml (never commit it — it's gitignored)
kubectl apply -k k8s/base
kubectl -n weathergpt get pods,svc,ingress,hpa
```

`kustomization.yaml` references `secret.yaml`, not the checked-in
`secret.example.yaml` — the build fails with a clear "no such file" error
until you copy it.

## kind quick-start (local cluster, no real secrets needed)

Uses locally built `:dev` images instead of pulling from GHCR.

```
kind create cluster --name weathergpt

docker build -t weathergpt-gateway:dev services/gateway
docker build -f services/orchestrator/Dockerfile -t weathergpt-orchestrator:dev .
kind load docker-image weathergpt-gateway:dev --name weathergpt
kind load docker-image weathergpt-orchestrator:dev --name weathergpt

cp k8s/base/secret.example.yaml k8s/base/secret.yaml   # empty values -> template narration, no paid calls

# point the base at the :dev tags for this cluster — either edit
# k8s/base/kustomization.yaml's `images:` block directly, or layer a small
# overlay:
#   resources: [../../k8s/base]
#   images:
#     - name: ghcr.io/niranjan-r062007/weathergpt-gateway
#       newName: weathergpt-gateway
#       newTag: dev
#     - name: ghcr.io/niranjan-r062007/weathergpt-orchestrator
#       newName: weathergpt-orchestrator
#       newTag: dev

kubectl apply -k k8s/base   # (or -k <path to your overlay>)
kubectl -n weathergpt rollout status deploy/gateway deploy/orchestrator --timeout=180s
kubectl -n weathergpt port-forward svc/gateway 18000:8000 &
curl localhost:18000/health
curl "localhost:18000/ask?text=weather%20in%20Chennai"
kubectl -n weathergpt get hpa,pods

kind delete cluster --name weathergpt
```

Note: `kubectl kustomize` does not support setting per-run image overrides
from the CLI without a temp overlay/kustomization edit — either edit
`images:` in place before applying (revert after), or use a throwaway
overlay directory as sketched above.

The HPA targets will show `<unknown>` for current CPU utilization unless a
metrics-server is installed in the cluster (kind doesn't ship one by
default) — that's expected and not a manifest bug.

### What an actual kind run turned up

A real run (kind v0.24.0, kubectl v1.31.0, `:dev` images built from this
checkout) got the cluster up, images loaded, and the manifests applied
cleanly — `kubectl apply -k` succeeded first try, kubeconform found no
schema issues, and the HPAs, Services and Ingress all registered. But the
Deployments themselves did not go healthy, for two reasons that are bugs in
the application images this base points at, not in the manifests:

1. **Gateway crashes at import if `DATABASE_URL`/`REDIS_URL` are empty
   strings.** `secret.example.yaml` ships both empty on purpose (no
   Postgres/Redis in this base — see above), and `envFrom: secretRef` sets
   the container's `DATABASE_URL` env var to `""`. `services/gateway/main.py`
   does `os.getenv("DATABASE_URL", "<default>")` — since the var *is* set
   (to an empty string), Python's `os.getenv` returns `""` rather than
   falling through to the default, and `sqlalchemy.create_engine("")` raises
   at import time, crash-looping the pod. Confirmed fix (verified live, not
   applied to committed files — out of this task's file ownership):
   `kubectl -n weathergpt set env deploy/gateway
   DATABASE_URL=postgresql://weathergpt:weathergpt_dev@localhost:5432/weathergpt
   REDIS_URL=redis://localhost:6379/0` — with those set to any
   syntactically valid (even unreachable) URL, the gateway pod goes
   `1/1 Running` immediately. **Until `services/gateway/main.py` is changed
   to treat an empty string the same as unset (matching the
   `os.getenv(...) or default` pattern `services/orchestrator/config.py`
   already uses elsewhere), a real deployment of this base needs
   `secret.yaml` to carry at least syntactically valid `DATABASE_URL` and
   `REDIS_URL` values, not empty ones** — flag this to whoever owns
   `services/gateway/main.py`.
2. **Orchestrator crashes at import: `RuntimeError: Directory
   '/app/prototype/frontend' does not exist`.** `services/orchestrator/main.py`
   mounts `StaticFiles(directory=_FRONTEND_DIR)` at `REPO_ROOT / "prototype"
   / "frontend"`, but `services/orchestrator/Dockerfile` only `COPY`s
   `services/orchestrator` and `data` into the image — `prototype/frontend`
   is never baked in. This is invisible in `docker-compose.yml` because that
   service bind-mounts the whole repo (`volumes: - .:/app`), which papers
   over the missing directory at runtime; it only surfaces when the image
   runs standalone, as Kubernetes must. Every orchestrator pod
   crash-loop-backed off on this in the kind run. **This is a real bug in
   the orchestrator image (Dockerfile or main.py, both outside this task's
   file ownership) that will affect any non-compose deployment, including
   `kubectl apply -k`, `docker run` on its own, or Kubernetes** — flag it
   to whoever owns `services/orchestrator/`.

With the gateway's DB/Redis vars patched live, the gateway pods came up and
the proxy behaved exactly as designed: `curl localhost:18000/health`
returned Postgres/Redis/orchestrator each independently reporting a
connection error (200 status, as coded) and `curl
localhost:18000/ask?text=weather%20in%20Chennai` returned `{"error":
"orchestrator unreachable", "detail": "ConnectError"}` — correct behavior
given the orchestrator pods were down. The gateway pods also restarted once
each on `/livez` — expected, since the images built from this checkout
predate the parallel workstream that's adding `/livez`/`/metrics`; once that
lands in the images, the liveness probe will pass on the first check.
`kubectl -n weathergpt get hpa` showed `cpu: <unknown>/60%` for both HPAs, as
expected with no metrics-server in a bare kind cluster.

The cluster was deleted afterward (`kind delete cluster --name weathergpt`)
along with the local `:dev` images and the temporary image-override overlay
used to apply them.

## Validating manifests without a cluster (used in CI and here)

```
# raw resources (kustomization.yaml itself is skipped, expected)
docker run --rm -v "$PWD/k8s:/k8s" ghcr.io/yannh/kubeconform:latest \
  -strict -summary -ignore-missing-schemas /k8s/base

# rendered output — kubeconform can't expand kustomize overlays itself
cp k8s/base/secret.example.yaml k8s/base/secret.yaml
docker run --rm -v "$PWD/k8s:/k8s" registry.k8s.io/kubectl:v1.31.0 \
  kustomize /k8s/base | \
  docker run --rm -i ghcr.io/yannh/kubeconform:latest \
  -strict -summary -ignore-missing-schemas -
```

## What's deliberately absent

**Postgres and Redis.** The gateway's `/health` checks them but the reverse
proxy itself works without them (see `services/gateway/main.py` — each
`/health` sub-check is independent, and `DATABASE_URL`/`REDIS_URL` default to
`localhost` if unset, which will simply show `error: ...` in `/health` rather
than crash the pod). This base manifest ships neither a Postgres nor a Redis
workload, so `/history` (Supabase-backed, not Postgres-in-cluster anyway) and
the gateway's own DB/cache checks will report errors — expected, and harmless
for the `/ask`, `/facts`, `/warnings` and `/asr` paths this cluster is meant to
serve. To add them later: a `StatefulSet` + `Service` for
`postgis/postgis:16-3.4` (mirroring `docker-compose.yml`'s `postgres`
service, with a `PersistentVolumeClaim` for `/var/lib/postgresql/data`) and a
`Deployment` + `Service` for `redis:7-alpine`, then point `DATABASE_URL` /
`REDIS_URL` in `secret.yaml` at their in-cluster Service DNS names
(`postgres.weathergpt.svc.cluster.local`, etc.) instead of leaving them
empty.

**metrics-server / Prometheus / Grafana.** Pods carry
`prometheus.io/scrape`, `prometheus.io/port`, `prometheus.io/path`
annotations for a Prometheus that discovers pods this way, and both services
expose `/metrics` — but no Prometheus/Grafana workload is included here; see
`docker-compose.yml`'s `--profile monitoring` (a separate agent's work) for a
local stack, or point a cluster Prometheus's annotation-based pod discovery
at this namespace.

**Ollama.** `OLLAMA_BASE` in the ConfigMap points at `http://ollama:11434`,
matching `docker-compose.yml`'s offline profile service name, but no Ollama
workload is deployed here — the orchestrator's third-provider fallback will
simply fail closed to the template narration path until one exists.

## Images

`kustomization.yaml`'s `images:` block pins both Deployments to
`ghcr.io/niranjan-r062007/weathergpt-gateway:latest` and
`ghcr.io/niranjan-r062007/weathergpt-orchestrator:latest` — published by
CI's `publish-images` job (`.github/workflows/ci.yml`) on every push to
`main`. For a kind cluster with locally built images, override `newName`/
`newTag` per service as shown above instead of relying on the `:latest`
GHCR pull (kind has no registry credentials or route to GHCR by default,
though public images should still pull — using local `:dev` tags just
avoids the network round trip and lets you test uncommitted Dockerfile
changes).
