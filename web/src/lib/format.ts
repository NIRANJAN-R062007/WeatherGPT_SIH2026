// Display helpers shared by the pages (mobile/lib/format.dart). IST is a
// fixed +05:30 with no DST.

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
