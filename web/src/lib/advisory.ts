// Client for the orchestrator's POST /advisory/travel and /advisory/sowing
// (services/orchestrator/main.py's _advisory(), plan.md TFA-17; mobile
// advisory_client.dart): a short dialogue. Each reply is either
// - `ask_back`: one question for the slot still missing (travel: origin,
//   destination, day; sowing: crop, district), with the slots gathered so
//   far, which the next turn sends back; or
// - `ok`: a verdict (travel: go / caution / avoid; sowing: suitable /
//   not_suitable; either: not_available), the pros and cons behind it, maybe
//   a time window, provenance per data section and a disclaimer.
// The question is in the user's language; the pros and cons are English.
import { cityLabel } from '../data/cities';
import { API_BASE_URL } from './api';
import { FactsError } from './facts';
import { sentenceCase } from './format';
import type { T } from './i18n';

/** The agent may wait on an LLM and fall back to a template: /ask's budget. */
export const ADVISORY_TIMEOUT_MS = 30_000;

export type AdvisoryKind = 'travel' | 'sowing';

export interface AdvisoryReply {
  /** "ask_back" or "ok". */
  status: string;
  /** ask_back: what to ask the user, in their language. */
  question: string | null;
  /** The slots gathered so far (origin, destination, day, mode; crop,
   *  district): sent back with the next turn. */
  slots: Record<string, string>;
  /** ask_back: the slot `question` asks for, sent back with the answer. */
  asking: string | null;
  /** ok: go / caution / avoid, suitable / not_suitable, or not_available. */
  verdict: string | null;
  pros: string[];
  cons: string[];
  /** ok: the best window, "HH:MM" city-local, when there is one. */
  window: { start: string; end: string } | null;
  /** ok: the data sources behind the answer and whether all were live. */
  sources: string[];
  allLive: boolean;
  disclaimer: string | null;
}

const str = (v: unknown) => (typeof v === 'string' ? v : null);
const strings = (v: unknown) => (Array.isArray(v) ? v.filter((e): e is string => typeof e === 'string' && e !== '') : []);
const object = (v: unknown) => (v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

/** The slots in reading order (where from, where to, when, how; crop,
 *  where), each as the app shows it: a city's name, Today / Tomorrow, or the
 *  value capitalised. */
export function slotLabels(t: T, slots: Record<string, string>) {
  const labels: string[] = [];
  for (const key of ['origin', 'destination', 'day', 'mode', 'crop', 'district']) {
    const value = slots[key];
    if (!value) continue;
    if (key === 'origin' || key === 'destination' || key === 'district') labels.push(t(cityLabel(value)));
    else if (key === 'day' && (value === 'today' || value === 'tomorrow')) labels.push(t(sentenceCase(value)));
    else labels.push(sentenceCase(value));
  }
  return labels;
}

export function parseAdvisory(json: Record<string, unknown>): AdvisoryReply {
  const answer = object(json.answer);
  const w = object(answer.window);
  const provenance = (Array.isArray(json.provenance) ? json.provenance : []).map(object);
  const slots: Record<string, string> = {};
  for (const [k, v] of Object.entries(object(json.slots))) if (typeof v === 'string') slots[k] = v;
  const start = str(w.start_local);
  const end = str(w.end_local);
  return {
    status: str(json.status) ?? 'ok',
    question: str(json.question),
    slots,
    asking: str(json.asking),
    verdict: str(answer.verdict),
    pros: strings(answer.pros),
    cons: strings(answer.cons),
    window: start && end ? { start, end } : null,
    sources: [...new Set(provenance.map((p) => str(p.source)).filter((s): s is string => s !== null))],
    allLive: provenance.length > 0 && provenance.every((p) => p.is_live === true),
    disclaimer: str(json.disclaimer),
  };
}

/** One turn: `text` as typed, with the `slots` and `asking` of the last
 *  reply. Failures are FactsErrors, so they share the weather service's
 *  messages. */
export async function fetchAdvisory(
  kind: AdvisoryKind,
  { text, lang, slots = {}, asking }: { text: string; lang: string; slots?: Record<string, string>; asking?: string | null },
): Promise<AdvisoryReply> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ADVISORY_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/advisory/${kind}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, lang, slots, ...(asking ? { asking } : {}) }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new FactsError('timeout', 'No answer within {seconds}s — the weather service timed out.', undefined, {
        seconds: ADVISORY_TIMEOUT_MS / 1000,
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
  if (!res.ok) {
    throw new FactsError('http', 'The weather service replied HTTP {status}.', res.status, { status: res.status });
  }
  try {
    return parseAdvisory(object(await res.json()));
  } catch {
    throw new FactsError('malformed', "The weather service's reply wasn't valid JSON.");
  }
}
