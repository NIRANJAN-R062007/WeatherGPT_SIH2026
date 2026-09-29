// Client for the orchestrator's GET /facts endpoint — the raw facts dict
// behind an answer, for surfaces that show individual figures rather than a
// narrated sentence (services/orchestrator/main.py's facts()). It's what
// lets Home and Forecast show live numbers (mobile/lib/facts_client.dart).
//
// Only three (intent, day) shapes are accepted by the backend — anything
// else is a 422:
//   current_weather + today    -> current conditions (temp_c, feels_like_c,
//                                 humidity_pct, wind_kmh, wind_dir, uv_index…)
//   will_it_rain    + today    -> today's forecast entry
//   current_weather + tonight / tomorrow -> that forecast entry
// (rain_probability_pct, high_c, low_c, condition). Tonight's high/low are
// the whole day's, since the backend reads them off the same forecast day.

import { API_BASE_URL } from './api';

/** Fixture/cache lookup with no LLM work — same budget as /warnings. */
export const FACTS_TIMEOUT_MS = 10_000;

export type FactsErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

export class FactsError extends Error {
  readonly kind: FactsErrorKind;
  readonly status: number | undefined;

  constructor(kind: FactsErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'FactsError';
    this.kind = kind;
    this.status = status;
  }
}

/** One /facts reply. An unsupported city or a missing snapshot is a 200
 *  with only `message` (and maybe `city`) — `facts` is absent then. */
export interface FactsResult {
  city?: string;
  city_name?: string;
  condition_label?: string;
  facts?: Record<string, unknown>;
  message?: string;
}

export function factNumber(r: FactsResult | null | undefined, key: string): number | null {
  const v = r?.facts?.[key];
  return typeof v === 'number' ? v : null;
}

export function factText(r: FactsResult | null | undefined, key: string): string | null {
  const v = r?.facts?.[key];
  return typeof v === 'string' && v !== '' ? v : null;
}

/** Canonical condition key (data/decoders/weather_conditions.json). */
export const factCondition = (r: FactsResult | null | undefined) => factText(r, 'condition');
export const factIsLive = (r: FactsResult | null | undefined) => r?.facts?.is_live === true;

export async function fetchFacts({
  city,
  intent = 'current_weather',
  day = 'today',
  lang,
}: {
  city: string;
  intent?: string;
  day?: string;
  lang?: string;
}): Promise<FactsResult> {
  const params = new URLSearchParams({ city, intent, day });
  if (lang) params.set('lang', lang);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FACTS_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}/facts?${params.toString()}`, { signal: controller.signal });
    if (!res.ok) {
      throw new FactsError('http', `The weather service replied HTTP ${res.status}.`, res.status);
    }
    try {
      return (await res.json()) as FactsResult;
    } catch {
      throw new FactsError('malformed', "The weather service's reply wasn't valid JSON.");
    }
  } catch (err) {
    if (err instanceof FactsError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new FactsError(
        'timeout',
        `No answer within ${Math.round(FACTS_TIMEOUT_MS / 1000)}s — the weather service timed out.`,
      );
    }
    throw new FactsError(
      'network',
      `Couldn't reach the weather service at ${API_BASE_URL}. Is the orchestrator running?`,
    );
  } finally {
    clearTimeout(timer);
  }
}
