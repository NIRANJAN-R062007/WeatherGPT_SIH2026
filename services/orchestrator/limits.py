"""Request limits for the public /ask surface (plan.md §8 Phase 3 security pass).

The prototype sits on a world-reachable ngrok URL with no auth on /ask, /asr
and /tts, and every one of those can fan out to paid Bhashini/LLM calls. Two
cheap in-process guards cover the demo:

- a body-size cap (413) so a multi-megabyte /asr upload never reaches Bhashini;
- a per-client sliding-window rate limit (429) on the expensive routes, keyed
  by the first X-Forwarded-For hop (ngrok sets it) or the socket peer.

Both are process-local — fine for one uvicorn worker, which is how the demo
runs. Behind a real gateway (plan.md §4) these move to the edge.
"""

import threading
import time
from collections import defaultdict, deque

import config
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

LIMITED_PATHS = frozenset({"/ask", "/asr", "/tts"})
_WINDOW_SECONDS = 60.0

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()
_monotonic = time.monotonic  # test seam


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def reset() -> None:
    with _lock:
        _hits.clear()


def _over_limit(key: str, per_minute: int) -> bool:
    now = _monotonic()
    with _lock:
        window = _hits[key]
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()
        if len(window) >= per_minute:
            return True
        window.append(now)
        return False


class RequestLimits(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > config.MAX_BODY_BYTES:
            return JSONResponse({"detail": "request body too large"}, status_code=413)

        per_minute = config.RATE_LIMIT_PER_MINUTE
        if per_minute > 0 and request.url.path in LIMITED_PATHS:
            if _over_limit(client_key(request), per_minute):
                return JSONResponse(
                    {"detail": "too many requests — try again in a minute"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
