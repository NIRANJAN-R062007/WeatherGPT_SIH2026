// Travel and Sowing advice: the reply, the slots shown, and what a turn sends.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fakeFetch } from '../test/fakes';
import { fetchAdvisory, parseAdvisory, slotLabels } from './advisory';
import type { T } from './i18n';

const t: T = (en) => en;

const ANSWER = {
  kind: 'travel',
  status: 'ok',
  slots: { mode: 'train', day: 'tomorrow', destination: 'madurai', origin: 'chennai' },
  answer: {
    verdict: 'caution',
    pros: ['Rain chance at the origin is 15%.', ''],
    cons: ['The IMD warning for the destination is not available.'],
    window: { start_local: '09:00', end_local: '11:00' },
  },
  provenance: [
    { section: 'origin', source: 'Google Weather API (live)', is_live: true },
    { section: 'destination', source: 'Google Weather API (live)', is_live: true },
  ],
  disclaimer: 'Awareness only.',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('advisory', () => {
  it('an answer: verdict, reasons, window, one line per source', () => {
    const r = parseAdvisory(ANSWER);
    expect(r.verdict).toBe('caution');
    expect(r.pros).toEqual(['Rain chance at the origin is 15%.']);
    expect(r.window).toEqual({ start: '09:00', end: '11:00' });
    expect(r.sources).toEqual(['Google Weather API (live)']);
    expect(r.allLive).toBe(true);
    expect(parseAdvisory({ status: 'ask_back', question: 'From where?', asking: 'origin' }).window).toBeNull();
  });

  it('shows the trip in reading order, cities by name', () => {
    expect(slotLabels(t, ANSWER.slots)).toEqual(['Chennai', 'Madurai', 'Tomorrow', 'Train']);
    expect(slotLabels(t, { district: 'coimbatore', crop: 'paddy' })).toEqual(['Paddy', 'Coimbatore']);
  });

  it('a turn posts the text, the slots so far and what was asked', async () => {
    const sent = fakeFetch(() => ANSWER);
    await fetchAdvisory('sowing', { text: 'groundnut', lang: 'ta', slots: { district: 'madurai' }, asking: 'crop' });
    expect(sent[0].url).toMatch(/\/advisory\/sowing$/);
    expect(sent[0].method).toBe('POST');
    expect(sent[0].body).toEqual({ text: 'groundnut', lang: 'ta', slots: { district: 'madurai' }, asking: 'crop' });
    await fetchAdvisory('travel', { text: 'Chennai to Madurai', lang: 'en' });
    expect(sent[1].body).toEqual({ text: 'Chennai to Madurai', lang: 'en', slots: {} });
  });
});
