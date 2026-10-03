// Alerts' three sources: /warnings (saved for an outage only), /hotlines
// (a saved list on any failure) and /glossary's colour legend.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeFetch, fakeLocalStorage } from '../test/fakes';
import { glossaryLegend, legendReviewed, parseGlossary } from './glossary';
import { fetchHotlines } from './hotlines';
import { fetchWarnings, WarningsError } from './warnings';

const entry = (text: string, native_qa = true) => ({ text, native_qa });

beforeEach(() => {
  fakeLocalStorage();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('glossary', () => {
  it('builds the legend green to red and knows whether it was reviewed', () => {
    const entries: Record<string, unknown> = {};
    for (const c of ['red', 'orange', 'yellow', 'green']) {
      entries[`colour_word_${c}`] = entry(`${c} (hi)`, c !== 'orange');
      entries[`colour_${c}`] = entry(`${c} means something`);
    }
    entries.category_rain = { text: 42 }; // malformed: dropped
    const g = parseGlossary({ entries });
    expect(glossaryLegend(g)?.map((r) => r.colour)).toEqual(['green', 'yellow', 'orange', 'red']);
    expect(glossaryLegend(g)?.[0]).toEqual({ colour: 'green', label: 'green (hi)', meaning: 'green means something' });
    expect(legendReviewed(g)).toBe(false);
    expect(g.category_rain).toBeUndefined();
    expect(glossaryLegend(parseGlossary({ entries: {} }))).toBeNull();
  });
});

describe('hotlines', () => {
  const reply = {
    city: 'chennai',
    checked: '2026-10-03',
    hotlines: [
      { number: '112', dial: '112', name: 'Emergency', note: 'Any emergency, anywhere in India' },
      { number: '1070', dial: '1070', name: 'State disaster helpline' },
      { number: 'n/a', dial: '' },
    ],
  };

  it('reads the dialable lines and when they were checked', async () => {
    fakeFetch(() => reply);
    const list = await fetchHotlines({ city: 'chennai', lang: 'en' });
    expect(list.lines.map((l) => l.dial)).toEqual(['112', '1070']);
    expect(list.lines[1].note).toBe('');
    expect(list.checked).toBe('2026-10-03');
  });

  it('a saved list on any failure, even a 404; nothing saved throws', async () => {
    fakeFetch(() => ({ status: 404 }));
    await expect(fetchHotlines({ city: 'chennai' })).rejects.toThrow();
    fakeFetch(() => reply);
    await fetchHotlines({ city: 'chennai' });
    fakeFetch(() => ({ status: 404 }));
    const saved = await fetchHotlines({ city: 'chennai' });
    expect(saved.lines).toHaveLength(2);
    expect(saved.savedAt).toBeInstanceOf(Date);
  });
});

describe('warnings', () => {
  it('derives the status an older backend leaves out', async () => {
    fakeFetch(() => ({ city: 'chennai', city_name: 'Chennai', warning: null }));
    expect((await fetchWarnings({ city: 'chennai' })).status).toBe('unavailable');
  });

  it('a saved verdict for an outage, never for a 404', async () => {
    const verdict = { city: 'chennai', city_name: 'Chennai', status: 'clear', warning: { colour: 'green' }, legend: [] };
    fakeFetch(() => verdict);
    expect((await fetchWarnings({ city: 'chennai', lang: 'en' })).savedAt).toBeNull();
    fakeFetch(() => ({ status: 503 }));
    expect((await fetchWarnings({ city: 'chennai', lang: 'en' })).savedAt).toBeInstanceOf(Date);
    fakeFetch(() => ({ status: 404 }));
    await expect(fetchWarnings({ city: 'chennai', lang: 'en' })).rejects.toThrow(WarningsError);
  });
});
