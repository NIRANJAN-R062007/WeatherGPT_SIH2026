// Client for the orchestrator's GET /hotlines: a city's emergency numbers —
// 112, then its state's, district's and city's own lines — each read off an
// official government page (services/orchestrator/hotlines.py,
// data/hotlines.json; mobile/lib/hotlines_client.dart). `name` and `note`
// are English keys into ui-strings/ui_strings.json, translated where shown.
import { getJson } from './facts';

export interface Hotline {
  /** As shown: "1077", "040 2111 1111". */
  number: string;
  /** Digits only, for a tel: link. */
  dial: string;
  name: string;
  note: string;
}

export interface HotlineList {
  lines: Hotline[];
  /** When the numbers were last checked against their sources (YYYY-MM-DD). */
  checked: string | null;
}

/** 112 works anywhere in India (MHA's ERSS page, data/hotlines.json), so it
 *  is shown even when the list can't be fetched. */
export const EMERGENCY_HOTLINE: Hotline = {
  number: '112',
  dial: '112',
  name: 'Emergency',
  note: 'Any emergency, anywhere in India',
};

function hotline(json: unknown): Hotline | null {
  if (json === null || typeof json !== 'object') return null;
  const o = json as Record<string, unknown>;
  if (typeof o.number !== 'string' || typeof o.dial !== 'string' || o.dial === '') return null;
  return {
    number: o.number,
    dial: o.dial,
    name: typeof o.name === 'string' ? o.name : o.number,
    note: typeof o.note === 'string' ? o.note : '',
  };
}

/** Throws on any failure (no connection, an HTTP error, a backend from
 *  before /hotlines, an empty list); the caller falls back to
 *  EMERGENCY_HOTLINE. */
export async function fetchHotlines({ city, lang }: { city: string; lang?: string }): Promise<HotlineList> {
  const params: Record<string, string> = { city };
  if (lang) params.lang = lang;
  const json = await getJson('/hotlines', params);
  const lines = (Array.isArray(json.hotlines) ? json.hotlines : []).map(hotline).filter((h): h is Hotline => h !== null);
  if (lines.length === 0) throw new Error('no hotlines');
  return { lines, checked: typeof json.checked === 'string' ? json.checked : null };
}
