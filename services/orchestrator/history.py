"""Per-user query history (plan.md §14 Abel track — picked up once Deepthi's
Supabase schema landed; keyed off her `public.profiles` table).

No service-role key here either (see config.py's note on auth.py) — every
read/write goes through Supabase PostgREST using the *caller's own* session
token, so Postgres RLS (public.history: auth.uid() = user_id, see
sql/supabase_schema.sql) is what actually keeps one user's history from
another's. `user_id` is never sent on insert — the column defaults to
`auth.uid()`, which PostgREST resolves from the same bearer token.
"""

import config
import httpx
from config import require


def record(token: str, *, query: str, intent: str | None, city: str | None,
           lang: str | None, response: str | None) -> None:
    """Log one answered query. Raises on failure — callers (main.py's /ask)
    must catch and swallow, since a broken history write must never break the
    weather answer itself."""
    url = require("SUPABASE_URL", config.SUPABASE_URL)
    key = require("SUPABASE_ANON_KEY", config.SUPABASE_ANON_KEY)
    row = {"query": query, "intent": intent, "city": city, "lang": lang, "response": response}
    resp = httpx.post(
        f"{url}/rest/v1/history",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=row,
        timeout=5,
    )
    resp.raise_for_status()


def list_for_user(token: str, *, limit: int = 50) -> list[dict]:
    """Most-recent-first history for whoever `token` belongs to."""
    url = require("SUPABASE_URL", config.SUPABASE_URL)
    key = require("SUPABASE_ANON_KEY", config.SUPABASE_ANON_KEY)
    resp = httpx.get(
        f"{url}/rest/v1/history",
        headers={"Authorization": f"Bearer {token}", "apikey": key},
        params={"select": "*", "order": "created_at.desc", "limit": str(limit)},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def clear_for_user(token: str, user_id: str) -> None:
    """Delete every history row belonging to `user_id`. PostgREST refuses an
    unfiltered DELETE, and RLS (auth.uid() = user_id) means the filter can
    only ever match the caller's own rows anyway."""
    url = require("SUPABASE_URL", config.SUPABASE_URL)
    key = require("SUPABASE_ANON_KEY", config.SUPABASE_ANON_KEY)
    resp = httpx.delete(
        f"{url}/rest/v1/history",
        headers={"Authorization": f"Bearer {token}", "apikey": key, "Prefer": "return=minimal"},
        params={"user_id": f"eq.{user_id}"},
        timeout=5,
    )
    resp.raise_for_status()
