// Typed client for the orchestrator's GET /climate endpoint: a demo city's
// rainfall and mean temperature history from Open-Meteo's ERA5 reanalysis, with
// the yearly and seasonal figures and trends already computed server-side
// (services/orchestrator/climate.py) — the page only draws and words them.
// ERA5 is a ~25 km model grid, NOT IMD station data; the payload's label, credit
// link and "computed by WeatherGPT" note go with every chart. Mirrors
// mobile/lib/climate_client.dart.
//
// A period without a complete set of days has a null figure: it is "missing",
// never zero (plan.md §2 principle 3), and the chart leaves a gap there.
// `status` "unavailable" means no data at all — "not available", never "no
// change".
import { useCallback, useRef, useState } from 'react';
import { API_BASE_URL } from './api';

/** A cold ERA5 fetch can take up to 30 s server-side (climate.py); the server
 *  caches the result for a day. */
export const CLIMATE_TIMEOUT_MS = 35_000;

export type ClimateMetric = 'rain' | 'temperature';
export type ClimatePeriod = 'year' | 'winter' | 'pre_monsoon' | 'monsoon' | 'post_monsoon';

export const CLIMATE_PERIODS: readonly ClimatePeriod[] = ['year', 'winter', 'pre_monsoon', 'monsoon', 'post_monsoon'];

/** The key of each metric in the payload's rows and trends, and its unit. */
export const METRIC_KEY = { rain: 'rain_mm', temperature: 'temp_mean_c' } as const;
export const METRIC_UNIT = { rain: 'mm', temperature: '°C' } as const;

export interface ClimateRow {
  year: number;
  season?: string;
  rain_mm: number | null;
  temp_mean_c: number | null;
}

/** An ordinary least-squares trend over the complete years (climate.linear_trend). */
export interface ClimateTrend {
  /** "ok", or "insufficient_data" with no slope. */
  status: string;
  n: number;
  first_year: number | null;
  last_year: number | null;
  mean: number | null;
  slope_per_decade: number | null;
  stderr_per_decade: number | null;
  /** Clear of year-to-year variation at the 95% level. False means "can't
   *  tell", not "no change". */
  significant_95: boolean;
}

type TrendPair = { rain_mm?: ClimateTrend; temp_mean_c?: ClimateTrend };

export interface ClimateResponse {
  /** "ok" or "unavailable" (never "unsupported_city": the route 404s on that). */
  status: 'ok' | 'unavailable';
  city: string;
  is_live: boolean;
  retrieved_at: string | null;
  requested: { start_date: string; end_date: string } | null;
  annual: ClimateRow[] | null;
  seasonal: ClimateRow[] | null;
  trends: { year?: TrendPair; season?: Record<string, TrendPair> } | null;
  /** "Open-Meteo / ERA5 reanalysis, not IMD station data". */
  label: string;
  credit: { text: string; url: string };
  changes_note: string;
  calendar_note: string;
  licence_url: string;
  terms_url: string;
  min_trend_years: number;
}

export type ClimateErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

export class ClimateError extends Error {
  readonly kind: ClimateErrorKind;

  constructor(kind: ClimateErrorKind, message: string) {
    super(message);
    this.name = 'ClimateError';
    this.kind = kind;
  }
}

export async function fetchClimate(city: string): Promise<ClimateResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CLIMATE_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}/climate?${new URLSearchParams({ city }).toString()}`, {
      signal: controller.signal,
    });
    if (!res.ok) {
      const detail = res.status === 404 ? 'No climate history for that city.' : `HTTP ${res.status}.`;
      throw new ClimateError('http', `The climate service replied ${detail}`);
    }
    let payload: unknown;
    try {
      payload = await res.json();
    } catch {
      throw new ClimateError('malformed', "The climate service's reply wasn't valid JSON.");
    }
    if (payload === null || typeof payload !== 'object' || !('status' in payload) || !('city' in payload)) {
      throw new ClimateError('malformed', "The climate service's reply didn't look like climate history.");
    }
    return payload as ClimateResponse;
  } catch (err) {
    if (err instanceof ClimateError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ClimateError('timeout', 'The climate service took too long to answer.');
    }
    throw new ClimateError(
      'network',
      `Couldn't reach the climate service at ${API_BASE_URL}. Is the orchestrator running?`,
    );
  } finally {
    clearTimeout(timer);
  }
}

