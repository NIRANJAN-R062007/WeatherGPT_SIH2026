import { useState } from 'react';
import AskAnswer from '../components/AskAnswer';
import { CITIES } from '../data/cities';
import { useAsk } from '../lib/useAsk';
import { useUiPrefs } from '../state/UiPrefsContext';

// Sent as the /ask `city` hint; only consulted when the question names no city.
const DEFAULT_CITY_HINT = 'chennai';

const SUGGESTIONS = [
  '🌧️ Will it rain tomorrow in Colaba?',
  '📅 5-day South Mumbai forecast',
];

export default function ChatPage() {
  const [showEvidence, setShowEvidence] = useState(false);
  const { lang } = useUiPrefs();
  const [query, setQuery] = useState('');
  const [cityHint, setCityHint] = useState(DEFAULT_CITY_HINT);
  const { asked, loading, outcome, error, ask } = useAsk();

  // Suggestion chips carry a leading emoji for the UI; /ask gets the words only.
  const submit = (text: string) => void ask(text.replace(/^\p{Extended_Pictographic}+\s*/u, ''), lang, cityHint);

  return (
    <div className="flex flex-col w-full gap-space-lg">

<div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">

<div className="xl:col-span-8 flex flex-col gap-space-md min-w-0">

<div className="flex flex-col gap-space-lg">

{/* Everything between here and the composer below is the original static
    design sample — hardcoded Colaba copy, not wired to /ask. The live
    ask/answer flow is the composer card at the bottom of this column. */}
<div className="flex items-center gap-2 font-citation-mono text-citation-mono text-outline uppercase tracking-wider">
<span className="material-symbols-outlined text-[14px]">design_services</span>
<span>Static design sample — not live data</span>
<span className="flex-1 h-px bg-outline-variant/50" />
</div>


<div className="flex justify-end pl-12">
<div className="bg-primary text-on-primary p-space-md rounded-2xl rounded-br-none shadow-md max-w-2xl flex flex-col gap-1.5">
<div className="flex items-center justify-end font-citation-mono text-citation-mono text-primary-fixed">
<span>08:34 IST</span>
</div>
<p className="font-body-lg text-body-lg text-on-primary font-medium">
              Will it rain in Colaba, Mumbai this evening? Need to plan an outdoor event.
            </p>
</div>
</div>

<div className="flex flex-col gap-space-sm pr-2">

<div className="bg-surface-container-lowest rounded-2xl rounded-bl-none p-space-lg shadow-sm flex flex-col gap-space-md">

<div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-secondary-container text-on-secondary-container font-label-md text-label-md font-semibold w-fit" title="Grounded against a live weather data response">
<span className="material-symbols-outlined text-[16px]">verified_user</span>
<span>Verified &amp; Live</span>
</div>

<div className="flex flex-col gap-2">
<p className="font-headline-sm text-headline-sm text-on-surface">
                Thunderstorm &amp; High-Precipitation Outlook: Colaba Coastal Tract
              </p>
<p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed">
<span className="text-primary font-semibold">Yes, significant rain is forecasted.</span> There is an <strong className="text-on-surface">82% probability</strong> of thunderstorms and moderate-to-heavy rain in Colaba between <strong className="text-on-surface">17:00 and 21:00 IST today</strong>. Peak precipitation rate is expected around <strong className="text-on-surface">18:30 IST (up to 12.4 mm/hr)</strong> accompanied by south-westerly wind gusts reaching up to <strong className="text-on-surface">38 km/h</strong>.
              </p>
</div>

<div className="bg-surface-container-low p-space-md rounded-xl flex flex-col gap-space-xs">
<div className="flex items-center justify-between font-label-md text-label-md text-on-surface-variant">
<span className="font-medium text-on-surface">Hourly Rain Distribution</span>
</div>

<div className="w-full h-20 pt-2">
<svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 540 60">

<rect className="fill-surface-container-high" height="12" rx="4" width="55" x="10" y="48"></rect>
<text className="fill-outline font-citation-mono text-[10px]" textAnchor="middle" x="37" y="42">15%</text>

<rect className="fill-primary-fixed-dim" height="28" rx="4" width="55" x="80" y="32"></rect>
<text className="fill-on-surface-variant font-citation-mono text-[10px]" textAnchor="middle" x="107" y="26">45%</text>

<rect className="fill-primary" height="50" rx="4" width="55" x="150" y="10"></rect>
<text className="fill-primary font-citation-mono text-[11px] font-bold" textAnchor="middle" x="177" y="6">82% (12mm)</text>

<rect className="fill-primary-container" height="40" rx="4" width="55" x="220" y="20"></rect>
<text className="fill-on-surface-variant font-citation-mono text-[10px]" textAnchor="middle" x="247" y="15">68%</text>

<rect className="fill-surface-container-high" height="22" rx="4" width="55" x="290" y="38"></rect>
<text className="fill-outline font-citation-mono text-[10px]" textAnchor="middle" x="317" y="32">35%</text>

<rect className="fill-surface-container-high" height="15" rx="4" width="55" x="360" y="45"></rect>
<text className="fill-outline font-citation-mono text-[10px]" textAnchor="middle" x="387" y="39">20%</text>

<rect className="fill-surface-container-high" height="10" rx="4" width="55" x="430" y="50"></rect>
<text className="fill-outline font-citation-mono text-[10px]" textAnchor="middle" x="457" y="44">10%</text>
</svg>
</div>
<div className="grid grid-cols-7 text-center font-citation-mono text-citation-mono text-outline-variant pt-1">
<span>14:00</span>
<span>16:00</span>
<span className="text-primary font-bold">18:00</span>
<span>20:00</span>
<span>22:00</span>
<span>00:00</span>
<span>02:00</span>
</div>
</div>

<div className="flex flex-wrap items-center justify-between gap-space-sm pt-space-xs">
<div className="flex flex-wrap items-center gap-space-xs">
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md transition-colors shadow-sm" type="button">
<span className="material-symbols-outlined text-[18px] text-primary">volume_up</span>
<span>Listen (EN / हिन्दी)</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md transition-colors shadow-sm" type="button">
<span className="material-symbols-outlined text-[18px] text-secondary">ios_share</span>
<span>Share Advisory</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed hover:bg-surface-container-highest text-on-primary-fixed font-label-md text-label-md transition-colors" onClick={() => setShowEvidence((v) => !v)} type="button">
<span className="material-symbols-outlined text-[18px]">terminal</span>
<span>{showEvidence ? 'Hide Sources' : 'View Sources'}</span>
</button>
</div>
</div>
</div>
</div>
</div>

<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm mt-space-xs">

<div className="flex items-center gap-2 font-citation-mono text-citation-mono text-primary uppercase tracking-wider">
<span className="material-symbols-outlined text-[14px]">bolt</span>
<span>Live — answers come from /ask</span>
<span className="flex-1 h-px bg-outline-variant/50" />
</div>

<AskAnswer asked={asked} detail error={error} loading={loading} outcome={outcome} />

<div className="flex items-center gap-2 overflow-x-auto pb-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider shrink-0">Suggested:</span>
{SUGGESTIONS.map((s) => (
<button
  className="shrink-0 px-3 py-1 rounded-full bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center gap-1.5 disabled:opacity-60"
  disabled={loading}
  key={s}
  onClick={() => {
    setQuery(s);
    submit(s);
  }}
  type="button"
>
<span>{s}</span>
</button>
))}
</div>

<form
  className="flex flex-col gap-space-xs"
  onSubmit={(e) => {
    e.preventDefault();
    submit(query);
  }}
>
<div className="flex items-center gap-space-sm bg-surface-container-low p-2 rounded-xl">
<button className="p-2 rounded-lg bg-surface-container-lowest hover:bg-surface-container text-on-surface-variant hover:text-primary transition-colors flex items-center justify-center shadow-sm" title="Multilingual Voice Input" type="button">
<span className="material-symbols-outlined text-[20px]">mic</span>
</button>
<input
  className="flex-1 bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface placeholder:text-outline px-2"
  onChange={(e) => setQuery(e.target.value)}
  placeholder="Ask WeatherGPT in English, हिंदी, मराठी, தமிழ்..."
  type="text"
  value={query}
/>
<div className="flex items-center gap-1.5 shrink-0">
<button
  className="p-2.5 rounded-lg bg-primary hover:bg-primary-container text-on-primary transition-colors flex items-center justify-center shadow-md disabled:opacity-60 disabled:cursor-not-allowed"
  disabled={loading || query.trim() === ''}
  title="Send"
  type="submit"
>
{loading ? (
  <span className="block w-[20px] h-[20px] rounded-full border-2 border-on-primary/40 border-t-on-primary animate-spin" />
) : (
  <span className="material-symbols-outlined text-[20px]">send</span>
)}
</button>
</div>
</div>

{/* City hint for /ask — used only when the question itself names no city. */}
<label className="flex items-center gap-1.5 px-1 font-citation-mono text-citation-mono text-on-surface-variant">
<span className="material-symbols-outlined text-[14px]">my_location</span>
<span>IF UNSPECIFIED, ASSUME</span>
<select
  className="bg-surface-container-low text-on-surface rounded px-1.5 py-1 font-label-md text-label-md focus:outline-none"
  onChange={(e) => setCityHint(e.target.value)}
  value={cityHint}
>
{CITIES.map((c) => (
<option key={c.key} value={c.key}>{c.name}</option>
))}
</select>
<span className="text-outline">· LANG {lang.toUpperCase()}</span>
</label>
</form>
</div>
</div>

<div className="xl:col-span-4 flex flex-col gap-space-md min-w-0">

{showEvidence && (
<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-primary text-[22px]">data_object</span>
<span className="font-headline-sm text-[16px] text-on-surface font-bold uppercase tracking-tight">Sources</span>
</div>

<div className="flex flex-col gap-2 font-citation-mono text-citation-mono">

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Rain Prob (18:00 IST)</span>
<span className="text-primary font-bold text-body-md">82%</span>
</div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              Hourly Forecast
            </div>
</div>

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Wind Gust</span>
<span className="text-on-surface font-bold text-body-md">38 km/h SW</span>
</div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              Hourly Forecast
            </div>
</div>
</div>
</div>
)}

<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-on-surface-variant text-[22px]">history</span>
<span className="font-headline-sm text-[16px] text-on-surface font-bold uppercase tracking-tight">Chat History</span>
</div>
<a className="font-citation-mono text-citation-mono text-primary hover:underline" href="#">VIEW ALL</a>
</div>

<div className="flex flex-col gap-1.5">

<button className="text-left flex flex-col gap-1 p-2.5 rounded-xl bg-primary-container/40 hover:bg-primary-container/60 transition-colors" type="button">
<div className="flex items-center justify-between gap-2">
<span className="font-label-md text-label-md font-semibold text-on-surface truncate">Will it rain in Colaba, Mumbai this evening?</span>
<span className="font-citation-mono text-[10px] text-outline shrink-0">Now</span>
</div>
<span className="font-body-sm text-[11px] text-on-surface-variant truncate">82% thunderstorm probability, 17:00–21:00 IST</span>
</button>

<button className="text-left flex flex-col gap-1 p-2.5 rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors" type="button">
<div className="flex items-center justify-between gap-2">
<span className="font-label-md text-label-md font-medium text-on-surface truncate">What's the weather like this weekend?</span>
<span className="font-citation-mono text-[10px] text-outline shrink-0">Yesterday</span>
</div>
<span className="font-body-sm text-[11px] text-on-surface-variant truncate">Pune, Kothrud — 5-day outlook</span>
</button>

<button className="text-left flex flex-col gap-1 p-2.5 rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors" type="button">
<div className="flex items-center justify-between gap-2">
<span className="font-label-md text-label-md font-medium text-on-surface truncate">Is it safe to be outside at noon today?</span>
<span className="font-citation-mono text-[10px] text-outline shrink-0">2 days ago</span>
</div>
<span className="font-body-sm text-[11px] text-on-surface-variant truncate">Chennai, T. Nagar — UV Index</span>
</button>

</div>
</div>
</div>
</div>
</div>
  );
}
