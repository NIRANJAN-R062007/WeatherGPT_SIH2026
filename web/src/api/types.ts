export type Lang = 'en' | 'ta' | 'hi' | 'te' | 'mr';

export interface City {
  key: string;
  lat: number;
  lon: number;
  names: Record<Lang, string>;
  region: { en: string; ta?: string };
  timezone: string;
}

export interface Facts {
  condition?: string;
  temp_c?: number;
  feels_like_c?: number;
  humidity_pct?: number;
  wind_kmh?: number;
  wind_dir?: string;
  uv_index?: number;
  issued?: string;
  source?: string;
  is_live?: boolean;
}

export interface FactsSuccess {
  city: string;
  city_name: string;
  condition_label: string;
  facts: Facts;
}

export interface FactsRefusal {
  city?: string;
  message: string;
}

export type FactsResponse = FactsSuccess | FactsRefusal;

export function isFactsSuccess(r: FactsResponse): r is FactsSuccess {
  return 'facts' in r;
}

export type WarningColour = 'green' | 'yellow' | 'orange' | 'red';

export interface Warning {
  district: string;
  colour: WarningColour;
  category: string | null;
  headline: string;
  advice: string;
  valid_from: string;
  valid_to: string;
  issued_by: string;
  source: string;
}

export interface WarningsResponse {
  city: string;
  city_name: string;
  warning: Warning | null;
}

export interface Grounding {
  ok: boolean;
  fallback_used: boolean;
  narration: string | null;
  attempts: number;
  provider: string | null;
}

export interface Provenance {
  source: string;
  issued?: string | null;
  is_live: boolean;
  retrieved_at: string;
}

export interface AskSuccess {
  intent: string;
  city?: string;
  day?: string;
  response: string;
  provenance?: Provenance;
  grounding: Grounding;
  nlu?: unknown;
  notice?: string;
}

export interface AskRefusal {
  intent: string;
  city?: string;
  message: string;
  nlu?: unknown;
  notice?: string;
}

export type AskResponse = AskSuccess | AskRefusal;

export function isAskSuccess(r: AskResponse): r is AskSuccess {
  return 'response' in r;
}
