// Client for the orchestrator's GET /glossary (glossary.py, plan.md §3.1):
// the IMD warning colour words and their meanings, and the warning category
// labels, in one language, each flagged by whether a native speaker has
// reviewed it (`native_qa`). Alerts builds its colour legend from it rather
// than carry its own copy (mobile/lib/glossary_client.dart).
import type { LegendRow, WarningColour } from './api';
import { getJson } from './facts';

export interface GlossaryEntry {
  text: string;
  /** A native speaker has checked this translation (always true in English). */
  reviewed: boolean;
}

export type Glossary = Record<string, GlossaryEntry>;

const COLOURS: WarningColour[] = ['green', 'yellow', 'orange', 'red'];

export function parseGlossary(json: Record<string, unknown>): Glossary {
  const out: Glossary = {};
  const raw = json.entries;
  if (raw === null || typeof raw !== 'object') return out;
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const v = value as Record<string, unknown> | null;
    if (v && typeof v === 'object' && typeof v.text === 'string') out[key] = { text: v.text, reviewed: v.native_qa === true };
  }
  return out;
}

/** The colour legend, green to red; null when any colour is missing. */
export function glossaryLegend(g: Glossary | null): LegendRow[] | null {
  if (!g) return null;
  const rows: LegendRow[] = [];
  for (const colour of COLOURS) {
    const word = g[`colour_word_${colour}`];
    const meaning = g[`colour_${colour}`];
    if (!word || !meaning) return null;
    rows.push({ colour, label: word.text, meaning: meaning.text });
  }
  return rows;
}

/** Every legend text has had native review. */
export const legendReviewed = (g: Glossary) =>
  COLOURS.every((c) => g[`colour_word_${c}`]?.reviewed === true && g[`colour_${c}`]?.reviewed === true);

/** Throws on a failure; Alerts then keeps /warnings' own legend. */
export async function fetchGlossary({ lang }: { lang: string }): Promise<Glossary> {
  return parseGlossary(await getJson('/glossary', { lang }));
}
