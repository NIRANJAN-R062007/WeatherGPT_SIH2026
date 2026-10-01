"""Security response headers and the routes production keeps private
(plan.md §8 Phase 8, SEC-N13; findings F8 and F12).

Byte-identical copies live in `services/orchestrator/` and `services/gateway/`:
the gateway's Docker build context is `services/gateway/` alone, so it can't
import this one. `tests/test_security_headers.py` fails if they drift.

Headers are added with setdefault, never overwritten. The gateway proxies the
orchestrator's responses untouched, so the orchestrator's choice (the page CSP
for the HTML it serves at `/`) survives the hop and the gateway only fills in
its own JSON responses.

PAGE_CSP must stay in step with `customHttp.yml`, which sends the same policy
from Amplify. `'unsafe-inline'` and `'unsafe-eval'` are there because
`prototype/frontend/support.js` compiles the page's inline `text/x-dc` scripts
with Babel and runs them through `new Function`; the policy still pins every
origin the page may load from or talk to, and forbids framing.
"""

import os

from starlette.datastructures import MutableHeaders
from starlette.requests import Request

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

_SUPABASE = "bkohiigdngppywnzakvg.supabase.co"  # prototype/frontend/auth.js
PAGE_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net",
    # jsdelivr: Swagger UI's stylesheet when API_DOCS_ENABLED is on locally.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
    "font-src 'self' data: https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",
    "media-src 'self' data: blob:",
    "worker-src 'self' blob:",
    # The live API (the page's default apiBase), Supabase auth, the script
    # CDNs, ngrok tunnels (run_tunnel.sh) and a local orchestrator.
    f"connect-src 'self' https://3-108-52-61.sslip.io https://{_SUPABASE} wss://{_SUPABASE}"
    " https://unpkg.com https://cdn.jsdelivr.net https://*.ngrok-free.app https://*.ngrok.app"
    " http://localhost:* http://127.0.0.1:*",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

_COMMON = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# Off unless API_DOCS_ENABLED is set: /docs, /redoc and /openapi.json map the
# whole API for anyone who asks. .env.example turns them on for local dev.
DOCS_ENABLED: bool = (os.getenv("API_DOCS_ENABLED") or "").strip().lower() in ("1", "true", "yes")


def docs_kwargs() -> dict:
    """FastAPI(...) keyword arguments that drop the docs routes unless enabled."""
    if DOCS_ENABLED:
        return {}
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


def is_direct(request: Request) -> bool:
    """True when nothing proxied this request. Platform probes (kubelet,
    `docker exec`, a curl on the host) hit the container directly; anything
    from the internet arrives through the ingress, Caddy, Render's edge, ngrok
    or the gateway, all of which add X-Forwarded-For. Used to keep `/livez`
    platform-only."""
    return "x-forwarded-for" not in request.headers


class SecurityHeaders:
    """Pure ASGI middleware: adds _COMMON plus a CSP to every HTTP response —
    PAGE_CSP for HTML, API_CSP for everything else."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _COMMON.items():
                    headers.setdefault(name, value)
                html = headers.get("content-type", "").startswith("text/html")
                headers.setdefault("Content-Security-Policy", PAGE_CSP if html else API_CSP)
            await send(message)

        await self.app(scope, receive, send_with_headers)
