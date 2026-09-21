FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --no-proxy-headers: a container never sees a 127.0.0.1 peer, so uvicorn's
# default X-Forwarded-For rewrite can't fire here anyway — belt and braces for
# the limiter, which reads the header itself.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
