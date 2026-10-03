// The forecast series and the offline rules: what a saved copy still says
// at a later time, and when a saved copy may stand in at all.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeFetch, fakeLocalStorage } from '../test/fakes';
import {
  FactsError,
  fetchDailyForecast,
  fetchFacts,
  freshDaily,
  freshFacts,
  freshHourly,
  isWeatherOutage,
  type ForecastSeries,
} from './facts';

const DAILY = {
  city: 'chennai',
  status: 'ok',
  days: [
    { label: 'today', date: '2026-10-03', high_c: 32.4, low_c: 26.8 },
    { label: 'tomorrow', date: '2026-10-04', high_c: 32 },
    { label: 'later', date: '2026-10-05', high_c: 33 },
    'not a day',
  ],
  provenance: { source: 'Google Weather API (live)', is_live: true, issued: '2026-10-03T14:30:00Z' },
};

const saved = (entries: Record<string, unknown>[]): ForecastSeries => ({
  entries,
  source: null,
  isLive: true,
  issued: null,
  savedAt: new Date('2026-10-03T10:00:00Z'),
});

beforeEach(() => {
  fakeLocalStorage();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('forecast series', () => {
  it('reads the days and the provenance; a non-object entry is dropped', async () => {
    const sent = fakeFetch(() => DAILY);
    const daily = await fetchDailyForecast({ city: 'chennai', lang: 'ta' });
    expect(daily.entries).toHaveLength(3);
    expect(daily.source).toBe('Google Weather API (live)');
    expect(daily.isLive).toBe(true);
    expect(daily.savedAt).toBeNull();
    expect(sent[0].url).toContain('/forecast/daily?city=chennai&days=10&lang=ta');
  });

  it('a 404 (a backend before /forecast/daily) is an error with its status', async () => {
    fakeFetch(() => ({ status: 404 }));
    const err = await fetchDailyForecast({ city: 'chennai' }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(FactsError);
    expect((err as FactsError).status).toBe(404);
    expect((err as FactsError).args).toEqual({ status: 404 });
  });
});

describe('offline', () => {
  it('only an outage lets a saved copy stand in', () => {
    expect(isWeatherOutage(new FactsError('network', 'x'))).toBe(true);
    expect(isWeatherOutage(new FactsError('timeout', 'x'))).toBe(true);
    expect(isWeatherOutage(new FactsError('http', 'x', 502))).toBe(true);
    expect(isWeatherOutage(new FactsError('http', 'x', 404))).toBe(false);
    expect(isWeatherOutage(new FactsError('malformed', 'x'))).toBe(false);
  });

  it('a reply is saved, and comes back with its saved time when the backend is out', async () => {
    fakeFetch(() => ({ city: 'chennai', facts: { temp_c: 29 } }));
    const fresh = await fetchFacts({ city: 'chennai', lang: 'en' });
    expect(fresh.savedAt).toBeNull();

    fakeFetch(() => new TypeError('Failed to fetch'));
    const offline = await fetchFacts({ city: 'chennai', lang: 'en' });
    expect(offline.facts).toEqual({ temp_c: 29 });
    expect(offline.savedAt).toBeInstanceOf(Date);

    // "It answered no" is not an outage: the error, not the saved copy.
    fakeFetch(() => ({ status: 422 }));
    await expect(fetchFacts({ city: 'chennai', lang: 'en' })).rejects.toThrow(FactsError);
  });

  it('no saved copy: the original error', async () => {
    fakeFetch(() => new TypeError('Failed to fetch'));
    await expect(fetchFacts({ city: 'madurai' })).rejects.toMatchObject({ kind: 'network' });
  });

  it('saved current conditions stand next day, without yesterday\'s rain; forecast periods go', () => {
    const r = { facts: { temp_c: 29 }, rain_so_far: { rain_so_far_mm: 0.8 }, savedAt: new Date('2026-10-03T10:00:00Z') };
    const sameDay = new Date('2026-10-03T17:00:00Z'); // 22:30 IST
    const nextDay = new Date('2026-10-03T19:00:00Z'); // 00:30 IST on the 4th
    expect(freshFacts(r, sameDay, true)).toBe(r);
    expect(freshFacts(r, nextDay, true)).toEqual({ facts: { temp_c: 29 }, savedAt: r.savedAt });
    expect(freshFacts(r, nextDay, false)).toBeNull();
    expect(freshFacts({ ...r, savedAt: null }, nextDay, false)).not.toBeNull();
  });

  it('a saved day list starts today, relabelled by date', () => {
    const d = saved(DAILY.days.slice(0, 3) as Record<string, unknown>[]);
    const next = freshDaily(d, new Date('2026-10-04T06:00:00Z'))!;
    expect(next.entries.map((e) => [e.date, e.label])).toEqual([
      ['2026-10-04', 'today'],
      ['2026-10-05', 'tomorrow'],
    ]);
    expect(freshDaily(d, new Date('2026-10-09T06:00:00Z'))).toBeNull();
  });

  it('a saved hourly series loses the hours that have ended', () => {
    const h = saved([
      { time_iso: '2026-10-03T14:30:00Z' },
      { time_iso: '2026-10-03T15:30:00Z' },
      { time_iso: '2026-10-03T16:30:00Z' },
    ]);
    const kept = freshHourly(h, new Date('2026-10-03T15:45:00Z'))!;
    expect(kept.entries.map((e) => e.time_iso)).toEqual(['2026-10-03T15:30:00Z', '2026-10-03T16:30:00Z']);
    expect(freshHourly(h, new Date('2026-10-04T00:00:00Z'))).toBeNull();
  });
});
