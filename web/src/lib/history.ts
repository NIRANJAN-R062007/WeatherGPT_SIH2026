// Client for the orchestrator's per-user query history. GET /history returns
// the signed-in user's past /ask calls, newest first; DELETE /history erases
// them (services/orchestrator/main.py). Both send the user's Supabase access
// token as `Authorization: Bearer <token>`; the backend forwards it to
// Supabase, where row-level security decides whose rows come back.
import { API_BASE_URL } from './api';

/** One row of `public.history` (services/orchestrator/sql/supabase_schema.sql). */
export interface HistoryRow {
  id: string;
  query: string;
  intent: string | null;
  city: string | null;
  lang: string | null;
  /** The answer that was shown; null when the question got no grounded answer. */
  response: string | null;
  /** ISO timestamp. */
  created_at: string;
}

export type HistoryErrorKind = 'auth' | 'unavailable' | 'http' | 'network' | 'timeout' | 'malformed';

export class HistoryError extends Error {
  readonly kind: HistoryErrorKind;

  constructor(kind: HistoryErrorKind, message: string) {
    super(message);
    this.name = 'HistoryError';
    this.kind = kind;
  }
}

const HISTORY_TIMEOUT_MS = 15_000;

async function call(method: 'GET' | 'DELETE', token: string): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HISTORY_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}/history`, {
      method,
      signal: controller.signal,
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) {
      throw new HistoryError('auth', 'Your session has expired. Sign in again to see your history.');
    }
    if (res.status === 503) {
      throw new HistoryError('unavailable', 'History is not set up on this server.');
    }
    if (!res.ok) {
      throw new HistoryError('http', `The history service replied HTTP ${res.status}.`);
    }
    try {
      return await res.json();
    } catch {
      throw new HistoryError('malformed', "The history service's reply wasn't valid JSON.");
    }
  } catch (err) {
    if (err instanceof HistoryError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new HistoryError('timeout', 'The history service took too long to answer.');
    }
    throw new HistoryError('network', `Couldn't reach the server at ${API_BASE_URL}. Is the orchestrator running?`);
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchHistory(token: string): Promise<HistoryRow[]> {
  const body = await call('GET', token);
  const rows = body && typeof body === 'object' ? (body as { history?: unknown }).history : undefined;
  if (!Array.isArray(rows)) {
    throw new HistoryError('malformed', "The history service's reply didn't look like a history list.");
  }
  return rows.filter(
    (r): r is HistoryRow =>
      !!r && typeof r === 'object' && typeof (r as HistoryRow).query === 'string' && typeof (r as HistoryRow).id === 'string',
  );
}

export async function clearHistory(token: string): Promise<void> {
  await call('DELETE', token);
}

/** Groups for the filter chips; matches nlu.py's INTENTS. */
export type HistoryFilter = 'all' | 'alerts' | 'rain';

export function matchesFilter(row: HistoryRow, filter: HistoryFilter) {
  if (filter === 'alerts') return row.intent === 'warnings';
  if (filter === 'rain') return row.intent === 'will_it_rain' || row.intent === 'rainfall_so_far_today';
  return true;
}
