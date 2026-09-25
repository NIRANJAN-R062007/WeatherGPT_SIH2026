import { useState } from 'react';

export default function ChatPage() {
  const [showEvidence, setShowEvidence] = useState(false);
  return (
    <div className="flex flex-col w-full gap-space-lg">

<div className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-space-sm" title="Session #W-BOM-8831 · Station 43003 · 18.9067° N, 72.8147° E">
<div className="flex flex-wrap items-center gap-space-sm">
<span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-primary-fixed text-on-primary-fixed font-citation-mono text-citation-mono font-medium">
<span className="w-2 h-2 rounded-full bg-primary animate-ping"></span>
        Doppler Radar Active
      </span>
<span className="inline-flex items-center gap-1 text-secondary font-label-md text-label-md">
<span className="material-symbols-outlined text-[16px]">verified</span>
<span>99.8% Ground Truth Grounding</span>
</span>
</div>
<span className="font-citation-mono text-citation-mono text-on-surface-variant">Colaba, Mumbai</span>
</div>

<div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">

<div className="xl:col-span-8 flex flex-col gap-space-md min-w-0">

<div className="flex flex-col gap-space-lg">

<div className="flex justify-end pl-12">
<div className="bg-primary text-on-primary p-space-md rounded-2xl rounded-br-none shadow-md max-w-2xl flex flex-col gap-1.5">
<div className="flex items-center justify-between gap-4 font-citation-mono text-citation-mono text-primary-fixed">
<span className="flex items-center gap-1">
<span className="material-symbols-outlined text-[14px]">account_circle</span>
                Rohit Sharma • Citizen Query
              </span>
<span>08:34 IST</span>
</div>
<p className="font-body-lg text-body-lg text-on-primary font-medium">
              Will it rain in Colaba, Mumbai this evening? Need to plan an outdoor event.
            </p>
</div>
</div>

<div className="flex flex-col gap-space-sm pr-2">

<div className="bg-surface-container-lowest rounded-2xl rounded-bl-none p-space-lg shadow-sm flex flex-col gap-space-md">

<div className="flex flex-wrap items-center justify-between gap-space-sm pb-space-sm bg-surface-bright p-space-sm rounded-xl">
<div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-secondary-container text-on-secondary-container font-label-md text-label-md font-semibold" title="Verified against MoES & IMD Open Gateway · Live fetch">
<span className="material-symbols-outlined text-[16px]">verified_user</span>
<span>Verified &amp; Live</span>
</div>
<span className="px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-md text-label-md font-semibold flex items-center gap-1">
<span className="material-symbols-outlined text-[15px]">warning</span>
                  IMD Code Orange
                </span>
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
<span className="font-medium text-on-surface">Hourly Rain Distribution (Colaba Ward A)</span>
<span className="font-citation-mono text-citation-mono text-primary">Model: GFS 0.25° + WRF-Mumbai</span>
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

<div className="bg-tertiary-fixed text-on-tertiary-fixed p-space-md rounded-xl flex items-start gap-space-sm shadow-sm">
<span className="material-symbols-outlined text-tertiary text-[24px] mt-0.5">report_problem</span>
<div className="flex flex-col gap-0.5">
<span className="font-headline-sm text-[16px] leading-tight font-bold text-on-tertiary-fixed">
                  Public Safety Advisory • Ward A (Colaba / Nariman Point)
                </span>
<p className="font-body-md text-body-md text-on-tertiary-fixed-variant leading-normal">
                  Implement waterproof rain contingencies or shift sensitive electrical audio/lighting equipment indoors by <strong>16:30 IST</strong>. High tide swell is concurrent at 19:12 IST (3.92m), aggravating drainage run-off near Marine Drive promenade.
                </p>
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
<span>{showEvidence ? 'Hide Raw JSON Evidence' : 'View Raw JSON Evidence'}</span>
</button>
</div>

<div className="text-right">
<span className="font-citation-mono text-citation-mono text-outline">
                  Source: Google Weather API (GFS 0.25°) &amp; IMD Colaba [43003]
                </span>
</div>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-low flex items-center justify-between gap-space-sm shadow-sm">
<div className="flex items-center gap-space-sm">
<div className="relative flex items-center justify-center w-6 h-6">
<span className="w-full h-full rounded-full bg-secondary-fixed opacity-75 animate-ping absolute"></span>
<span className="w-2.5 h-2.5 rounded-full bg-secondary"></span>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono font-medium text-on-surface">
                  TELEMETRY STREAM IN-FLIGHT: Querying Google Weather API &amp; Colaba geofence polygon (43003_COLABA)
                </span>
<span className="font-citation-mono text-[10px] text-outline">LATENCY: 42ms • RADAR DBZ REFRESH: 120s</span>
</div>
</div>
<span className="font-citation-mono text-citation-mono px-2 py-0.5 rounded bg-surface-container-lowest text-secondary font-semibold">SYNCED</span>
</div>
</div>
</div>

<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm mt-space-xs">

<div className="flex items-center gap-2 overflow-x-auto pb-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider shrink-0">Suggested:</span>
<button className="shrink-0 px-3 py-1 rounded-full bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center gap-1.5" type="button">
<span>🌧️ Will it rain tomorrow in Colaba?</span>
</button>
<button className="shrink-0 px-3 py-1 rounded-full bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center gap-1.5" type="button">
<span>📅 5-day South Mumbai forecast</span>
</button>
<button className="shrink-0 px-3 py-1 rounded-full bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center gap-1.5" type="button">
<span>🌊 High tide timing Marine Drive</span>
</button>
</div>

<div className="flex items-center gap-space-sm bg-surface-container-low p-2 rounded-xl">
<button className="p-2 rounded-lg bg-surface-container-lowest hover:bg-surface-container text-on-surface-variant hover:text-primary transition-colors flex items-center justify-center shadow-sm" title="Multilingual Voice Input" type="button">
<span className="material-symbols-outlined text-[20px]">mic</span>
</button>
<input className="flex-1 bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface placeholder:text-outline px-2" placeholder="Ask WeatherGPT in English, हिंदी, मराठी, தமிழ்... (e.g. 'Can I host an outdoor dinner at 7 PM?')" type="text" value="What are the wind speeds at Marine Drive between 18:00 and 20:00?"/>
<div className="flex items-center gap-1.5 shrink-0">
<span className="px-2 py-0.5 rounded text-xs font-citation-mono bg-surface-container-highest text-on-surface-variant font-medium">
              IN-EN / HI
            </span>
<button className="p-2.5 rounded-lg bg-primary hover:bg-primary-container text-on-primary transition-colors flex items-center justify-center shadow-md" type="button">
<span className="material-symbols-outlined text-[20px]">send</span>
</button>
</div>
</div>

<div className="flex items-center justify-between text-on-surface-variant px-1">
<div className="flex items-center gap-1.5 font-citation-mono text-citation-mono">
<span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>
<span>Cross-referenced against IMD radar bulletins every 10 minutes</span>
</div>
<span className="font-citation-mono text-citation-mono text-outline">Open Civic Framework • Zero Hallucination Mode</span>
</div>
</div>
</div>

<div className="xl:col-span-4 flex flex-col gap-space-md min-w-0">

{showEvidence && (
<>
<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-primary text-[22px]">data_object</span>
<span className="font-headline-sm text-[16px] text-on-surface font-bold uppercase tracking-tight">Telemetry Inspector</span>
</div>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface-variant">API v1.4</span>
</div>
<div className="flex items-center justify-between p-2 rounded-lg bg-surface-container-low font-citation-mono text-citation-mono text-outline">
<span>SHA-256 HASH</span>
<span className="text-on-surface-variant font-bold">7f3a9e088...c4b2a</span>
</div>
</div>

<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface font-semibold flex items-center gap-1">
<span className="material-symbols-outlined text-secondary text-[16px]">account_tree</span>
            Verified Observation Pipeline
          </span>
<span className="font-citation-mono text-citation-mono text-secondary">METAR VALID</span>
</div>

<div className="flex flex-col gap-2 font-citation-mono text-citation-mono">

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Rain Prob (18:00 IST)</span>
<span className="text-primary font-bold text-body-md">82%</span>
</div>
<div className="text-[10px] text-outline truncate">
              ↳ data.timelines.hourly[18:00].precipProbability
            </div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              Google Weather Global High-Res Forecast
            </div>
</div>

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Peak Precipitation Rate</span>
<span className="text-on-surface font-bold text-body-md">12.4 mm/h</span>
</div>
<div className="text-[10px] text-outline truncate">
              ↳ stations['43003_COLABA'].metar.rainRate
            </div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              IMD Colaba Automatic Weather Station (AWS)
            </div>
</div>

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Wind Gust Vector</span>
<span className="text-on-surface font-bold text-body-md">38 km/h SW (225°)</span>
</div>
<div className="text-[10px] text-outline truncate">
              ↳ forecast.hourly[18:00].windGust
            </div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              MoES NCMRWF Unified Model Data
            </div>
</div>

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Hazard Warning Tier</span>
<span className="text-tertiary font-bold text-body-md">Code Orange (#EA580C)</span>
</div>
<div className="text-[10px] text-outline truncate">
              ↳ imd.bulletins.coastal_alert_level
            </div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              IMD Mumbai Regional Met Centre (RMC)
            </div>
</div>

<div className="p-2.5 rounded-xl bg-surface-container-low flex flex-col gap-1">
<div className="flex items-center justify-between">
<span className="text-on-surface-variant">Barometric Trend</span>
<span className="text-on-surface font-bold text-body-md">1008.2 hPa (↓ 1.4/3h)</span>
</div>
<div className="text-[10px] text-outline truncate">
              ↳ surface.barometer.qnh_tendency
            </div>
<div className="flex items-center gap-1 text-[10px] text-secondary">
<span className="material-symbols-outlined text-[12px]">check_circle</span>
              Synoptic Station Barometric Sensor
            </div>
</div>
</div>
</div>
</>
)}

<div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-sm overflow-hidden">
<div className="flex items-center justify-between">
<div className="flex items-center gap-1.5">
<span className="material-symbols-outlined text-primary text-[18px]">radar</span>
<span className="font-label-md text-label-md text-on-surface font-semibold">Doppler Radar Reflectivity</span>
</div>
<span className="font-citation-mono text-citation-mono text-on-surface-variant">MAX: 44 dBZ</span>
</div>

<div className="relative w-full h-44 rounded-xl overflow-hidden shadow-inner">
<img className="w-full h-full object-cover" data-alt="Wide-angle view of Mumbai Marine Drive promenade during an ominous monsoon storm approaching sunset. Dramatic dark storm clouds fill the sky with warm golden light breaking through the horizon. Rain-slicked wet black asphalt with yellow-topped vintage Premier Padmini taxis driving along the curving coastal road. Giant waves crash against concrete tetrapods spraying white seafoam into the air. Coastal colonial buildings line the boulevard under dramatic atmospheric weather." src="/images/hero-alerts-storm.jpg"/>

<div className="absolute inset-0 bg-gradient-to-t from-inverse-surface/80 via-transparent to-transparent flex flex-col justify-between p-space-sm">
<div className="flex items-center justify-between">
<span className="px-2 py-0.5 rounded bg-surface-container-lowest/90 backdrop-blur text-primary font-citation-mono text-citation-mono font-bold">
                RADAR: COLABA 300KM
              </span>
<span className="w-3 h-3 rounded-full bg-error animate-ping"></span>
</div>
<div className="flex items-end justify-between text-inverse-on-surface">
<div>
<div className="font-headline-sm text-sm font-bold">Mumbai Harbor &amp; Marine Drive</div>
<div className="font-citation-mono text-[10px] text-surface-container">CELL DELTA: Moving ENE at 22 km/h</div>
</div>
<span className="material-symbols-outlined text-[20px] text-secondary-container">navigation</span>
</div>
</div>
</div>
<div className="flex items-center justify-between pt-1 font-citation-mono text-citation-mono text-on-surface-variant">
<span>SWEEP FREQUENCY: 5.6 GHz</span>
<span className="text-primary font-medium">LIVE TILT 0.5°</span>
</div>
</div>

<div className="bg-secondary-container text-on-secondary-container rounded-2xl p-space-md shadow-sm flex flex-col gap-2">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-secondary text-[22px]">shield_lock</span>
<span className="font-headline-sm text-[15px] font-bold text-on-secondary-container">
            Zero-Hallucination Architecture
          </span>
</div>
<p className="font-body-sm text-body-sm leading-relaxed text-on-secondary-fixed-variant">
          WeatherGPT relies strictly on deterministic retrieval: every prompt assertion is matched directly against live IMD Doppler and Google Weather API JSON values before text synthesis occurs.
        </p>
<div className="pt-1 flex items-center justify-between font-citation-mono text-citation-mono text-on-secondary-container">
<span>PUBLIC PIPELINE: NO KEY REQUIRED</span>
<span className="font-bold underline cursor-pointer">AUDIT LOGS</span>
</div>
</div>
</div>
</div>
</div>

  );
}
