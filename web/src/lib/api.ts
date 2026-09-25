// Typed client for the orchestrator's GET /ask endpoint.
//
// Every interface below mirrors one `resp` literal that
// services/orchestrator/main.py's `ask()` actually returns — no invented
// fields. The shapes were also captured from a live orchestrator on :8001
// (2026-09-26) before they were typed, including the two warnings branches
// (WARNINGS_ENABLED off -> `message`, on -> `response` + `warning`).
//
// /ask is a GET with query params, not a JSON POST: ?text=&lang=&city=.

// `or default`, not `??`: an env var that is *set but empty*
// (VITE_API_BASE_URL=) must fall back too, the same gotcha config.py guards
// against on the backend side.
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL;
export const API_BASE_URL: string =
  typeof RAW_BASE_URL === 'string' && RAW_BASE_URL.trim() !== ''
    ? RAW_BASE_URL.trim().replace(/\/+$/, '')
    : 'http://localhost:8001';

// Generous on purpose. /ask is synchronous over the whole NLU + weather +
// narration chain, and the slow paths are real: a `next_n_days` forecast
// measured 4.7 s on a good run, but when the primary LLM is degraded (Gemini
// was returning 503 during this wiring) the Gemini->Groq fallback pushed the
// same query past 15 s and a live 5-day forecast was aborted mid-flight.
export const ASK_TIMEOUT_MS = 30_000;

// ---------------------------------------------------------------------------
// Sub-objects shared across branches
// ---------------------------------------------------------------------------

/** `pq.as_dict()` — nlu.py's ParsedQuery dataclass, verbatim. */
export interface Nlu {
  intent: string;
  /** The city string the NLU pulled out of the question, NOT a resolved key.
   *  Stays set (e.g. "Kolkata") on the unsupported_city branch, where the
   *  top-level `city` is absent. */
  city: string | null;
  time_window: string;
  days: number | null;
  parameter: string;
  /** null when the requested language isn't supported — that's what puts
   *  `notice` on the response. */
  language: string | null;
  /** "rules" | "llm" | "rules_fallback" */
  source: string;
  confidence: number;
}

/** One numeric token guardrail.check() extracted from the narration.
 *  `path` is the raw-data path it matched, or null when it matched nothing. */
export interface GroundingFigure {
  reading: string;
  value: number;
  unit: string | null;
  path: string | null;
  matched: boolean;
}

/** asdict(guardrail.Report) plus the four keys main.py merges in. */
export interface Grounding {
  ok: boolean;
  matched: number;
  total: number;
  figures: GroundingFigure[];
  fallback_used: boolean;
  /** "llm" | "llm+bhashini" | "template" | "verbatim" */
  narration: string;
  attempts: number;
  /** "gemini" | "groq" | "ollama" | "template" | "feed" */
  provider: string;
}

/** main.py's `_provenance(data)` — the weather-data branches. */
export interface WeatherProvenance {
  source: string;
  issued: string | null;
  is_live: boolean;
  retrieved_at: string;
}

/** The warnings branch builds its provenance inline instead of calling
 *  `_provenance`, so it has `issued_by`/`valid_from`/`valid_to` and NO
 *  `issued`. Deliberately a separate type rather than optional fields. */
export interface WarningProvenance {
  source: string;
  issued_by: string;
  valid_from: string;
  valid_to: string;
  is_live: boolean;
  retrieved_at: string;
}

export type Provenance = WeatherProvenance | WarningProvenance;

export type WarningColour = 'green' | 'yellow' | 'orange' | 'red';

/** imd_warnings.public()'s flattened `warning` object. */
export interface WarningDetail {
  city: string;
  district: string;
  colour: WarningColour;
  colour_label: string;
  /** The feed's own category text; null when there's no warning category. */
  category: string | null;
  category_label: string;
  headline: string;
  /** Feed text. Known gap (plan.md audit 4.3): stays English in every lang. */
  advice: string;
  valid_from: string;
  valid_to: string;
  issued_by: string;
  /** "fixture" today; a real feed name once one is wired. */
  source: string;
}

/** glossary.legend(lang) — always four rows, in COLOURS order. */
export interface LegendRow {
  colour: WarningColour;
  label: string;
  meaning: string;
}

/** imd_warnings STATUS_* */
export type WarningStatus = 'unavailable' | 'clear' | 'active';

// ---------------------------------------------------------------------------
// The five response branches
// ---------------------------------------------------------------------------

/** Weather intent, narration passed the guardrail. The only branch with `day`. */
export interface AskSuccessResponse {
  intent: string;
  /** Resolved city key, lowercase (e.g. "chennai"), not a display name. */
  city: string;
  /** router.legacy_day(pq): a time_window, or "next_<n>_days". */
  day: string;
  response: string;
  provenance: WeatherProvenance;
  grounding: Grounding;
  nlu: Nlu;
  notice?: string;
}

/** `warnings` intent with a usable feed verdict. Its `response` is the feed's
 *  headline verbatim — no LLM narration, no guardrail pass. */
