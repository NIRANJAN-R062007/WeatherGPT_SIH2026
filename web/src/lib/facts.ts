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
// Current conditions also carry `rain_so_far` (FactsResult.rain_so_far).
//
// GET /forecast/daily and /forecast/hourly (the day list, sun times and the
// hourly strip) come through the same helper and errors. A backend from
// before those routes answers 404; FactsError.status says so, and the pages
// fall back to the /facts rows.

import { API_BASE_URL } from './api';
import type { Args } from './i18n';

/** Fixture/cache lookup with no LLM work — same budget as /warnings. */
export const FACTS_TIMEOUT_MS = 10_000;

export type FactsErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

export class FactsError extends Error {
  readonly kind: FactsErrorKind;
  readonly status: number | undefined;
  /** Values for the `{name}` placeholders in `message`, a ui_strings.json key. */
  readonly args: Args;

  constructor(kind: FactsErrorKind, message: string, status?: number, args: Args = {}) {
    super(message);
    this.name = 'FactsError';
    this.kind = kind;
    this.status = status;
    this.args = args;
  }
}

/** A JSON object of figures; a missing or mistyped field reads as null. */
export type Figures = Record<string, unknown>;

export function figure(f: Figures | null | undefined, key: string): number | null {
  const v = f?.[key];
  return typeof v === 'number' ? v : null;
}

export function figureText(f: Figures | null | undefined, key: string): string | null {
  const v = f?.[key];
  return typeof v === 'string' && v !== '' ? v : null;
}

/** One /facts reply. An unsupported city or a missing snapshot is a 200
 *  with only `message` (and maybe `city`) — `facts` is absent then. */
export interface FactsResult {
  city?: string;
  city_name?: string;
  condition_label?: string;
  facts?: Figures;
  message?: string;
  /** Current conditions only: rain since local midnight (`rain_so_far_mm`,
   *  `since`) or, with no hourly history, the last 24 hours
   *  (`rain_last_24h_mm`); either with `rain_category`, `is_live`, `source`. */
  rain_so_far?: Figures;
}

export const factNumber = (r: FactsResult | null | undefined, key: string) => figure(r?.facts, key);
export const factText = (r: FactsResult | null | undefined, key: string) => figureText(r?.facts, key);

/** Canonical condition key (data/decoders/weather_conditions.json). */
export const factCondition = (r: FactsResult | null | undefined) => factText(r, 'condition');
export const factIsLive = (r: FactsResult | null | undefined) => r?.facts?.is_live === true;

/** One day of GET /forecast/daily: `label` (today / tomorrow / a weekday),
 *  `date` (YYYY-MM-DD), `condition` + `condition_label`, `night_condition`
 *  + `night_condition_label`, `high_c`, `low_c`, `rain_probability_pct`,
 *  `night_rain_probability_pct`, `rain_mm`, `wind_kmh`, `wind_dir`,
 *  `humidity_pct`, `uv_index`, `sunrise`, `sunset` — each only when served. */
export type ForecastDay = Figures;

/** One hour of GET /forecast/hourly: `time_iso`, `local_time` ("HH:MM",
 *  city-local), `date`, `temp_c`, `feels_like_c`, `rain_probability_pct`,
 *  `rain_mm`, `wind_kmh`, `condition` + `condition_label`, `uv_index`,
 *  `is_daytime`. */
export type ForecastHour = Figures;

/** GET /forecast/daily or /forecast/hourly: the entries plus the series'
 *  provenance. Empty `entries` means `status: unavailable`. */
export interface ForecastSeries {
  entries: Figures[];
  source: string | null;
  isLive: boolean;
  issued: string | null;
}

function series(json: Record<string, unknown>, key: string): ForecastSeries {
  const provenance = (json.provenance ?? {}) as Figures;
  const list = json[key];
  return {
    entries: Array.isArray(list) ? list.filter((e): e is Figures => e !== null && typeof e === 'object') : [],
    source: figureText(provenance, 'source'),
    isLive: provenance.is_live === true,
    issued: figureText(provenance, 'issued'),
  };
}

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
  const params: Record<string, string> = { city, intent, day };
  if (lang) params.lang = lang;
  return (await getJson('/facts', params)) as FactsResult;
}

/** Up to `days` days (the backend serves 1–10). */
export async function fetchDailyForecast({ city, lang, days = 10 }: { city: string; lang?: string; days?: number }) {
  const params: Record<string, string> = { city, days: String(days) };
  if (lang) params.lang = lang;
  return series(await getJson('/forecast/daily', params), 'days');
}

/** The next 24 hours. */
export async function fetchHourlyForecast({ city, lang }: { city: string; lang?: string }) {
  const params: Record<string, string> = { city };
  if (lang) params.lang = lang;
  return series(await getJson('/forecast/hourly', params), 'hours');
}

/** GET `path` with `params` from the orchestrator as a JSON object, with
 *  FactsError for every failure. Also used by lib/hotlines.ts and
 *  lib/glossary.ts. */
export async function getJson(path: string, params: Record<string, string>): Promise<Record<string, unknown>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FACTS_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}${path}?${new URLSearchParams(params).toString()}`, {
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new FactsError('http', 'The weather service replied HTTP {status}.', res.status, { status: res.status });
    }
    let json: unknown;
    try {
      json = await res.json();
    } catch {
      throw new FactsError('malformed', "The weather service's reply wasn't valid JSON.");
    }
    if (json === null || typeof json !== 'object' || Array.isArray(json)) {
      throw new FactsError('malformed', "The weather service's reply wasn't valid JSON.");
    }
    return json as Record<string, unknown>;
  } catch (err) {
    if (err instanceof FactsError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new FactsError('timeout', 'No answer within {seconds}s — the weather service timed out.', undefined, {
        seconds: Math.round(FACTS_TIMEOUT_MS / 1000),
      });
    }
    throw new FactsError(
      'network',
      "Couldn't reach the weather service at {url}. Is the orchestrator running?",
      undefined,
      { url: API_BASE_URL },
    );
  } finally {
    clearTimeout(timer);
  }
}
