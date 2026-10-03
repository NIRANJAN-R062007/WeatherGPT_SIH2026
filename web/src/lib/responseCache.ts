// Saved copies of the backend's replies, so a page that can't reach the
// backend shows the last good answer, labelled with when it was saved,
// instead of only an error (plan.md §2 principle 5, offline-degradable;
// mobile/lib/response_cache.dart).
//
// Only public, non-personal replies are saved: /facts, /forecast/daily,
// /forecast/hourly, /warnings, /hotlines and /glossary. Never /ask answers
// or History. Each reply is one localStorage entry keyed by its request
// path and query, so the set is bounded by cities × languages × routes. A
// copy older than MAX_SAVED_AGE_MS is not used. Storage that is full,
// blocked or missing just means nothing is saved.

/** Older saved copies are ignored: a week-old forecast is no answer. */
export const MAX_SAVED_AGE_MS = 7 * 24 * 60 * 60 * 1000;

const PREFIX = 'weathergpt.saved:';

export type Json = Record<string, unknown>;

/** The key for a GET: path plus query, parameters in a fixed order. */
export function replyKey(path: string, params: Record<string, string>) {
  return `${path}?${Object.keys(params)
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join('&')}`;
}

export function readSaved(key: string): { body: Json; savedAt: Date } | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const { body, saved_at } = JSON.parse(raw) as { body?: unknown; saved_at?: unknown };
    const savedAt = new Date(typeof saved_at === 'string' ? saved_at : NaN);
    if (body === null || typeof body !== 'object' || Number.isNaN(savedAt.getTime())) return null;
    return { body: body as Json, savedAt };
  } catch {
    return null; // no storage, or a damaged entry
  }
}

/** Best effort: a failure is swallowed, the reply still reaches the page. */
export function writeSaved(key: string, body: Json, now = new Date()) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({ saved_at: now.toISOString(), body }));
  } catch {
    // Full or blocked storage: this reply just isn't saved.
  }
}

/** `fetch`'s reply, saved for next time, with a null saved time. If `fetch`
 *  fails in a way `canUseSaved` accepts (the backend couldn't be reached, not
 *  "it answered no"), the saved copy and when it was saved instead; with no
 *  usable copy, the original error. */
export async function fetchOrSaved(
  key: string,
  fetch: () => Promise<Json>,
  canUseSaved: (error: unknown) => boolean,
): Promise<{ body: Json; savedAt: Date | null }> {
  try {
    const body = await fetch();
    writeSaved(key, body);
    return { body, savedAt: null };
  } catch (err) {
    if (!canUseSaved(err)) throw err;
    const saved = readSaved(key);
    if (!saved || Date.now() - saved.savedAt.getTime() > MAX_SAVED_AGE_MS) throw err;
    return saved;
  }
}
