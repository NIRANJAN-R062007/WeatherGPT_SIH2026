// Display helpers shared by the pages (mobile/lib/format.dart). IST is a
// fixed +05:30 with no DST.
import type { T } from './i18n';

const IST = 'Asia/Kolkata';

function parts(d: Date) {
  const f = new Intl.DateTimeFormat('en-GB', {
    timeZone: IST,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const get = (type: string) => f.find((p) => p.type === type)?.value ?? '';
  return { day: get('day'), month: get('month'), hour: Number(get('hour')) % 24, minute: get('minute') };
}

/** The current hour in IST (0–23). */
export function istHour(now = new Date()) {
  return parts(now).hour;
}

/** "13:49 IST" — the raw string back if it doesn't parse. */
export function istTime(iso: string | null | undefined) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = parts(d);
  return `${String(p.hour).padStart(2, '0')}:${p.minute} IST`;
}

/** "13:49" — istTime without the zone, for tight rows; '' if unparseable. */
export function istClock(iso: string | null | undefined) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return '';
  const p = parts(d);
  return `${String(p.hour).padStart(2, '0')}:${p.minute}`;
}

/** Minutes past IST midnight of `iso`, for placing it on a day's timeline. */
export function istMinuteOfDay(iso: string | null | undefined) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return null;
  const p = parts(d);
  return p.hour * 60 + Number(p.minute);
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** A calendar date ("2026-10-03") as a UTC-midnight Date; null if it isn't one. */
export function calendarDate(s: string | null | undefined) {
  const m = s ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(s) : null;
  return m ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))) : null;
}

/** "3 Oct" for a calendar date, the month in the app language. */
export function dayMonth(t: T, date: Date) {
  return `${date.getUTCDate()} ${t(MONTHS[date.getUTCMonth()])}`;
}

/** A forecast day's name: "Today" and "Tomorrow" by the backend's `label`,
 *  else the short weekday of `date` ("Mon"). */
export function forecastDayName(t: T, label: string | null, date: Date | null) {
  if (label === 'today') return t('Today');
  if (label === 'tomorrow') return t('Tomorrow');
  return date ? t(WEEKDAYS[date.getUTCDay()]) : t('Later');
}

/** "11 h 59 min". */
export function hoursMinutes(t: T, minutes: number) {
  return t('{h} h {m} min', { h: Math.floor(minutes / 60), m: Math.round(minutes % 60) });
}

/** "0.6 mm": one decimal below 10 mm, whole millimetres above. */
export function millimetres(mm: number) {
  return `${mm < 10 ? mm.toFixed(1) : Math.round(mm)} mm`;
}

/** IMD rain categories (data/decoders/precipitation_categories.json) as
 *  ui_strings.json keys; null for a key this table doesn't know. */
export function rainCategoryLabel(key: string | null) {
  const labels: Record<string, string> = {
    no_rain: 'No rain',
    light: 'Light rain',
    moderate: 'Moderate rain',
    heavy: 'Heavy rain',
    very_heavy: 'Very heavy rain',
    extremely_heavy: 'Extremely heavy rain',
  };
  return key ? (labels[key] ?? null) : null;
}

/** "27 Sep" for `iso`, or for today + `fallbackOffsetDays` when absent. */
export function istDayMonth(iso: string | null | undefined, fallbackOffsetDays = 0) {
  let d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) d = new Date(Date.now() + fallbackOffsetDays * 86_400_000);
  const p = parts(d);
  return `${p.day} ${p.month}`;
}

/** "light rain" -> "Light rain" (condition_label is lowercase in English). */
export function sentenceCase(s: string | null | undefined) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Night in IST, for choosing moon glyphs. */
export function isNightIst(now = new Date()) {
  const h = istHour(now);
  return h >= 19 || h < 6;
}
