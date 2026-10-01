FROM python:3.11-slim

# Debian security fixes the base tag hasn't been rebuilt with yet (openssl,
# pcre2, ...). CI's Trivy gate fails on any fixable HIGH/CRITICAL finding
# (.github/workflows/security.yml, plan.md SEC-N18).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then drop the packaging tools: nothing at runtime needs them, and pip
# vendors its own (vulnerable) urllib3/msgpack that no pip upgrade fixes.
RUN pip uninstall -y pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.11/ensurepip

COPY . .

# Non-root runtime: fixed UID/GID so k8s runAsUser/fsGroup can match. App files
# stay root-owned and read-only (the service writes nothing under /app);
# /tmp is the only writable path (emptyDir under readOnlyRootFilesystem).
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp TMPDIR=/tmp
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001:10001

EXPOSE 8000

# --no-proxy-headers: a container never sees a 127.0.0.1 peer, so uvicorn's
# default X-Forwarded-For rewrite can't fire here anyway — belt and braces for
# the limiter, which reads the header itself.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
