import { describe, expect, it } from 'vitest';
import {
  calendarDate,
  forecastDayName,
  hoursMinutes,
  istClock,
  istMinuteOfDay,
  millimetres,
  rainCategoryLabel,
  savedTimeLabel,
} from './format';
import type { T } from './i18n';

/** English: keys back with their placeholders filled. */
const t: T = (en, args) => en.replace(/\{(\w+)\}/g, (_, k: string) => String(args?.[k] ?? ''));

describe('format', () => {
  it('reads UTC instants as IST clock times', () => {
    expect(istClock('2026-10-03T00:28:22.940653695Z')).toBe('05:58');
    expect(istMinuteOfDay('2026-10-03T12:27:38Z')).toBe(17 * 60 + 57);
    expect(istClock('not a time')).toBe('');
    expect(istMinuteOfDay(null)).toBeNull();
  });

  it('names forecast days: Today / Tomorrow by label, else the weekday', () => {
    const date = calendarDate('2026-10-05');
    expect(forecastDayName(t, 'today', date)).toBe('Today');
    expect(forecastDayName(t, 'tomorrow', date)).toBe('Tomorrow');
    expect(forecastDayName(t, 'later', date)).toBe('Mon');
    expect(forecastDayName(t, 'later', null)).toBe('Later');
    expect(calendarDate('5 Oct')).toBeNull();
  });

  it('writes durations and rainfall like the app', () => {
    expect(hoursMinutes(t, 11 * 60 + 59)).toBe('11 h 59 min');
    expect(millimetres(0.81)).toBe('0.8 mm');
    expect(millimetres(12.4)).toBe('12 mm');
    expect(rainCategoryLabel('very_heavy')).toBe('Very heavy rain');
    expect(rainCategoryLabel('drizzle')).toBeNull();
  });

  it('labels a saved time by the clock today, with the date otherwise', () => {
    const now = new Date('2026-10-03T14:00:00Z'); // 19:30 IST
    expect(savedTimeLabel(t, new Date('2026-10-03T08:50:00Z'), now)).toBe('14:20 IST');
    expect(savedTimeLabel(t, new Date('2026-10-02T08:50:00Z'), now)).toBe('2 Oct, 14:20 IST');
  });
});
