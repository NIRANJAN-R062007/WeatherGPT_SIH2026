FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
