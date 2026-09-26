// Typed client for the orchestrator's GET /warnings endpoint.
//
// This is NOT /ask's warnings branch (AskWarningsResponse /
// AskWarningsUnavailableResponse in ./api.ts) — it's the standalone
// `/warnings?city=&lang=` route, which returns a flatter top-level shape:
// no `intent`/`response`/`provenance`/`grounding`/`nlu`, just `city`,
// `city_name`, `status`, `warning`, `legend`. Verified directly against
// services/orchestrator/main.py's `warnings_route()` and
// imd_warnings.py's `public()` (2026-09-26).
//
// `WarningDetail`, `LegendRow`, `WarningColour`, `WarningStatus` are already
// defined in ./api.ts for /ask's warnings branch, which wraps the exact same
// `imd_warnings.public()` call — reused here rather than redefined.

import { useCallback, useRef, useState } from 'react';
import { API_BASE_URL, type LegendRow, type WarningDetail } from './api';

// /warnings does no LLM/narration work — it's a fixture/cache lookup — so a
// much shorter timeout than /ask's 30s is appropriate.
export const WARNINGS_TIMEOUT_MS = 10_000;

// ---------------------------------------------------------------------------
// Response shape
// ---------------------------------------------------------------------------

/** `imd_warnings.STATUS_UNAVAILABLE` branch: WARNINGS_ENABLED is off (the
 *  default in this repo's .env) or the city's fixture is missing/malformed.
 *  `warning` is always null here — this is a "no verdict", never an
 *  all-clear (plan.md §2 principle 3). */
export interface WarningsUnavailable {
  city: string;
  city_name: string;
  status: 'unavailable';
  warning: null;
  legend: LegendRow[];
}

/** `imd_warnings.STATUS_CLEAR` / `STATUS_ACTIVE`: a real fixture verdict.
 *  `warning` is always present — green ("clear") still carries the feed's
 *  own "nothing in force" headline and validity window. */
export interface WarningsVerdict {
  city: string;
  city_name: string;
  status: 'clear' | 'active';
  warning: WarningDetail;
  legend: LegendRow[];
}

export type WarningsRouteResponse = WarningsUnavailable | WarningsVerdict;

// ---------------------------------------------------------------------------
// The call
// ---------------------------------------------------------------------------

export type WarningsErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

/** Thrown by fetchWarnings for anything that isn't a parsed 2xx body —
 *  including the genuine 404 /warnings raises for an unknown city (unlike
 *  /ask, there is no soft "unsupported city" JSON fallback for this route). */
export class WarningsError extends Error {
  readonly kind: WarningsErrorKind;
  readonly status: number | undefined;

  constructor(kind: WarningsErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'WarningsError';
    this.kind = kind;
    this.status = status;
  }
}

export interface WarningsParams {
  /** A city key /or/ a display name — the backend resolves it the same way
   *  /ask does (cities.resolve). Passing a CITIES[].key is safest. */
  city: string;
  /** One of i18n.SUPPORTED_LANGUAGES; anything else gets a 422 from the
   *  backend (`_require_lang`), surfaced here as an 'http' error. */
  lang?: string;
}

export async function fetchWarnings({ city, lang }: WarningsParams): Promise<WarningsRouteResponse> {
  const params = new URLSearchParams({ city });
  if (lang) params.set('lang', lang);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), WARNINGS_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_BASE_URL}/warnings?${params.toString()}`, {
      signal: controller.signal,
    });
    if (!res.ok) {
      const detail = res.status === 404 ? 'Unknown city.' : `HTTP ${res.status}.`;
      throw new WarningsError('http', `The warnings service replied ${detail}`, res.status);
    }
    let payload: unknown;
    try {
      payload = await res.json();
    } catch {
      throw new WarningsError('malformed', "The warnings service's reply wasn't valid JSON.");
    }
    if (
      payload === null ||
      typeof payload !== 'object' ||
      !('status' in payload) ||
      !('legend' in payload)
    ) {
      throw new WarningsError('malformed', "The warnings service's reply didn't look like a verdict.");
    }
    return payload as WarningsRouteResponse;
  } catch (err) {
    if (err instanceof WarningsError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new WarningsError(
        'timeout',
        `No answer within ${Math.round(WARNINGS_TIMEOUT_MS / 1000)}s — the warnings service timed out.`,
      );
    }
    throw new WarningsError(
      'network',
      `Couldn't reach the warnings service at ${API_BASE_URL}. Is the orchestrator running?`,
    );
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Hook — same shape as ./useAsk.ts's useAsk, adapted for a city-keyed lookup
// instead of a free-text question.
// ---------------------------------------------------------------------------

export interface WarningsState {
  /** The city key the displayed result answers (not necessarily the
   *  currently-selected one, if a request is still in flight). */
  city: string | null;
  loading: boolean;
  data: WarningsRouteResponse | null;
  error: WarningsError | null;
}

const IDLE: WarningsState = { city: null, loading: false, data: null, error: null };

/** Shared /warnings call state: one in-flight request at a time, late
 *  replies from a superseded request (e.g. a fast city switch) dropped. */
export function useWarnings() {
  const [state, setState] = useState<WarningsState>(IDLE);
  // Bumped on every load(); a reply whose id no longer matches is stale.
  const requestId = useRef(0);

  const load = useCallback(async (city: string, lang?: string) => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const data = await fetchWarnings({ city, lang });
      if (requestId.current !== id) return;
      setState({ city, loading: false, data, error: null });
    } catch (err) {
      if (requestId.current !== id) return;
      const error =
        err instanceof WarningsError
          ? err
          : new WarningsError('network', 'Something went wrong talking to the warnings service.');
      setState({ city, loading: false, data: null, error });
    }
  }, []);

  return { ...state, load };
}
