/**
 * Weather → sky theme. The Ask page paints its whole shell in the current
 * weather of the city it's about; this module decides which sky that is.
 * The palettes and ambient layers themselves live in sky.css, keyed by the
 * `data-sky` attribute `useSky` puts on <html> (see that file's header for
 * how to preview one without live data).
 */

/** The looks a sky can have. `windy` shares cloudy's palette, not its motion. */
export type SkyFamily = 'clear' | 'partly' | 'cloudy' | 'windy' | 'rain' | 'storm';

export type SkyKey = `${SkyFamily}-${'day' | 'night'}`;

export type Glyph = 'sun' | 'cloud' | 'rain' | 'thunder' | 'wind';

/**
 * Canonical condition keys from data/decoders/weather_conditions.json. An
 * unmapped Google type reaches us lowercased (the decoder's `unknown_policy`),
 * hence the substring fallback below.
 */
const FAMILY_BY_CONDITION: Record<string, SkyFamily> = {
  clear: 'clear',
  mostly_clear: 'clear',
  partly_cloudy: 'partly',
  mostly_cloudy: 'cloudy',
  cloudy: 'cloudy',
  windy: 'windy',
  light_rain: 'rain',
  rain_showers: 'rain',
  rain: 'rain',
  heavy_rain: 'rain',
  thunderstorm: 'storm',
  thunderstorm_with_rain: 'storm',
  scattered_thunderstorms: 'storm',
};

/** `null` when the condition is missing or means nothing to us — no sky, plain paper. */
export function conditionFamily(condition: string | undefined): SkyFamily | null {
  if (!condition) return null;
  const c = condition.toLowerCase();
  const mapped = FAMILY_BY_CONDITION[c];
  if (mapped) return mapped;
  // Order matters: "thundershower" is a storm before it's rain.
  if (c.includes('thunder')) return 'storm';
  if (c.includes('rain') || c.includes('shower') || c.includes('drizzle')) return 'rain';
  if (c.includes('wind')) return 'windy';
  if (c.includes('cloud')) return 'cloudy';
  if (c.includes('clear') || c.includes('sunny')) return 'clear';
  return null;
}

const GLYPH_BY_FAMILY: Record<SkyFamily, Glyph> = {
  clear: 'sun',
  partly: 'cloud',
  cloudy: 'cloud',
  windy: 'wind',
  rain: 'rain',
  storm: 'thunder',
};

export function glyphFor(family: SkyFamily | null): Glyph {
  return family ? GLYPH_BY_FAMILY[family] : 'cloud';
}

/**
 * Day between 06:00 and 18:00 local time. Coarse, but the three cities are
 * all near 10°N, where sunrise and sunset drift under half an hour either
 * side of those all year — good enough to pick a palette. The observation
 * time is used rather than "now" so a fixture from 04:23 IST paints a night
 * sky, matching the timestamp the page prints next to it.
 */
export function isDaytime(observedAt: string | undefined, timeZone: string): boolean {
  const date = observedAt ? new Date(observedAt) : new Date();
  if (Number.isNaN(date.getTime())) return true;
  let hour: number;
  try {
    hour = Number(
      new Intl.DateTimeFormat('en-US', { hour: 'numeric', hourCycle: 'h23', timeZone }).format(date),
    );
  } catch {
    // Unknown time zone string — fall back to the viewer's clock.
    hour = date.getHours();
  }
  return hour >= 6 && hour < 18;
}

export function skyFor(
  condition: string | undefined,
  observedAt: string | undefined,
  timeZone: string,
): SkyKey | null {
  const family = conditionFamily(condition);
  if (!family) return null;
  return `${family}-${isDaytime(observedAt, timeZone) ? 'day' : 'night'}`;
}
