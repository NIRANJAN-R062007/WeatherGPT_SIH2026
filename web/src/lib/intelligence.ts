// Typed client for the orchestrator's Weather Intelligence Engine view-only
// slice (plan.md §8 Phase 9, WIE-13): GET /intelligence/best-window and
// POST /intelligence/scenario (services/orchestrator/main.py +
// weather_intelligence/). Deterministic rules only — nothing here is
// narrated by an LLM (plan.md §2 principle 7), so these shapes are read
// directly, the same discipline as lib/aviation.ts and lib/warnings.ts.
import { useCallback, useRef, useState } from 'react';
import { API_BASE_URL } from './api';

export const INTELLIGENCE_TIMEOUT_MS = 15_000;

export type Day = 'today' | 'tomorrow';

export interface IntelligenceHour {
  time_iso: string;
  local_time: string;
  temp_c: number;
  rain_probability_pct: number;
  wind_kmh: number;
  condition: string;
  uv_index?: number | null;
}

export interface BestWindow {
  start_local: string;
  end_local: string;
  avg_temp_c: number;
  max_rain_probability_pct: number;
  max_wind_kmh: number;
  hours: IntelligenceHour[];
}

export interface Provenance {
  source: string;
  is_live: boolean;
}

export interface BestWindowResponse {
  city: string;
  city_name: string;
  day: Day;
  activity: string;
  /** "ok" (a window exists) | "no_suitable_window" (checked, none passed —
   *  a real negative result, never the least-bad hour) | "unavailable"
   *  (no hourly forecast to check, e.g. "tomorrow" against the committed
   *  fixtures' single-day hourly series). */
  status: 'ok' | 'no_suitable_window' | 'unavailable';
  window: BestWindow | null;
  provenance: Provenance | null;
}

export interface ScenarioHourResult {
  time: string;
  available: boolean;
  temp_c?: number;
  rain_probability_pct?: number;
  wind_kmh?: number;
  condition?: string;
  suitable?: boolean;
}

export interface ScenarioResponse {
  city: string;
  city_name: string;
  day: Day;
  activity: string;
  status: 'ok' | 'unavailable';
  hours: ScenarioHourResult[];
  better_time: string | null;
  provenance: Provenance | null;
}

export type IntelligenceErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

export class IntelligenceError extends Error {
  readonly kind: IntelligenceErrorKind;
  constructor(kind: IntelligenceErrorKind, message: string) {
    super(message);
    this.name = 'IntelligenceError';
    this.kind = kind;
  }
}

async function _request<T>(path: string, init: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), INTELLIGENCE_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
    if (!res.ok) {
      const detail = res.status === 404 ? 'Unknown city.' : res.status === 422 ? 'Bad request.' : `HTTP ${res.status}.`;
      throw new IntelligenceError('http', `The weather intelligence service replied ${detail}`);
    }
    try {
      return (await res.json()) as T;
    } catch {
      throw new IntelligenceError('malformed', "The weather intelligence service's reply wasn't valid JSON.");
    }
  } catch (err) {
    if (err instanceof IntelligenceError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new IntelligenceError('timeout', 'The weather intelligence service took too long to answer.');
    }
    throw new IntelligenceError(
      'network',
      `Couldn't reach the weather intelligence service at ${API_BASE_URL}. Is the orchestrator running?`,
    );
  } finally {
    clearTimeout(timer);
  }
}

export function fetchBestWindow(city: string, day: Day, activity = 'outdoor'): Promise<BestWindowResponse> {
  const params = new URLSearchParams({ city, day, activity }).toString();
  return _request<BestWindowResponse>(`/intelligence/best-window?${params}`, { method: 'GET' });
}

export function fetchScenario(
  city: string,
  day: Day,
  times: string[],
  activity = 'outdoor',
): Promise<ScenarioResponse> {
  return _request<ScenarioResponse>('/intelligence/scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city, day, times, activity }),
  });
}

interface BestWindowState {
  loading: boolean;
  data: BestWindowResponse | null;
  error: IntelligenceError | null;
}

const IDLE_WINDOW: BestWindowState = { loading: false, data: null, error: null };

/** One request at a time; a late reply from a superseded request (a fast
 *  city/day switch) is dropped — same discipline as useAviation(). */
export function useBestWindow() {
  const [state, setState] = useState<BestWindowState>(IDLE_WINDOW);
  const requestId = useRef(0);

  const load = useCallback(async (city: string, day: Day, activity = 'outdoor') => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await fetchBestWindow(city, day, activity);
      if (requestId.current !== id) return;
      setState({ loading: false, data, error: null });
    } catch (err) {
      if (requestId.current !== id) return;
      const error =
        err instanceof IntelligenceError
          ? err
          : new IntelligenceError('network', 'Something went wrong finding the best window.');
      setState({ loading: false, data: null, error });
    }
  }, []);

  return { ...state, load };
}

interface ScenarioState {
  loading: boolean;
  data: ScenarioResponse | null;
  error: IntelligenceError | null;
}

const IDLE_SCENARIO: ScenarioState = { loading: false, data: null, error: null };

export function useScenario() {
  const [state, setState] = useState<ScenarioState>(IDLE_SCENARIO);
  const requestId = useRef(0);

  const compare = useCallback(async (city: string, day: Day, times: string[], activity = 'outdoor') => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await fetchScenario(city, day, times, activity);
      if (requestId.current !== id) return;
      setState({ loading: false, data, error: null });
    } catch (err) {
      if (requestId.current !== id) return;
      const error =
        err instanceof IntelligenceError
          ? err
          : new IntelligenceError('network', 'Something went wrong comparing those times.');
      setState({ loading: false, data: null, error });
    }
  }, []);

  const reset = useCallback(() => setState(IDLE_SCENARIO), []);

  return { ...state, compare, reset };
}
