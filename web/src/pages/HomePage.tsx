import { useEffect, useMemo, useState } from 'react';
import AskAnswer from '../components/AskAnswer';
import { CITIES } from '../data/cities';
import { useAsk } from '../lib/useAsk';
import { useUiPrefs } from '../state/UiPrefsContext';

// Sunrise/sunset are the same mock IST values shown in the sub-panel below;
// CONDITION mirrors the mock "Partly Cloudy" label. Both are real inputs to
// the gradient math (real current time, real condition->color mapping) —
// once this page gets live weather data, swapping these two constants for
// fetched state is the only change needed to make the gradient fully live.
const SUNRISE_IST = '06:32';
const SUNSET_IST = '18:14';
const CONDITION: keyof typeof CONDITION_META = 'partly_cloudy';

const CONDITION_META = {
  clear: { label: 'Clear', icon: 'sunny', accent: '#9d6a00' }, // tertiary-container
  partly_cloudy: { label: 'Partly Cloudy', icon: 'partly_cloudy_day', accent: '#006ef3' }, // primary-container
  cloudy: { label: 'Cloudy', icon: 'cloud', accent: '#727786' }, // outline
  rain: { label: 'Rain', icon: 'rainy', accent: '#006a6a' }, // secondary
  storm: { label: 'Thunderstorms', icon: 'thunderstorm', accent: '#1d3052' }, // inverse-surface
} as const;

const MOOD_TINT = {
  dawn: '#ffba46', // tertiary-fixed-dim — soft sunrise gold
  day: '#f1f3ff', // surface-container-low — bright neutral
  dusk: '#9d6a00', // tertiary-container — warm sunset amber
  night: '#1d3052', // inverse-surface — deep night blue
} as const;

type Mood = keyof typeof MOOD_TINT;

function toMinutes(hhmm: string) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

