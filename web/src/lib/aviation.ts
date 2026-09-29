// Typed client for the orchestrator's GET /aviation endpoint: the current
// METAR and TAF for a demo city's airport (services/orchestrator/aviation.py).
// Shapes verified against the endpoint's own output, 2026-09-30.
//
// Each report (`metar`, `taf`) is null when the source has none; the page must
// show that as "not available", never as fair weather (plan.md §2
// principle 3). `is_live` is false for a snapshot, which the page labels.
import { useCallback, useRef, useState } from 'react';
import { API_BASE_URL } from './api';

// A live fetch plus decoding, cached server-side; well under /ask's 30 s.
export const AVIATION_TIMEOUT_MS = 15_000;

export interface AviationReport {
  /** The report exactly as issued. */
  raw: string;
  /** metar.decode() / taf.decode() output; only the fields the page reads. */
  decoded: {
    observed?: { day: number; time_utc: string; time_ist: string } | null;
    issued?: { day: number; time_utc: string; time_ist: string } | null;
  };
  /** The English briefing as one paragraph. */
  briefing: string;
  /** The same briefing, one line per element or forecast period. */
  lines: string[];
  is_live: boolean;
  /** When the text was fetched — a snapshot's own date when it isn't live. */
  retrieved_at: string;
  source: string;
}

export interface AviationResponse {
  station: string;
  station_name: string | null;
  city: string | null;
  /** "ok" when at least one report exists, "unavailable" when neither does. */
  status: 'ok' | 'unavailable';
  metar: AviationReport | null;
  taf: AviationReport | null;
  disclaimer: string;
}

export type AviationErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

export class AviationError extends Error {
  readonly kind: AviationErrorKind;

  constructor(kind: AviationErrorKind, message: string) {
    super(message);
    this.name = 'AviationError';
    this.kind = kind;
  }
}

export async function fetchAviation(city: string): Promise<AviationResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AVIATION_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}/aviation?${new URLSearchParams({ city }).toString()}`, {
      signal: controller.signal,
    });
    if (!res.ok) {
      const detail = res.status === 404 ? 'No airport for that city.' : `HTTP ${res.status}.`;
      throw new AviationError('http', `The airport weather service replied ${detail}`);
    }
    let payload: unknown;
    try {
      payload = await res.json();
    } catch {
      throw new AviationError('malformed', "The airport weather service's reply wasn't valid JSON.");
    }
    if (payload === null || typeof payload !== 'object' || !('station' in payload) || !('status' in payload)) {
      throw new AviationError('malformed', "The airport weather service's reply didn't look like a report.");
    }
    return payload as AviationResponse;
  } catch (err) {
    if (err instanceof AviationError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new AviationError('timeout', 'The airport weather service took too long to answer.');
    }
    throw new AviationError(
      'network',
      `Couldn't reach the airport weather service at ${API_BASE_URL}. Is the orchestrator running?`,
    );
  } finally {
    clearTimeout(timer);
  }
}

export interface AviationState {
  /** The city key the displayed result answers. */
  city: string | null;
  loading: boolean;
  data: AviationResponse | null;
  error: AviationError | null;
}

const IDLE: AviationState = { city: null, loading: false, data: null, error: null };

/** /aviation call state: one request at a time, a late reply from a superseded
 *  request (a fast city switch) dropped. */
export function useAviation() {
  const [state, setState] = useState<AviationState>(IDLE);
  const requestId = useRef(0);

  const load = useCallback(async (city: string) => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await fetchAviation(city);
      if (requestId.current !== id) return;
      setState({ city, loading: false, data, error: null });
    } catch (err) {
      if (requestId.current !== id) return;
      const error =
        err instanceof AviationError
          ? err
          : new AviationError('network', 'Something went wrong talking to the airport weather service.');
      setState({ city, loading: false, data: null, error });
    }
  }, []);

  return { ...state, load };
}