export interface ClimateState {
  /** The city key the displayed result answers. */
  city: string | null;
  loading: boolean;
  data: ClimateResponse | null;
  error: ClimateError | null;
}

const IDLE: ClimateState = { city: null, loading: false, data: null, error: null };

/** /climate call state: one request at a time, a late reply from a superseded
 *  request (a fast city switch) dropped. */
export function useClimate() {
  const [state, setState] = useState<ClimateState>(IDLE);
  const requestId = useRef(0);

  const load = useCallback(async (city: string) => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await fetchClimate(city);
      if (requestId.current !== id) return;
      setState({ city, loading: false, data, error: null });
    } catch (err) {
      if (requestId.current !== id) return;
      const error =
        err instanceof ClimateError ? err : new ClimateError('network', 'Something went wrong talking to the climate service.');
      setState({ city, loading: false, data: null, error });
    }
  }, []);

  return { ...state, load };
}

// --- reading the payload ----------------------------------------------------

export interface YearValue {
  year: number;
  /** Null when the year (or season) has missing days. */
  value: number | null;
}

const finite = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** Each year's figure for [period] and [metric], oldest first. A year with
 *  missing days has a null value, not zero. */
export function seriesOf(data: ClimateResponse, period: ClimatePeriod, metric: ClimateMetric): YearValue[] {
  const rows = (period === 'year' ? data.annual : data.seasonal?.filter((r) => r.season === period)) ?? [];
  const key = METRIC_KEY[metric];
  return rows
    .filter((r) => Number.isInteger(r.year))
    .map((r) => ({ year: r.year, value: finite(r[key]) }))
    .sort((a, b) => a.year - b.year);
}

/** The trend for [period] and [metric], or null if the payload has none. */
export function trendOf(data: ClimateResponse, period: ClimatePeriod, metric: ClimateMetric): ClimateTrend | null {
  const pair = period === 'year' ? data.trends?.year : data.trends?.season?.[period];
  const t = pair?.[METRIC_KEY[metric]];
  return t && typeof t.status === 'string' ? t : null;
}

/** True when the trend has a slope to draw and word. */
export function hasSlope(t: ClimateTrend | null): boolean {
  return !!t && t.status === 'ok' && finite(t.slope_per_decade) !== null && finite(t.mean) !== null;
}

/** The trend line's value in [year]: it passes through (mean year, mean value)
 *  of the complete years with the server's slope. */
export function trendValueAt(t: ClimateTrend, year: number, meanYear: number): number {
  return (t.mean as number) + ((t.slope_per_decade as number) / 10) * (year - meanYear);
}

/** Mean of the years that have a value — the x the least-squares line is centred on. */
export function meanYearOf(series: YearValue[]): number {
  const years = series.filter((p) => p.value !== null).map((p) => p.year);
  return years.length ? years.reduce((a, b) => a + b, 0) / years.length : 0;
}

/** A step of 1, 2 or 5 × 10ⁿ giving about `target` intervals over `span`. */
export function niceStep(span: number, target: number): number {
  if (!(span > 0)) return 1;
  const raw = span / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
}

/** "1,035 mm" / "28.2 °C"; `slope` keeps a sign and one more decimal for the
 *  small temperature changes per decade. */
export function formatClimate(v: number, metric: ClimateMetric, slope = false): string {
  const digits = metric === 'rain' ? (slope || Math.abs(v) < 100 ? 1 : 0) : slope ? 2 : 1;
  const body = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const sign = v < 0 ? '−' : slope ? '+' : '';
  return `${sign}${body} ${METRIC_UNIT[metric]}`;
}

export const METRIC_NAME: Record<ClimateMetric, string> = { rain: 'Rainfall', temperature: 'Temperature' };

export const PERIOD_NAME: Record<ClimatePeriod, string> = {
  year: 'Whole year',
  winter: 'Winter (Jan–Feb)',
  pre_monsoon: 'Pre-monsoon (Mar–May)',
  monsoon: 'Monsoon (Jun–Sep)',
  post_monsoon: 'Post-monsoon (Oct–Dec)',
};