function minutesToHHMM(mins: number) {
  const m = ((Math.round(mins) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

function minutesToDuration(mins: number) {
  const m = Math.max(0, Math.round(mins));
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function nowMinutesIST(date: Date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const h = Number(parts.find((p) => p.type === 'hour')?.value ?? '0');
  const m = Number(parts.find((p) => p.type === 'minute')?.value ?? '0');
  return h * 60 + m;
}

const TRANSITION_WINDOW_MIN = 40;

// Sent as the /ask `city` hint. It only matters when the question names no
// city — the NLU's own extraction from the text always wins over it.
const DEFAULT_CITY_HINT = 'chennai';

const QUICK_QUERY = 'When will heavy rain start today?';

function getDayMood(nowMin: number, sunriseMin: number, sunsetMin: number): Mood {
  if (Math.abs(nowMin - sunriseMin) <= TRANSITION_WINDOW_MIN) return 'dawn';
  if (Math.abs(nowMin - sunsetMin) <= TRANSITION_WINDOW_MIN) return 'dusk';
  if (nowMin > sunriseMin && nowMin < sunsetMin) return 'day';
  return 'night';
}

export default function HomePage() {
  const [now, setNow] = useState(() => new Date());
  const { lang } = useUiPrefs();
  const [query, setQuery] = useState('');
  const [cityHint, setCityHint] = useState(DEFAULT_CITY_HINT);
  const { asked, loading, outcome, error, ask } = useAsk();

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const sunriseMin = toMinutes(SUNRISE_IST);
  const sunsetMin = toMinutes(SUNSET_IST);
  const solarNoonMin = (sunriseMin + sunsetMin) / 2;
  const nowMin = nowMinutesIST(now);
  const totalDaylightMin = sunsetMin - sunriseMin;
  const elapsedMin = Math.min(Math.max(nowMin - sunriseMin, 0), totalDaylightMin);
  const remainingMin = totalDaylightMin - elapsedMin;
  const dayProgressPct = totalDaylightMin > 0 ? (elapsedMin / totalDaylightMin) * 100 : 0;

  const mood = useMemo(
    () => getDayMood(nowMin, sunriseMin, sunsetMin),
    [nowMin, sunriseMin, sunsetMin],
  );
  const condition = CONDITION_META[CONDITION];
  const heroGradient = `linear-gradient(135deg, #f1f3ff 0%, ${MOOD_TINT[mood]}33 55%, ${condition.accent}4d 100%)`;
  const chipGradient = `linear-gradient(135deg, ${condition.accent}4d 0%, ${MOOD_TINT[mood]}1a 60%, transparent 100%)`;

  return (
    <div className="flex flex-col w-full gap-space-lg">

<section
  className="rounded-2xl bg-[length:200%_200%] animate-gradient-drift p-space-lg shadow-sm flex flex-col gap-space-lg"
  style={{ backgroundImage: heroGradient }}
>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-end">

<div
  className="lg:col-span-6 flex flex-col sm:flex-row items-start sm:items-center gap-space-lg p-space-md rounded-xl"
  style={{ backgroundImage: chipGradient }}
>
<div className="flex items-baseline gap-2">
<span className="font-metric-display text-metric-display text-on-surface font-extrabold leading-none tracking-tighter">
            29°
          </span>
<span className="font-headline-sm text-headline-sm text-on-surface-variant">C</span>
</div>
<div className="flex flex-col">
<div className="flex items-center gap-2 text-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[26px]">{condition.icon}</span>
            {condition.label}
          </div>
<div className="flex items-center gap-3 mt-1 font-body-md text-body-md text-on-surface-variant">
<span>Feels like <strong className="font-semibold text-on-surface">33°C</strong></span>
</div>
</div>
</div>

<div className="lg:col-span-6 flex flex-col justify-end bg-surface-container-low p-space-md rounded-xl gap-2">
<div className="flex items-start justify-between font-citation-mono text-citation-mono text-on-surface-variant">
<span className="flex flex-col items-start gap-0.5">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-tertiary">wb_sunny</span>Sunrise</span>
<span className="text-on-surface font-semibold">{SUNRISE_IST}</span>
</span>
<span className="flex flex-col items-center gap-0.5">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">wb_twilight</span>Solar Noon</span>
<span className="text-on-surface font-semibold">{minutesToHHMM(solarNoonMin)}</span>
</span>
<span className="flex flex-col items-end gap-0.5">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-tertiary">bedtime</span>Sunset</span>
<span className="text-on-surface font-semibold">{SUNSET_IST}</span>
</span>
</div>

<div className="relative h-1.5 rounded-full bg-gradient-to-r from-tertiary-fixed-dim via-primary-container to-tertiary-container">
<div
  className="absolute top-1/2 w-3 h-3 rounded-full bg-surface-container-lowest border-2 border-primary shadow-sm"
  style={{ left: `${Math.min(Math.max(dayProgressPct, 0), 100)}%`, transform: 'translate(-50%, -50%)' }}
/>
</div>

<div className="flex items-center justify-between font-citation-mono text-citation-mono text-on-surface-variant">
<span>Daylight Elapsed <strong className="text-on-surface font-semibold">{minutesToDuration(elapsedMin)}</strong></span>
<span className="px-2 py-0.5 rounded bg-surface-container text-on-surface font-semibold">UV Index: 4.8 (Moderate)</span>
<span>Remaining <strong className="text-on-surface font-semibold">{minutesToDuration(remainingMin)}</strong></span>
</div>
</div>
</div>

<div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-space-md">
<div className="flex flex-col gap-1 p-2.5 rounded-xl bg-primary-container text-on-primary-container">
<span className="font-citation-mono text-citation-mono opacity-80">HUMIDITY</span>
<div className="flex items-center gap-1 font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px]">humidity_high</span>
          78%
        </div>
</div>
<div className="flex flex-col gap-1 p-2.5 rounded-xl bg-secondary-container text-on-secondary-container">
<span className="font-citation-mono text-citation-mono opacity-80">WIND</span>
<div className="flex items-center gap-1 font-headline-sm text-headline-sm font-semibold">
{/* mock wind bearing: 45° (NE) — decorative, matches the icon's default heading */}
<span className="material-symbols-outlined text-[18px]" style={{ transform: 'rotate(45deg)' }}>north_east</span>
          14 km/h
        </div>
</div>
<div className="flex flex-col gap-1 p-2.5 rounded-xl bg-primary-container text-on-primary-container">
<span className="font-citation-mono text-citation-mono opacity-80">PRECIPITATION</span>
<div className="flex items-center gap-1 font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px]">rainy</span>
          35%
        </div>
</div>
<div className="flex flex-col gap-1 p-2.5 rounded-xl bg-primary-container text-on-primary-container">
<span className="font-citation-mono text-citation-mono opacity-80">RAIN SO FAR TODAY</span>
<div className="flex items-center gap-1 font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px]">water_drop</span>
          6.2mm
        </div>
</div>
</div>

<div className="flex flex-col gap-2 pt-space-sm">
<div className="flex items-center justify-between">
<span className="font-citation-mono text-citation-mono text-on-surface-variant">5-DAY OUTLOOK</span>
</div>
<div className="flex gap-2 overflow-x-auto pb-space-xs scroll-smooth">

<div className="flex-shrink-0 w-20 p-2 rounded-xl bg-primary text-on-primary shadow-sm flex flex-col items-center gap-1">
<span className="font-citation-mono text-[10px] font-bold uppercase tracking-wide">Today</span>
<span className="material-symbols-outlined text-[22px] text-secondary-fixed">thunderstorm</span>
<div className="flex items-baseline gap-1 font-label-md text-label-md font-semibold">
<span>31°</span>
<span className="opacity-70 text-[11px]">24°</span>
</div>
<div className="w-full h-1 rounded-full bg-on-primary/25 overflow-hidden">
<div className="h-full rounded-full bg-on-primary/90 w-[70%] ml-[10%]"></div>
</div>
<span className="flex items-center gap-0.5 font-citation-mono text-[10px]">
<span className="material-symbols-outlined text-[12px]">umbrella</span>82%
</span>
</div>

<div className="flex-shrink-0 w-20 p-2 rounded-xl bg-surface-container-low text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col items-center gap-1">
<span className="font-citation-mono text-[10px] text-on-surface-variant font-medium">Fri</span>
<span className="material-symbols-outlined text-[22px] text-primary">rainy</span>
<div className="flex items-baseline gap-1 font-label-md text-label-md font-semibold">
<span>30°</span>
<span className="text-on-surface-variant text-[11px]">23°</span>
</div>
<div className="w-full h-1 rounded-full bg-surface-container-high overflow-hidden">
<div className="h-full rounded-full bg-primary w-[70%] ml-[0%]"></div>
</div>
<span className="flex items-center gap-0.5 font-citation-mono text-[10px] text-on-surface-variant">
<span className="material-symbols-outlined text-[12px] text-primary">umbrella</span>65%
</span>
</div>

<div className="flex-shrink-0 w-20 p-2 rounded-xl bg-surface-container-low text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col items-center gap-1">
<span className="font-citation-mono text-[10px] text-on-surface-variant font-medium">Sat</span>
<span className="material-symbols-outlined text-[22px] text-tertiary">partly_cloudy_day</span>
<div className="flex items-baseline gap-1 font-label-md text-label-md font-semibold">
<span>32°</span>
<span className="text-on-surface-variant text-[11px]">25°</span>
</div>
<div className="w-full h-1 rounded-full bg-surface-container-high overflow-hidden">
<div className="h-full rounded-full bg-primary w-[70%] ml-[20%]"></div>
</div>
<span className="flex items-center gap-0.5 font-citation-mono text-[10px] text-on-surface-variant">
<span className="material-symbols-outlined text-[12px] text-primary">umbrella</span>30%
</span>
</div>

<div className="flex-shrink-0 w-20 p-2 rounded-xl bg-surface-container-low text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col items-center gap-1">
<span className="font-citation-mono text-[10px] text-on-surface-variant font-medium">Sun</span>
<span className="material-symbols-outlined text-[22px] text-tertiary">sunny</span>
<div className="flex items-baseline gap-1 font-label-md text-label-md font-semibold">
<span>33°</span>
<span className="text-on-surface-variant text-[11px]">25°</span>
</div>
<div className="w-full h-1 rounded-full bg-surface-container-high overflow-hidden">
<div className="h-full rounded-full bg-primary w-[80%] ml-[20%]"></div>
</div>
<span className="flex items-center gap-0.5 font-citation-mono text-[10px] text-on-surface-variant">
<span className="material-symbols-outlined text-[12px] text-primary">umbrella</span>15%
</span>
</div>

<div className="flex-shrink-0 w-20 p-2 rounded-xl bg-surface-container-low text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col items-center gap-1">
<span className="font-citation-mono text-[10px] text-on-surface-variant font-medium">Mon</span>
<span className="material-symbols-outlined text-[22px] text-primary">rainy_heavy</span>
<div className="flex items-baseline gap-1 font-label-md text-label-md font-semibold">
<span>29°</span>
<span className="text-on-surface-variant text-[11px]">23°</span>
</div>
<div className="w-full h-1 rounded-full bg-surface-container-high overflow-hidden">
<div className="h-full rounded-full bg-primary w-[60%] ml-[0%]"></div>
</div>
<span className="flex items-center gap-0.5 font-citation-mono text-[10px] text-on-surface-variant">
<span className="material-symbols-outlined text-[12px] text-primary">umbrella</span>88%
</span>
</div>

</div>
</div>
</section>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">

<div className="lg:col-span-8 flex flex-col gap-space-lg">

<div className="grid grid-cols-1 sm:grid-cols-2 gap-space-md">

<section className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group">
<div className="flex items-center justify-between">
<div className="w-9 h-9 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center group-hover:scale-105 transition-transform">
<span className="material-symbols-outlined text-[20px]">mic</span>
</div>
<span className="font-citation-mono text-[10px] text-primary font-bold">AI AUDIO</span>
</div>
<div className="mt-3">
<span className="font-label-md text-label-md font-bold text-on-surface block">Voice Assistant</span>
<p className="font-body-sm text-[11px] text-on-surface-variant mt-0.5 leading-tight">
            Ask in हिंदी, தமிழ், मराठी, or English
          </p>
</div>
</section>

<section className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group">
<div className="flex items-center justify-between">
<div className="w-9 h-9 rounded-xl bg-secondary-container text-on-secondary-container flex items-center justify-center group-hover:scale-105 transition-transform">
<span className="material-symbols-outlined text-[20px]">translate</span>
</div>
<span className="font-citation-mono text-[10px] text-secondary font-bold">5 LANGUAGES</span>
</div>
<div className="mt-3">
<span className="font-label-md text-label-md font-bold text-on-surface block">Multilingual Answers</span>
<p className="font-body-sm text-[11px] text-on-surface-variant mt-0.5 leading-tight">
            Narration translated, numbers stay grounded
          </p>
</div>
</section>

</div>

<section className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md flex-1">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-[20px] text-on-surface-variant">history</span>
<span className="font-headline-sm text-headline-sm font-bold text-on-surface">Recently Asked</span>
</div>
<a className="font-citation-mono text-citation-mono text-primary hover:underline" href="#">VIEW ALL</a>
</div>

<div className="flex flex-col gap-space-sm">

<button className="text-left flex flex-col gap-1.5 p-space-md rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors" type="button">
<div className="flex items-center justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2 py-0.5 rounded-full bg-surface-container-high text-primary font-citation-mono text-[10px] font-medium">PRECIPITATION FORECAST</span>
<span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[12px]">location_on</span> Mumbai, Colaba
            </span>
</div>
<span className="font-citation-mono text-[10px] text-outline shrink-0">Today, 08:34 IST</span>
</div>
<div className="flex items-baseline gap-2">
<span className="material-symbols-outlined text-primary text-[16px] shrink-0">chat</span>
<span className="font-body-md text-body-md text-on-surface leading-snug">"Will it rain in Colaba, Mumbai this evening?"</span>
</div>
</button>

<button className="text-left flex flex-col gap-1.5 p-space-md rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors" type="button">
<div className="flex items-center justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2 py-0.5 rounded-full bg-surface-container-high text-primary font-citation-mono text-[10px] font-medium">FORECAST</span>
<span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[12px]">location_on</span> Pune, Kothrud
            </span>
</div>
<span className="font-citation-mono text-[10px] text-outline shrink-0">Yesterday, 19:02 IST</span>
</div>
<div className="flex items-baseline gap-2">
<span className="material-symbols-outlined text-primary text-[16px] shrink-0">chat</span>
<span className="font-body-md text-body-md text-on-surface leading-snug">"What's the weather like this weekend?"</span>
</div>
</button>

<button className="text-left flex flex-col gap-1.5 p-space-md rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors" type="button">
<div className="flex items-center justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2 py-0.5 rounded-full bg-surface-container-high text-primary font-citation-mono text-[10px] font-medium">UV INDEX</span>
<span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[12px]">location_on</span> Chennai, T. Nagar
            </span>
</div>
<span className="font-citation-mono text-[10px] text-outline shrink-0">2 days ago, 12:47 IST</span>
</div>
<div className="flex items-baseline gap-2">
<span className="material-symbols-outlined text-primary text-[16px] shrink-0">chat</span>
<span className="font-body-md text-body-md text-on-surface leading-snug">"Is it safe to be outside at noon today?"</span>
</div>
</button>

</div>
</section>
</div>

<div className="lg:col-span-4 flex flex-col gap-space-lg">

<section className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-on-primary">
<span className="material-symbols-outlined text-[16px]">smart_toy</span>
</div>
<span className="font-headline-sm text-headline-sm font-bold text-on-surface">WeatherGPT Copilot</span>
</div>
</div>

<div className="flex flex-col gap-1.5">
<span className="font-citation-mono text-citation-mono text-on-surface-variant">QUICK SITUATIONAL INQUIRIES</span>
<div className="flex flex-col gap-1.5">
<button
  className="text-left px-3 py-2 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center justify-between group disabled:opacity-60"
  disabled={loading}
  onClick={() => {
    setQuery(QUICK_QUERY);
    void ask(QUICK_QUERY, lang, cityHint);
  }}
  type="button"
>
<span>"{QUICK_QUERY}"</span>
<span className="material-symbols-outlined text-outline group-hover:text-primary text-[16px]">north_east</span>
</button>
</div>
</div>

<form
  className="flex flex-col gap-2 mt-1"
  onSubmit={(e) => {
    e.preventDefault();
    void ask(query, lang, cityHint);
  }}
>
<div className="relative flex items-center">
<input
  className="w-full pl-3 pr-20 py-3 rounded-xl bg-surface-container text-on-surface placeholder:text-on-surface-variant/70 font-body-md text-body-md focus:outline-none focus:bg-surface-container-low transition-colors shadow-inner"
  onChange={(e) => setQuery(e.target.value)}
  placeholder="Ask WeatherGPT..."
  type="text"
  value={query}
/>
<div className="absolute right-2 flex items-center gap-1">
<button className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-highest transition-colors" title="Voice Search" type="button">
<span className="material-symbols-outlined text-[20px]">mic</span>
</button>
<button
  className="p-1.5 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-colors shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
  disabled={loading || query.trim() === ''}
  title="Submit Query"
  type="submit"
>
{loading ? (
  <span className="block w-[18px] h-[18px] rounded-full border-2 border-on-primary/40 border-t-on-primary animate-spin" />
) : (
  <span className="material-symbols-outlined text-[18px]">send</span>
)}
</button>
</div>
</div>

{/* City hint for /ask — used only when the question itself names no city. */}
<label className="flex items-center gap-1.5 font-citation-mono text-citation-mono text-on-surface-variant">
<span className="material-symbols-outlined text-[14px]">my_location</span>
<span>IF UNSPECIFIED, ASSUME</span>
<select
  className="flex-1 min-w-0 bg-surface-container-low text-on-surface rounded px-1.5 py-1 font-label-md text-label-md focus:outline-none"
  onChange={(e) => setCityHint(e.target.value)}
  value={cityHint}
>
{CITIES.map((c) => (
  <option key={c.key} value={c.key}>{c.name}</option>
))}
</select>
</label>

</form>

<AskAnswer asked={asked} error={error} loading={loading} outcome={outcome} />
</section>
</div>
</div>
</div>
  );
}
