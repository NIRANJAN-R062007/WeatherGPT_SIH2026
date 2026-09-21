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

/**
 * Whether the feed had a verdict — `imd_warnings.STATUS_*` on the backend.
 * `unavailable` (feed switched off, which is every deploy's default, or no
 * fixture for the city) is not an all-clear and must never render green.
 */
export type WarningStatus = 'unavailable' | 'clear' | 'active';

export interface Warning {
  district: string;
  colour: WarningColour;
  colour_label: string; // glossary colour word in the requested language
  category: string | null; // the feed's own text, verbatim
  category_label: string; // glossary label for it (null category → "no warning")
  headline: string;
  advice: string;
  valid_from: string;
  valid_to: string;
  issued_by: string;
  source: string;
}

/** One row of the colour-code legend, from data/i18n/glossary.json. */
export interface LegendRow {
  colour: WarningColour;
  label: string;
  meaning: string;
}

export interface WarningsResponse {
  city: string;
  city_name: string;
  status?: WarningStatus; // absent from a backend older than the status field
  warning: Warning | null; // null exactly when status is 'unavailable'
  legend?: LegendRow[];
}

/**
 * A backend that predates `status`, or a payload whose `warning` doesn't
 * back its status, is treated as unavailable — never as an all-clear.
 */
export function warningStatus(r: WarningsResponse): WarningStatus {
  if ((r.status === 'active' || r.status === 'clear') && r.warning) return r.status;
  return 'unavailable';
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
