import { apiBase } from '../config';
import type { AskResponse, City, FactsResponse, Lang, WarningsResponse } from './types';

export type ApiErrorKind = 'network' | 'timeout' | 'http';

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  detail?: string;

  constructor(kind: ApiErrorKind, message: string, status?: number, detail?: string) {
    super(message);
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string, params?: Record<string, string | undefined>): string {
  const url = new URL(apiBase + path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

export async function getJson<T>(
  path: string,
  params?: Record<string, string | undefined>,
  signal?: AbortSignal,
  timeoutMs = 12000,
): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;

  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), { signal: combined });
  } catch (err) {
    if (timeoutSignal.aborted) {
      throw new ApiError('timeout', 'Request timed out');
    }
    throw new ApiError('network', err instanceof Error ? err.message : 'Network error');
  }

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body.detail;
    } catch {
      // Non-JSON error body — leave detail undefined.
    }
    throw new ApiError('http', `HTTP ${res.status}`, res.status, detail);
  }

  return (await res.json()) as T;
}

export function fetchCities(signal?: AbortSignal): Promise<{ cities: City[] }> {
  return getJson<{ cities: City[] }>('/cities', undefined, signal);
}

export function fetchFacts(city: string, lang: Lang, signal?: AbortSignal): Promise<FactsResponse> {
  return getJson<FactsResponse>(
    '/facts',
    { city, intent: 'current_weather', day: 'today', lang },
    signal,
  );
}

export function fetchWarning(
  city: string,
  lang: Lang,
  signal?: AbortSignal,
): Promise<WarningsResponse> {
  return getJson<WarningsResponse>('/warnings', { city, lang }, signal);
}

export function ask(
  text: string,
  lang: Lang,
  city?: string,
  signal?: AbortSignal,
): Promise<AskResponse> {
  // LLM narration + Bhashini translation on free tiers can take ~20 s.
  return getJson<AskResponse>('/ask', { text, lang, city }, signal, 45000);
}
