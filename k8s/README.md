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
schema issues, and the HPAs, Services and Ingress all registered. The
Deployments did **not** go healthy on that first run, which exposed two bugs
in the application images (not the manifests). Both are now fixed on `main`:

1. **Gateway crashed at import when `DATABASE_URL`/`REDIS_URL` were empty
   strings.** `secret.example.yaml` ships both empty on purpose (no
   Postgres/Redis in this base), and `envFrom: secretRef` sets the variable
   to `""` — `os.getenv(name, default)` then returns `""` and
   `create_engine("")` raised. `services/gateway/main.py` now uses
   `os.getenv(name) or default`, so empty means "use the default (and let
   `/health` report the connection error)".
2. **Orchestrator crashed at import with `Directory '/app/prototype/frontend'
   does not exist`.** `main.py` mounts the web UI from there but the
   Dockerfile never copied it in — invisible under docker-compose, which
   bind-mounts the whole repo. The Dockerfile now `COPY`s
   `prototype/frontend`, and the mount uses `check_dir=False` so an
   API-only image still boots.

With the gateway's DB/Redis vars patched live during that run, its pods came
up and the proxy behaved exactly as designed: `/health` returned
Postgres/Redis/orchestrator each independently reporting a connection error
(200 status, as coded) and `/ask` returned `{"error": "orchestrator
unreachable"}` while the orchestrator pods were down. `kubectl -n weathergpt
get hpa` showed `cpu: <unknown>/60%` for both HPAs, as expected with no
metrics-server in a bare kind cluster. The cluster and local `:dev` images
were deleted afterward.

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

**Package visibility.** Packages first published with `GITHUB_TOKEN` are
**private** on GHCR, so a fresh cluster gets `ImagePullBackOff` until one of
these is done once:

- make both packages public — GitHub → the owner's *Packages* →
  `weathergpt-gateway` / `weathergpt-orchestrator` → *Package settings* →
  *Change visibility*; nothing in the manifests changes; or
- keep them private and give the namespace a pull secret:
  `kubectl -n weathergpt create secret docker-registry ghcr-pull --docker-server=ghcr.io --docker-username=<github-user> --docker-password=<PAT with read:packages>`
  then add `imagePullSecrets: [{name: ghcr-pull}]` to both pod specs (an
  overlay patch is the tidy way; the base stays credential-free).