export interface AskWarningsResponse {
  intent: 'warnings';
  city: string;
  response: string;
  status: 'clear' | 'active';
  warning: WarningDetail;
  legend: LegendRow[];
  provenance: WarningProvenance;
  /** Stub report: provider "feed", narration "verbatim", 0 figures. */
  grounding: Grounding;
  nlu: Nlu;
  notice?: string;
}

/** `warnings` intent, feed off or fixture unusable. Carries `message` instead
 *  of `response` and has NO provenance — explicitly not an all-clear. */
export interface AskWarningsUnavailableResponse {
  intent: 'warnings';
  city: string;
  message: string;
  status: 'unavailable';
  warning: null;
  legend: LegendRow[];
  nlu: Nlu;
  notice?: string;
}

/** Guardrail rejected the narration (plan.md §2.3). The distinguishing shape:
 *  `message` AND `provenance`/`grounding`, but no `response` and no `day`. */
export interface AskUngroundedResponse {
  intent: string;
  city: string;
  message: string;
  provenance: WeatherProvenance;
  grounding: Grounding;
  nlu: Nlu;
  notice?: string;
}

/** unrecognized / unsupported_city / out_of_scope (no `city` at all),
 *  the "which city?" refusal (no `city`), and no_data (`city` present).
 *  Never has provenance or grounding. */
export interface AskFallbackResponse {
  intent: string;
  city?: string;
  message: string;
  nlu: Nlu;
  notice?: string;
}

export type AskResponse =
  | AskSuccessResponse
  | AskWarningsResponse
  | AskWarningsUnavailableResponse
  | AskUngroundedResponse
  | AskFallbackResponse;

// ---------------------------------------------------------------------------
// Runtime discrimination
// ---------------------------------------------------------------------------

export type AskOutcome =
  | { kind: 'success'; data: AskSuccessResponse }
  | { kind: 'warnings'; data: AskWarningsResponse }
  | { kind: 'warnings-unavailable'; data: AskWarningsUnavailableResponse }
  | { kind: 'ungrounded'; data: AskUngroundedResponse }
  | { kind: 'fallback'; data: AskFallbackResponse };

/** Sort a raw /ask body into its branch. Order matters:
 *  - `intent === "warnings"` returns early in main.py, so it can never be a
 *    weather success; inside it, `response` vs `message` splits the two.
 *  - a success also carries `grounding`, so `response` must be checked before
 *    the ungrounded test.
 *  - ungrounded is the only `message` branch that carries `grounding`.
 */
export function classifyAsk(data: AskResponse): AskOutcome {
  if (data.intent === 'warnings') {
    return 'response' in data
      ? { kind: 'warnings', data: data as AskWarningsResponse }
      : { kind: 'warnings-unavailable', data: data as AskWarningsUnavailableResponse };
  }
  if ('response' in data) {
    return { kind: 'success', data: data as AskSuccessResponse };
  }
  if ('grounding' in data) {
    return { kind: 'ungrounded', data: data as AskUngroundedResponse };
  }
  return { kind: 'fallback', data: data as AskFallbackResponse };
}

// ---------------------------------------------------------------------------
// The call
// ---------------------------------------------------------------------------

export type AskErrorKind = 'http' | 'network' | 'timeout' | 'malformed';

/** Thrown by askWeather for anything that isn't a parsed 2xx body. A /ask
 *  branch that merely refuses to answer is a resolved AskResponse, not this. */
export class AskError extends Error {
  readonly kind: AskErrorKind;
  readonly status: number | undefined;

  constructor(kind: AskErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'AskError';
    this.kind = kind;
    this.status = status;
  }
}

export interface AskParams {
  text: string;
  /** One of i18n.SUPPORTED_LANGUAGES; anything else silently becomes "en". */
  lang?: string;
  /** City hint only — the NLU's own extraction from `text` wins over it. */
  city?: string;
  /** Sent as `Authorization: Bearer <token>`; makes the backend record the
   *  call to /history, best-effort. Omitted when absent. */
  token?: string;
}

export async function askWeather({ text, lang, city, token }: AskParams): Promise<AskResponse> {
  const params = new URLSearchParams({ text });
  if (lang) params.set('lang', lang);
  if (city) params.set('city', city);

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ASK_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_BASE_URL}/ask?${params.toString()}`, {
      signal: controller.signal,
      headers,
    });
    if (!res.ok) {
      throw new AskError('http', `The weather service replied HTTP ${res.status}.`, res.status);
    }
    let payload: unknown;
    try {
      payload = await res.json();
    } catch {
      throw new AskError('malformed', "The weather service's reply wasn't valid JSON.");
    }
    if (payload === null || typeof payload !== 'object' || !('intent' in payload)) {
      throw new AskError('malformed', "The weather service's reply didn't look like an answer.");
    }
    return payload as AskResponse;
  } catch (err) {
    if (err instanceof AskError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new AskError(
        'timeout',
        `No answer within ${Math.round(ASK_TIMEOUT_MS / 1000)}s — the weather service timed out.`,
      );
    }
    throw new AskError(
      'network',
      `Couldn't reach the weather service at ${API_BASE_URL}. Is the orchestrator running?`,
    );
  } finally {
    clearTimeout(timer);
  }
}
