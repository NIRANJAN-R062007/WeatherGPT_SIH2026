import { useEffect, useState } from 'react';
import { Legend } from '../components/AskAnswer';
import { CITIES } from '../data/cities';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useWarnings, type WarningsVerdict } from '../lib/warnings';
import { COLOUR_BAR, COLOUR_TEXT, istTimestamp } from '../lib/warningUi';

function LiveVerdict({ data }: { data: WarningsVerdict }) {
  return (
    <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-low">
      <div className={`h-1.5 rounded-full ${COLOUR_BAR[data.warning.colour]}`} />
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`flex items-center gap-1 font-label-md text-label-md font-bold ${COLOUR_TEXT[data.warning.colour]}`}>
          <span className="material-symbols-outlined text-[18px]">
            {data.status === 'active' ? 'warning' : 'check_circle'}
          </span>
          {data.warning.colour_label}
          {data.status === 'active' ? ' — in force' : ' — nothing in force'}
        </span>
        <span className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-citation-mono text-[10px] font-medium">
          <span className="material-symbols-outlined text-[11px] align-middle">location_on</span> {data.city_name}
        </span>
        <span className="px-2 py-0.5 rounded-full bg-surface-container-high text-primary font-citation-mono text-[10px] font-medium">
          {data.warning.category_label}
        </span>
      </div>
      <p className="font-body-lg text-body-lg text-on-surface leading-relaxed">{data.warning.headline}</p>
      <p className="font-body-md text-body-md text-on-surface-variant">{data.warning.advice}</p>
      <Legend highlight={data.warning.colour} rows={data.legend} />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-space-xs border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
        <span className="flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">campaign</span>
          {data.warning.issued_by}
        </span>
        <span>
          Valid {istTimestamp(data.warning.valid_from)} → {istTimestamp(data.warning.valid_to)}
        </span>
        <span className="text-outline">source: {data.warning.source}</span>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  const [showGeofence, setShowGeofence] = useState(false);
  const { lang, city, setCity } = useUiPrefs();
  const { loading, data, error, load } = useWarnings();

  // Fetch on mount (default city) and whenever the selected city or
  // language changes.
  useEffect(() => {
    void load(city, lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, lang]);

  return (
    <div className="flex flex-col w-full gap-space-lg pb-12">

<div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-lowest shadow-sm">
<div className="flex items-center gap-2 font-citation-mono text-citation-mono text-primary uppercase tracking-wider">
<span className="material-symbols-outlined text-[14px]">bolt</span>
<span>Live — data from /warnings</span>
<span className="flex-1 h-px bg-outline-variant/50" />
</div>

<label className="flex items-center gap-1.5 font-citation-mono text-citation-mono text-on-surface-variant">
<span className="material-symbols-outlined text-[14px]">location_on</span>
<span>CITY</span>
<select
  className="bg-surface-container-low text-on-surface rounded px-1.5 py-1 font-label-md text-label-md focus:outline-none"
  onChange={(e) => setCity(e.target.value)}
  value={city}
>
{CITIES.map((c) => (
  <option key={c.key} value={c.key}>{c.name}</option>
))}
</select>
</label>

{loading && (
<div className="flex items-center gap-2 p-space-md rounded-xl bg-surface-container-low font-body-md text-body-md text-on-surface-variant">
<span className="w-4 h-4 rounded-full border-2 border-outline-variant border-t-primary animate-spin" />
Checking current warnings…
</div>
)}

{error && (
<div className="flex flex-col gap-1 p-space-md rounded-xl bg-error-container text-on-error-container">
<div className="flex items-center gap-1.5 font-label-md text-label-md font-semibold">
<span className="material-symbols-outlined text-[18px]">wifi_off</span>
Warnings service unreachable
</div>
<p className="font-body-md text-body-md">{error.message}</p>
</div>
)}

{!loading && !error && data?.status === 'unavailable' && (
  /* Deliberately neutral, never green: no verdict is not an all-clear. */
<div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container">
<div className="flex flex-wrap items-center gap-1.5">
<span className="flex items-center gap-1 font-label-md text-label-md font-bold text-on-surface-variant">
<span className="material-symbols-outlined text-[18px]">help</span>
No warning verdict
</span>
<span className="px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-citation-mono text-[10px] font-medium">
<span className="material-symbols-outlined text-[11px] align-middle">location_on</span> {data.city_name}
</span>
</div>
<p className="font-body-md text-body-md text-on-surface">
Weather warnings aren't available right now for {data.city_name} — this can't be read as an all-clear.
</p>
<Legend rows={data.legend} />
</div>
)}

{!loading && !error && data && data.status !== 'unavailable' && <LiveVerdict data={data} />}
</div>

<div className="flex items-center gap-2 font-citation-mono text-citation-mono text-outline uppercase tracking-wider">
<span className="material-symbols-outlined text-[14px]">design_services</span>
<span>Static design sample — not live data</span>
<span className="flex-1 h-px bg-outline-variant/50" />
</div>

<div className="flex flex-col md:flex-row md:items-center justify-between gap-space-sm p-4 rounded-xl bg-surface-container-low shadow-sm">
<div className="flex items-center gap-3">
<span className="flex h-3 w-3 relative">
<span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-error opacity-75"></span>
<span className="relative inline-flex rounded-full h-3 w-3 bg-error"></span>
</span>
<div className="flex flex-col">
<div className="flex items-center gap-2">
<span className="font-headline-sm text-headline-sm text-on-surface">Warnings &amp; Advisories</span>
<span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-citation-mono text-citation-mono uppercase">Updated: 08:45 IST</span>
</div>
<span className="font-body-sm text-body-sm text-on-surface-variant">Konkan &amp; Mumbai Maritime Sector</span>
</div>
</div>
</div>

<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md">

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex flex-col justify-between opacity-70 transition-all hover:opacity-100">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="w-3.5 h-3.5 rounded-full bg-error"></span>
<span className="font-citation-mono text-citation-mono uppercase tracking-wider text-outline">Red</span>
</div>
<span className="font-citation-mono text-citation-mono font-bold px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">0 ACTIVE</span>
</div>
<div className="mt-space-md">
<h4 className="font-headline-sm text-headline-sm text-error">Take Action / खतरा</h4>
<p className="font-body-sm text-body-sm text-on-surface-variant mt-1">Extreme life threat. Flash flood and gale surges.</p>
</div>
<div className="mt-4 pt-2 flex items-center justify-between">
<span className="font-citation-mono text-citation-mono text-outline">Threshold &gt;204.4 mm</span>
<span className="material-symbols-outlined text-outline text-[18px]">verified</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-md flex flex-col justify-between relative overflow-hidden ring-2 ring-tertiary-container/30">
<div className="absolute top-0 left-0 right-0 h-1.5 bg-tertiary-container"></div>
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="w-3.5 h-3.5 rounded-full bg-tertiary-container animate-pulse"></span>
<span className="font-citation-mono text-citation-mono uppercase tracking-wider text-tertiary font-bold">Orange</span>
</div>
<span className="font-citation-mono text-citation-mono font-bold px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed">1 ACTIVE</span>
</div>
<div className="mt-space-md">
<h4 className="font-headline-sm text-headline-sm text-on-surface">Be Prepared / सतर्क</h4>
<p className="font-body-sm text-body-sm text-on-surface-variant mt-1 font-medium">Mumbai Metro &amp; Thane Suburban sectors under severe surge.</p>
</div>
<div className="mt-4 pt-2 flex items-center justify-between">
<span className="font-citation-mono text-citation-mono text-tertiary font-semibold">Rainfall: 115.6 - 204.4 mm</span>
<span className="material-symbols-outlined text-tertiary-container text-[18px]">warning</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex flex-col justify-between">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="w-3.5 h-3.5 rounded-full bg-secondary"></span>
<span className="font-citation-mono text-citation-mono uppercase tracking-wider text-outline">Yellow</span>
</div>
<span className="font-citation-mono text-citation-mono font-bold px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed">1 ACTIVE</span>
</div>
<div className="mt-space-md">
<h4 className="font-headline-sm text-headline-sm text-on-surface">Be Aware / निगरानी</h4>
<p className="font-body-sm text-body-sm text-on-surface-variant mt-1">Maharashtra Offshore waters; squally gale gusts active.</p>
</div>
<div className="mt-4 pt-2 flex items-center justify-between">
<span className="font-citation-mono text-citation-mono text-outline">Rainfall: 64.5 - 115.5 mm</span>
<span className="material-symbols-outlined text-outline text-[18px]">info</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex flex-col justify-between">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="w-3.5 h-3.5 rounded-full bg-primary-container"></span>
<span className="font-citation-mono text-citation-mono uppercase tracking-wider text-outline">Green</span>
</div>
<span className="font-citation-mono text-citation-mono font-bold px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">NORMAL</span>
</div>
<div className="mt-space-md">
<h4 className="font-headline-sm text-headline-sm text-on-surface">No Warning / सुरक्षित</h4>
<p className="font-body-sm text-body-sm text-on-surface-variant mt-1">Western Ghats &amp; Deccan interior corridors clear.</p>
</div>
<div className="mt-4 pt-2 flex items-center justify-between">
<span className="font-citation-mono text-citation-mono text-outline">Clear / Light Showers</span>
<span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
</div>
</div>
</div>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">

<div className="lg:col-span-8 flex flex-col gap-space-lg">

<div className="rounded-xl bg-surface-container-lowest shadow-md overflow-hidden flex flex-col">

<div className="px-space-lg py-3 bg-tertiary-container text-on-tertiary-container flex flex-wrap items-center justify-between gap-2">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-[20px]">thunderstorm</span>
<span className="font-label-md text-label-md font-semibold tracking-wide uppercase">Monsoon Surge Advisory</span>
</div>
<span className="font-citation-mono text-citation-mono px-2 py-0.5 rounded bg-tertiary text-on-tertiary font-bold">
            VALID: 18 OCT 12:00 – 20 OCT 08:30 IST
          </span>
</div>
<div className="p-space-lg flex flex-col gap-space-md">

<div className="flex flex-col gap-1">
<div className="flex flex-wrap items-center gap-2">
<span className="px-2.5 py-1 rounded bg-tertiary-fixed text-on-tertiary-fixed font-citation-mono text-citation-mono font-bold uppercase">
                Advisory Code: BOM-MET-2023-A4
              </span>
</div>
<h2 className="font-headline-lg text-headline-lg text-on-surface mt-1">
              Heavy to Very Heavy Rainfall in Mumbai &amp; Thane Suburban
            </h2>
<p className="font-body-md text-body-md text-on-surface-variant">
              Deep depression over east-central Arabian Sea is accelerating monsoonal westerlies onto the North Konkan shoreline.
            </p>
</div>

<div className="flex flex-col gap-2 pt-2">
<span className="font-label-md text-label-md font-semibold text-outline uppercase tracking-wider">Designated Critical Sectors</span>
<div className="flex flex-wrap gap-2">
<div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold">
<span className="material-symbols-outlined text-tertiary text-[18px]">location_on</span>
<span>Mumbai City (Colaba &amp; South)</span>
</div>
<div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold">
<span className="material-symbols-outlined text-tertiary text-[18px]">location_on</span>
<span>Mumbai Suburban (Bandra - Borivali)</span>
</div>
<div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold">
<span className="material-symbols-outlined text-tertiary text-[18px]">location_on</span>
<span>Thane &amp; Navi Mumbai</span>
</div>
<div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold">
<span className="material-symbols-outlined text-tertiary text-[18px]">location_on</span>
<span>Raigad / Alibaug Coast</span>
</div>
</div>
</div>

<div className="grid grid-cols-2 md:grid-cols-4 p-space-md gap-4 bg-surface-container rounded-xl">
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-on-surface-variant uppercase">Current Precipitation</span>
<span className="font-headline-sm text-headline-sm text-on-surface font-bold">68.2 mm/h</span>
<span className="font-body-sm text-body-sm text-error font-medium">Extreme Intensity</span>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-on-surface-variant uppercase">Gust Velocity</span>
<span className="font-headline-sm text-headline-sm text-on-surface font-bold">54 km/h</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Direction: WSW</span>
</div>
</div>
</div>

<div className="rounded-xl bg-surface-container p-4 flex flex-col gap-2">
<button className="flex items-center justify-between w-full text-left font-label-md text-label-md font-semibold text-on-surface" onClick={() => setShowGeofence((v) => !v)} type="button">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-primary text-[18px]">verified_user</span>
<span>Why am I receiving this alert?</span>
</div>
<span className={`material-symbols-outlined text-on-surface-variant text-[20px] transition-transform ${showGeofence ? 'rotate-180' : ''}`}>expand_more</span>
</button>
<div className={`${showGeofence ? 'flex' : 'hidden'} flex-col gap-2 pt-2 text-on-surface-variant font-body-sm text-body-sm border-t border-surface-container-high mt-1`}>
<p>
                Your connected GPS coordinates <span className="font-citation-mono font-semibold text-on-surface">[18.9067° N, 72.8147° E]</span> fall inside the advisory area for code <span className="font-citation-mono font-semibold text-on-surface">BOM-MET-2023-A4</span>, sourced from the CAP/SACHET (National Disaster Management Authority) alert feed.
              </p>
</div>
</div>

<div className="flex flex-wrap items-center justify-between gap-space-sm pt-2">
<div className="flex items-center gap-2">
<button className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-surface-container-high hover:bg-surface-variant text-on-surface font-label-md text-label-md font-semibold transition" id="shareBulletinBtn" type="button">
<span className="material-symbols-outlined text-[18px]">share</span>
<span>Share Warning Bulletin</span>
</button>
</div>
</div>
</div>
</div>
</div>

<div className="lg:col-span-4 flex flex-col gap-space-lg">

<div className="p-space-lg rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-md">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-error text-[22px]">contact_phone</span>
<h3 className="font-headline-sm text-headline-sm text-on-surface">Emergency Hotlines</h3>
</div>
</div>

<div className="flex flex-col gap-2.5">

<a className="p-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition-all flex items-center justify-between group" href="tel:1916">
<div className="flex items-center gap-3">
<div className="w-10 h-10 rounded-lg bg-surface-container-high group-hover:bg-primary group-hover:text-on-primary transition flex items-center justify-center text-primary">
<span className="material-symbols-outlined text-[20px]">corporate_fare</span>
</div>
<div className="flex flex-col">
<span className="font-label-md text-label-md font-semibold text-on-surface">BMC Disaster Desk</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Mumbai Floods &amp; Fallen Trees</span>
</div>
</div>
<span className="font-headline-sm text-headline-sm text-primary font-bold">1916</span>
</a>

<a className="p-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition-all flex items-center justify-between group" href="tel:1078">
<div className="flex items-center gap-3">
<div className="w-10 h-10 rounded-lg bg-surface-container-high group-hover:bg-error group-hover:text-on-error transition flex items-center justify-center text-error">
<span className="material-symbols-outlined text-[20px]">medical_services</span>
</div>
<div className="flex flex-col">
<span className="font-label-md text-label-md font-semibold text-on-surface">NDRF HQ Helpline</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">National Disaster Relief</span>
</div>
</div>
<span className="font-headline-sm text-headline-sm text-error font-bold">1078</span>
</a>

<a className="p-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition-all flex items-center justify-between group" href="tel:18001801717">
<div className="flex items-center gap-3">
<div className="w-10 h-10 rounded-lg bg-surface-container-high group-hover:bg-secondary group-hover:text-on-secondary transition flex items-center justify-center text-secondary">
<span className="material-symbols-outlined text-[20px]">cyclone</span>
</div>
<div className="flex flex-col">
<span className="font-label-md text-label-md font-semibold text-on-surface">IMD Cyclone Desk</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">MoES National Helpline</span>
</div>
</div>
<span className="font-label-md text-label-md text-on-surface font-bold text-right leading-tight">1800-180<br/>1717</span>
</a>
</div>
</div>

<div className="p-space-lg rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-md">
<h4 className="font-headline-sm text-headline-sm text-on-surface">Adjacent Sectors Status</h4>
<div className="flex flex-col gap-3">
<div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-low">
<div className="flex items-center gap-2.5">
<span className="w-2.5 h-2.5 rounded-full bg-primary-container"></span>
<div className="flex flex-col">
<span className="font-label-md text-label-md font-semibold text-on-surface">Pune &amp; Western Ghats</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Lonavala / Khandala Ghat</span>
</div>
</div>
<span className="font-citation-mono text-citation-mono px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-bold">GREEN</span>
</div>
<div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-low">
<div className="flex items-center gap-2.5">
<span className="w-2.5 h-2.5 rounded-full bg-secondary"></span>
<div className="flex flex-col">
<span className="font-label-md text-label-md font-semibold text-on-surface">South Konkan (Ratnagiri)</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Wind 30–40 km/h</span>
</div>
</div>
<span className="font-citation-mono text-citation-mono px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed font-bold">YELLOW</span>
</div>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-2">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-primary text-[18px]">verified</span>
<span className="font-label-md text-label-md font-semibold text-on-surface">Source</span>
</div>
<p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">
          Warnings are sourced from the CAP/SACHET alert feed (National Disaster Management Authority), rendered with the official category text.
        </p>
</div>
</div>
</div>

  );
}
