"""Supabase session verification for the orchestrator (plan.md §14 Deepthi track).

The frontend signs in with Google via Supabase Auth (see prototype/frontend/auth.js)
and gets back a session access token. It sends that token as
`Authorization: Bearer <token>` on requests that need to know who the user is
(e.g. Abel's /history endpoint). We don't verify the JWT locally — we ask
Supabase's own Auth API to validate it, which sidesteps signing-algorithm/key
rotation details entirely and is cheap at hackathon scale.
"""

import config
import httpx
from config import SUPABASE_ANON_KEY, SUPABASE_URL, require
from fastapi import Header, HTTPException


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1]


async def _fetch_user(token: str) -> dict:
    try:
        url = require("SUPABASE_URL", SUPABASE_URL)
        key = require("SUPABASE_ANON_KEY", SUPABASE_ANON_KEY)
    except config.ConfigError:  # attribute lookup survives test reloads of config
        raise HTTPException(status_code=503, detail="Sign-in is not configured on this server")
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": key},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return resp.json()


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: require a signed-in user, 401 otherwise."""
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return await _fetch_user(token)


async def get_optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    """Like get_current_user, but returns None instead of 401 when signed out."""
    token = _parse_bearer(authorization)
    if not token:
        return None
    try:
        return await _fetch_user(token)
    except HTTPException:
        return None


def get_bearer_token(authorization: str | None = Header(default=None)) -> str | None:
    """Raw session token, or None when signed out — no Supabase round-trip.

    For endpoints (history.py) that hand the token straight to Supabase
    PostgREST and let Postgres RLS + PostgREST's own JWT check be the
    authorization, instead of first verifying it against /auth/v1/user the
    way get_current_user does for /me.
    """
    return _parse_bearer(authorization)
