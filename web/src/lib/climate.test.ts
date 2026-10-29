// The climate client and the helpers the Climate trends page draws and words
// from: reading a series and its trend out of /climate's body (a year with
// missing days stays null, never zero), the trend line, number formatting, and
// the fetch's error handling.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { climateBody, trend } from '../test/climateFixture';
import { fakeFetch } from '../test/fakes';
import {
  ClimateError,
  fetchClimate,
  formatClimate,
  hasSlope,
  meanYearOf,
  niceStep,
  seriesOf,
  trendOf,
  trendValueAt,
} from './climate';

afterEach(() => vi.unstubAllGlobals());

describe('seriesOf', () => {
  it('reads the yearly series oldest first; a year with missing days is null, not zero', () => {
    const rain = seriesOf(climateBody(), 'year', 'rain');
    expect(rain[0]).toEqual({ year: 1996, value: 940 });
    expect(rain[rain.length - 1]).toEqual({ year: 2026, value: null });
    expect(rain.filter((p) => p.value === null)).toHaveLength(1);
  });

  it('reads one season whatever order the rows come in', () => {
    const body = climateBody();
    body.seasonal = [...(body.seasonal ?? [])].reverse();
    const monsoon = seriesOf(body, 'monsoon', 'rain');
    expect(monsoon).toHaveLength(31);
    expect(monsoon.map((p) => p.year)).toEqual(Array.from({ length: 31 }, (_, i) => 1996 + i));
    expect(monsoon[0].value).toBe(300);
  });

  it('is empty when the data is absent', () => {
    expect(seriesOf(climateBody({ annual: null, seasonal: null }), 'year', 'rain')).toEqual([]);
  });
});

describe('trendOf and hasSlope', () => {
  it('finds the year and season trends', () => {
    const body = climateBody();
    expect(trendOf(body, 'year', 'temperature')?.slope_per_decade).toBe(0.243);
    expect(trendOf(body, 'monsoon', 'rain')?.slope_per_decade).toBe(20);
    expect(trendOf(body, 'post_monsoon', 'rain')).toBeNull();
  });

  it('only a status "ok" trend with a slope and a mean has a slope to draw', () => {
    expect(hasSlope(trend())).toBe(true);
    expect(hasSlope(trend({ status: 'insufficient_data', slope_per_decade: null, mean: null }))).toBe(false);
    expect(hasSlope(null)).toBe(false);
  });
});

describe('the trend line', () => {
  it('passes through (mean year, mean value) and moves by the slope per decade', () => {
    const t = trend({ mean: 100, slope_per_decade: 10 });
    expect(trendValueAt(t, 2000, 2000)).toBe(100);
    expect(trendValueAt(t, 2010, 2000)).toBe(110);
    expect(trendValueAt(t, 1990, 2000)).toBe(90);
  });

  it('is centred on the years that have a value', () => {
    expect(meanYearOf([{ year: 2000, value: 1 }, { year: 2001, value: null }, { year: 2002, value: 3 }])).toBe(2001);
  });
});

describe('niceStep', () => {
  it.each([
    [1000, 4, 500],
    [3.4, 4, 1],
    [0.8, 4, 0.2],
    [0, 4, 1],
  ])('%d over about %d intervals -> %d', (span, target, step) => {
    expect(niceStep(span, target)).toBeCloseTo(step);
  });
});

describe('formatClimate', () => {
  it('rain: thousands grouped, one decimal below 100, a signed slope with a decimal', () => {
    expect(formatClimate(1034.83, 'rain')).toBe('1,035 mm');
    expect(formatClimate(68.34, 'rain')).toBe('68.3 mm');
    expect(formatClimate(84.021, 'rain', true)).toBe('+84.0 mm');
    expect(formatClimate(-1.925, 'rain', true)).toBe('−1.9 mm');
  });

  it('temperature: one decimal, two for a slope', () => {
    expect(formatClimate(28.2, 'temperature')).toBe('28.2 °C');
    expect(formatClimate(0.243, 'temperature', true)).toBe('+0.24 °C');
  });
});

describe('fetchClimate', () => {
  it('asks GET /climate?city= and returns the body', async () => {
    const sent = fakeFetch(() => climateBody());
    const data = await fetchClimate('chennai');
    expect(sent[0].url).toMatch(/\/climate\?city=chennai$/);
    expect(data.city).toBe('chennai');
  });

  it('a 404 says there is no history for the city; a 500 is an http error', async () => {
    fakeFetch(() => ({ status: 404 }));
    await expect(fetchClimate('patna')).rejects.toThrow('No climate history for that city.');
    fakeFetch(() => ({ status: 500 }));
    await expect(fetchClimate('chennai')).rejects.toMatchObject({ kind: 'http' });
  });

  it('no connection and a body that is not climate history are errors, not empty data', async () => {
    fakeFetch(() => new Error('offline'));
    await expect(fetchClimate('chennai')).rejects.toMatchObject({ kind: 'network' });
    fakeFetch(() => ({ hello: 'world' }));
    await expect(fetchClimate('chennai')).rejects.toBeInstanceOf(ClimateError);
    await expect(fetchClimate('chennai')).rejects.toMatchObject({ kind: 'malformed' });
  });
});
