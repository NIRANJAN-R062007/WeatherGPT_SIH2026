export default function HomePage() {
  return (
    <div className="flex flex-col w-full gap-space-lg">

<section className="relative isolate w-full rounded-2xl overflow-hidden shadow-xl text-on-primary min-h-[380px] flex flex-col justify-between p-space-lg lg:p-space-xl">

<div className="absolute inset-0 bg-cover bg-center -z-20 transform scale-105 transition-transform duration-1000" data-alt="Dramatic monsoon sky over Mumbai's Marine Drive crescent bay, stormy deep slate rain clouds contrasting with golden sunset break, high churning sea spray crashing against tetrapods, slick wet coastal highway reflecting twilight city lights and taxi headlights, hyper-realistic, atmospheric photography." style={{ backgroundImage: "url('/images/hero-mumbai-marine-drive-1.jpg')" }}></div>
<div className="absolute inset-0 bg-gradient-to-r from-on-background/95 via-on-background/80 to-primary/40 -z-10 backdrop-blur-[2px]"></div>
<div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-secondary-container/20 blur-3xl pointer-events-none -z-10"></div>

<div className="flex flex-wrap items-center justify-between gap-space-md">
<div className="flex flex-col gap-1">
<div className="flex items-center gap-2">
<span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-lowest/15 backdrop-blur-md font-citation-mono text-citation-mono text-on-primary font-medium tracking-wide" title="Station: Colaba IMD AWS [43003] · 18.9067° N, 72.8147° E · MSL: 11m">
<span className="w-2 h-2 rounded-full bg-secondary-fixed animate-ping"></span>
            MONSOON COASTAL FRONT ACTIVE • Beaufort 5
          </span>
</div>
<h1 className="font-headline-lg text-headline-lg font-bold tracking-tight text-on-primary mt-1">
          Good morning, Rohit! 🇮🇳
        </h1>
<p className="font-citation-mono text-citation-mono text-surface-container-high/85 flex items-center gap-1.5">
<span className="material-symbols-outlined text-[14px] text-secondary-fixed">my_location</span>
          Mumbai, Maharashtra • Updated 08:30 IST
        </p>
</div>

<div className="flex items-center gap-2">
<div className="px-3 py-2 rounded-xl bg-surface-container-lowest/10 backdrop-blur-md flex items-center gap-2 text-right">
<span className="material-symbols-outlined text-secondary-fixed text-[24px]">air</span>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-surface-container-high">INCOIS BUOY</span>
<span className="font-label-md text-label-md font-semibold text-on-primary">Swell: 2.8m SSW</span>
</div>
</div>
</div>
</div>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-end mt-space-md">

<div className="lg:col-span-6 flex flex-col sm:flex-row items-start sm:items-center gap-space-lg">
<div className="flex items-baseline gap-2">
<span className="font-metric-display text-metric-display text-surface-container-lowest font-extrabold leading-none tracking-tighter drop-shadow-md">
            29°
          </span>
<span className="font-headline-sm text-headline-sm text-surface-container-high/80">C</span>
</div>
<div className="flex flex-col">
<div className="flex items-center gap-2 text-secondary-fixed font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[26px]">cyclone</span>
            Partly Cloudy with Coastal Swell Breeze
          </div>
<div className="flex items-center gap-3 mt-1 font-body-md text-body-md text-surface-container-high/90">
<span>Feels like <strong className="font-semibold text-surface-container-lowest">33°C</strong></span>
<span>•</span>
<span className="inline-flex items-center gap-1 text-tertiary-fixed font-medium">
<span className="w-2 h-2 rounded-full bg-tertiary-fixed"></span>
              AQI 112 (Moderate - PM2.5)
            </span>
</div>
</div>
</div>

<div className="lg:col-span-6 flex flex-col justify-end bg-surface-container-lowest/10 backdrop-blur-md p-space-md rounded-xl">
<div className="flex items-center justify-between text-surface-container-high font-citation-mono text-citation-mono mb-1">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-tertiary-fixed">wb_sunny</span> Sunrise 06:32 IST</span>
<span className="text-secondary-fixed font-semibold">Solar Noon 12:24</span>
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-tertiary-fixed-dim">bedtime</span> Sunset 18:14 IST</span>
</div>

<div className="relative w-full h-12 flex items-center">
<svg className="w-full h-12 overflow-visible" fill="none" viewBox="0 0 300 48">
<path className="text-surface-container-highest/40" d="M 10 40 Q 150 -10 290 40" stroke="currentColor" strokeDasharray="3 3" strokeWidth="2"></path>
<path className="text-tertiary-fixed" d="M 10 40 Q 80 12 110 18" stroke="currentColor" strokeLinecap="round" strokeWidth="3"></path>
<circle className="fill-tertiary-fixed shadow-md shadow-tertiary-fixed" cx="110" cy="18" r="6"></circle>
<circle className="stroke-tertiary-fixed/40 animate-ping" cx="110" cy="18" r="11" strokeWidth="1.5"></circle>
</svg>
</div>
<div className="flex items-center justify-between font-citation-mono text-citation-mono text-surface-container-high mt-1">
<span>Daylight elapsed: 2h 18m</span>
<span className="px-2 py-0.5 rounded bg-surface-container-lowest/20 text-on-primary font-semibold">UV Index: 4.8 (Moderate)</span>
</div>
</div>
</div>

<div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-2 mt-space-md pt-space-md bg-surface-container-lowest/10 backdrop-blur-md rounded-xl p-3">
<div className="flex flex-col" title="Dew Pt: 24.2°C">
<span className="font-citation-mono text-citation-mono text-surface-container-high">HUMIDITY</span>
<div className="flex items-center gap-1 text-on-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-secondary-fixed">humidity_high</span>
          78%
        </div>
</div>
<div className="flex flex-col" title="Heading: 220° SSW">
<span className="font-citation-mono text-citation-mono text-surface-container-high">WIND (SURFACE)</span>
<div className="flex items-center gap-1 text-on-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-secondary-fixed">north_east</span>
          14 km/h
        </div>
</div>
<div className="flex flex-col" title="Swell band 12km off">
<span className="font-citation-mono text-citation-mono text-surface-container-high">PRECIPITATION</span>
<div className="flex items-center gap-1 text-on-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-secondary-fixed">rainy</span>
          35%
        </div>
</div>
<div className="flex flex-col" title="Pressure Falling -0.8">
<span className="font-citation-mono text-citation-mono text-surface-container-high">BAROMETER</span>
<div className="flex items-center gap-1 text-on-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-tertiary-fixed">trending_down</span>
          1008 hPa
        </div>
</div>
<div className="flex flex-col" title="82% Cloud Cover">
<span className="font-citation-mono text-citation-mono text-surface-container-high">VISIBILITY</span>
<div className="flex items-center gap-1 text-on-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-secondary-fixed">visibility</span>
          8.0 km
        </div>
</div>
<div className="flex flex-col" title="High Tide: 13:42 IST">
<span className="font-citation-mono text-citation-mono text-surface-container-high">TIDE CYCLES</span>
<div className="flex items-center gap-1 text-on-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-secondary-fixed">waves</span>
          4.12 m
        </div>
</div>
</div>
</section>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">

<div className="lg:col-span-8 flex flex-col gap-space-lg">

<section className="rounded-xl bg-tertiary-fixed/30 p-space-md flex flex-col sm:flex-row gap-space-md items-start justify-between shadow-sm relative overflow-hidden">
<div className="absolute left-0 top-0 bottom-0 w-2 bg-tertiary"></div>
<div className="flex items-start gap-space-md pl-1">
<div className="w-10 h-10 rounded-xl bg-tertiary text-on-tertiary flex items-center justify-center shrink-0 shadow-sm">
<span className="material-symbols-outlined text-[24px]">warning</span>
</div>
<div className="flex flex-col gap-0.5">
<div className="flex items-center gap-2 flex-wrap">
<span className="px-2 py-0.5 rounded font-citation-mono text-citation-mono bg-tertiary-container text-on-tertiary-container font-bold uppercase tracking-wider">
                IMD Code 2 : Yellow Advisory
              </span>
<span className="font-citation-mono text-citation-mono text-on-tertiary-fixed-variant">
                Valid: 08:30 - 20:30 IST Today
              </span>
</div>
<h2 className="font-headline-sm text-headline-sm text-on-surface font-bold mt-1">
              Squally Weather Warning for North Maharashtra &amp; Mumbai Coast
            </h2>
<p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
              Fishermen advised not to venture along &amp; off North Maharashtra coast. Sea condition rough to very rough with swell waves up to <strong>3.2 meters</strong>. Gale gusts reaching <strong>45-55 kmph</strong>. High-energy swell surge expected along Marine Drive and Bandra sea-front during high tide.
            </p>
<div className="flex items-center gap-3 mt-2">
<span className="font-citation-mono text-citation-mono text-on-surface-variant flex items-center gap-1">
<span className="material-symbols-outlined text-[14px] text-tertiary">verified_user</span>
                Regional Meteorological Centre, Mumbai
              </span>
<a className="font-label-md text-label-md text-primary font-semibold hover:underline inline-flex items-center gap-1" href="#">
                Read Official PDF Bulletin <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
</a>
</div>
</div>
</div>
</section>

<section className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md relative">
<div className="flex flex-wrap items-center justify-between gap-space-sm">
<div className="flex items-center gap-space-sm">
<div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
<span className="material-symbols-outlined text-[20px]">radar</span>
</div>
<div>
<h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">
                Live Doppler S-Band Radar Sync
              </h3>
<p className="font-citation-mono text-citation-mono text-on-surface-variant">
                Composite Max Reflectivity (dBZ) • Veravali &amp; Colaba 250km PPI
              </p>
</div>
</div>
<div className="flex items-center gap-2">
<span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-secondary/10 text-secondary font-citation-mono text-citation-mono font-medium">
<span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
              SWEEP 08:24 IST
            </span>
<div className="flex items-center rounded-lg bg-surface-container-low p-1 gap-1">
<button className="px-2.5 py-1 rounded-md bg-surface-container-lowest font-label-md text-label-md font-semibold text-primary shadow-xs">Composite</button>
<button className="px-2.5 py-1 rounded-md font-label-md text-label-md text-on-surface-variant hover:text-on-surface">Radial Velocity</button>
<button className="px-2.5 py-1 rounded-md font-label-md text-label-md text-on-surface-variant hover:text-on-surface">VIL</button>
</div>
</div>
</div>

<div className="relative w-full h-[320px] rounded-xl overflow-hidden bg-on-background flex items-center justify-center">

<div className="absolute inset-0 bg-cover bg-center opacity-40 mix-blend-luminosity" data-location="Mumbai, Maharashtra, India" style={{ backgroundImage: "url('/images/hero-mumbai-marine-drive-2.jpg')" }}></div>

<svg className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="xMidYMid slice" viewBox="0 0 800 320">

<circle cx="400" cy="160" fill="none" r="60" stroke="#7af5f5" strokeDasharray="2 3" strokeOpacity="0.3" strokeWidth="1"></circle>
<circle cx="400" cy="160" fill="none" r="120" stroke="#7af5f5" strokeOpacity="0.25" strokeWidth="1"></circle>
<circle cx="400" cy="160" fill="none" r="180" stroke="#7af5f5" strokeDasharray="3 4" strokeOpacity="0.2" strokeWidth="1"></circle>
<circle cx="400" cy="160" fill="none" r="240" stroke="#7af5f5" strokeOpacity="0.15" strokeWidth="1"></circle>

<line stroke="#7af5f5" strokeOpacity="0.2" strokeWidth="1" x1="160" x2="640" y1="160" y2="160"></line>
<line stroke="#7af5f5" strokeOpacity="0.2" strokeWidth="1" x1="400" x2="400" y1="0" y2="320"></line>
<line stroke="#7af5f5" strokeOpacity="0.1" strokeWidth="1" x1="230" x2="570" y1="0" y2="320"></line>
<line stroke="#7af5f5" strokeOpacity="0.1" strokeWidth="1" x1="570" x2="230" y1="0" y2="320"></line>

<g transform="translate(400, 160)">
<line opacity="0.8" stroke="#5bd9d8" strokeWidth="2" x1="0" x2="250" y1="0" y2="-120">
<animateTransform attributeName="transform" dur="6s" from="0" repeatCount="indefinite" to="360" type="rotate"></animateTransform>
</line>
</g>


<ellipse cx="310" cy="120" fill="#006a6a" filter="blur(6px)" opacity="0.5" rx="35" ry="24"></ellipse>
<circle cx="305" cy="115" fill="#ffba46" filter="blur(4px)" opacity="0.65" r="18"></circle>
<circle cx="302" cy="113" fill="#ba1a1a" filter="blur(2px)" opacity="0.8" r="8"></circle>

<ellipse cx="370" cy="80" fill="#007070" filter="blur(5px)" opacity="0.6" rx="28" ry="16"></ellipse>
<circle cx="368" cy="78" fill="#9d6a00" filter="blur(3px)" opacity="0.7" r="10"></circle>

<ellipse cx="440" cy="220" fill="#006a6a" filter="blur(5px)" opacity="0.45" rx="42" ry="20"></ellipse>
<circle cx="445" cy="222" fill="#7af5f5" filter="blur(3px)" opacity="0.6" r="14"></circle>
</svg>

<div className="absolute top-3 left-3 flex flex-col gap-1 bg-on-background/70 backdrop-blur-md p-2 rounded-lg font-citation-mono text-citation-mono text-surface-container-high pointer-events-none">
<span className="text-secondary-fixed font-bold">COLABA S-BAND [DWR]</span>
<span>Range: 250 km PPI • Elevation: 0.5°</span>
<span>Offshore Squall Echo: 42 dBZ at 14 NM SW</span>
</div>
<div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 bg-on-background/75 backdrop-blur-md p-2 rounded-lg">
<div className="flex items-center gap-2">
<span className="font-citation-mono text-citation-mono text-surface-container-high">REFLECTIVITY (dBZ):</span>
<div className="flex items-center gap-0.5">
<span className="w-4 h-2.5 rounded-xs bg-[#5bd9d8]" title="15 dBZ"></span>
<span className="w-4 h-2.5 rounded-xs bg-[#007070]" title="25 dBZ"></span>
<span className="w-4 h-2.5 rounded-xs bg-[#ffba46]" title="35 dBZ"></span>
<span className="w-4 h-2.5 rounded-xs bg-[#9d6a00]" title="45 dBZ"></span>
<span className="w-4 h-2.5 rounded-xs bg-[#ba1a1a]" title="55 dBZ"></span>
<span className="w-4 h-2.5 rounded-xs bg-[#93000a]" title="65 dBZ"></span>
</div>
<span className="font-citation-mono text-[10px] text-surface-container-high/70">15 (Light) → 65 (Severe Squall)</span>
</div>
<div className="flex items-center gap-1.5 font-citation-mono text-citation-mono text-on-primary">
<button className="px-2 py-0.5 rounded bg-surface-container-lowest/20 hover:bg-surface-container-lowest/30 transition-colors flex items-center gap-1">
<span className="material-symbols-outlined text-[14px]">play_arrow</span> Loop 2hr
              </button>
<button className="px-2 py-0.5 rounded bg-surface-container-lowest/20 hover:bg-surface-container-lowest/30 transition-colors flex items-center gap-1">
<span className="material-symbols-outlined text-[14px]">fullscreen</span> Expand
              </button>
</div>
</div>
</div>
</section>

<section className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md">
<div className="flex items-center justify-between">
<div className="flex items-center gap-space-sm">
<div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
<span className="material-symbols-outlined text-[20px]">calendar_view_week</span>
</div>
<div>
<h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">
                5-Day Synoptic Outlook
              </h3>
<p className="font-citation-mono text-citation-mono text-on-surface-variant">
                IMD Numerical Weather Prediction (WRF-9km &amp; ECMWF Ensemble)
              </p>
</div>
</div>
<span className="font-citation-mono text-citation-mono text-primary font-semibold cursor-pointer hover:underline">
            View 15-Day Extended
          </span>
</div>

<div className="grid grid-cols-2 sm:grid-cols-5 gap-3">

<div className="p-3 rounded-xl bg-surface-container-low flex flex-col justify-between hover:bg-surface-container transition-colors">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md font-bold text-on-surface">TODAY</span>
<span className="w-2 h-2 rounded-full bg-secondary"></span>
</div>
<div className="my-2 flex flex-col items-center">
<span className="material-symbols-outlined text-[32px] text-primary">partly_cloudy_day</span>
<span className="font-citation-mono text-[10px] text-on-surface-variant mt-0.5 text-center">Partly Cloudy</span>
</div>
<div className="flex items-center justify-between text-center pt-2">
<span className="font-headline-sm text-headline-sm text-on-surface font-bold">31°</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">26°</span>
</div>
<div className="mt-1 flex items-center justify-center gap-1 font-citation-mono text-citation-mono text-secondary font-medium">
<span className="material-symbols-outlined text-[13px]">water_drop</span> 35%
            </div>
</div>

<div className="p-3 rounded-xl bg-surface-container-low flex flex-col justify-between hover:bg-surface-container transition-colors">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md font-bold text-on-surface">THU 12</span>
<span className="w-2.5 h-2.5 rounded-full bg-tertiary-fixed-dim" title="Yellow Warning: Heavy Thunderstorms"></span>
</div>
<div className="my-2 flex flex-col items-center">
<span className="material-symbols-outlined text-[32px] text-tertiary">thunderstorm</span>
<span className="font-citation-mono text-[10px] text-on-surface-variant mt-0.5 text-center">Thunderstorms</span>
</div>
<div className="flex items-center justify-between text-center pt-2">
<span className="font-headline-sm text-headline-sm text-on-surface font-bold">30°</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">25°</span>
</div>
<div className="mt-1 flex items-center justify-center gap-1 font-citation-mono text-citation-mono text-primary font-medium">
<span className="material-symbols-outlined text-[13px]">water_drop</span> 75%
            </div>
</div>

<div className="p-3 rounded-xl bg-error-container/40 flex flex-col justify-between shadow-xs">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md font-bold text-error">FRI 13</span>
<span className="w-2.5 h-2.5 rounded-full bg-error animate-ping" title="Red Alert: Monsoon Surge"></span>
</div>
<div className="my-2 flex flex-col items-center">
<span className="material-symbols-outlined text-[32px] text-error">flood</span>
<span className="font-citation-mono text-[10px] text-error font-semibold mt-0.5 text-center">Heavy Surge</span>
</div>
<div className="flex items-center justify-between text-center pt-2">
<span className="font-headline-sm text-headline-sm text-error font-bold">28°</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">24°</span>
</div>
<div className="mt-1 flex items-center justify-center gap-1 font-citation-mono text-citation-mono text-error font-bold">
<span className="material-symbols-outlined text-[13px]">rainy</span> 98%
            </div>
</div>

<div className="p-3 rounded-xl bg-surface-container-low flex flex-col justify-between hover:bg-surface-container transition-colors">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md font-bold text-on-surface">SAT 14</span>
<span className="w-2.5 h-2.5 rounded-full bg-tertiary-fixed-dim"></span>
</div>
<div className="my-2 flex flex-col items-center">
<span className="material-symbols-outlined text-[32px] text-primary">rainy_heavy</span>
<span className="font-citation-mono text-[10px] text-on-surface-variant mt-0.5 text-center">Moderate Rain</span>
</div>
<div className="flex items-center justify-between text-center pt-2">
<span className="font-headline-sm text-headline-sm text-on-surface font-bold">29°</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">25°</span>
</div>
<div className="mt-1 flex items-center justify-center gap-1 font-citation-mono text-citation-mono text-primary font-medium">
<span className="material-symbols-outlined text-[13px]">water_drop</span> 80%
            </div>
</div>

<div className="p-3 rounded-xl bg-surface-container-low flex flex-col justify-between hover:bg-surface-container transition-colors col-span-2 sm:col-span-1">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md font-bold text-on-surface">SUN 15</span>
<span className="w-2 rounded-full bg-secondary"></span>
</div>
<div className="my-2 flex flex-col items-center">
<span className="material-symbols-outlined text-[32px] text-secondary">cloudy</span>
<span className="font-citation-mono text-[10px] text-on-surface-variant mt-0.5 text-center">Passing Showers</span>
</div>
<div className="flex items-center justify-between text-center pt-2">
<span className="font-headline-sm text-headline-sm text-on-surface font-bold">30°</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">26°</span>
</div>
<div className="mt-1 flex items-center justify-center gap-1 font-citation-mono text-citation-mono text-secondary font-medium">
<span className="material-symbols-outlined text-[13px]">water_drop</span> 45%
            </div>
</div>
</div>
</section>
</div>

<div className="lg:col-span-4 flex flex-col gap-space-lg">

<section className="grid grid-cols-2 gap-3">

<div className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group">
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
</div>

<div className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group">
<div className="flex items-center justify-between">
<div className="w-9 h-9 rounded-xl bg-surface-container text-secondary flex items-center justify-center group-hover:scale-105 transition-transform">
<span className="material-symbols-outlined text-[20px]">satellite_alt</span>
</div>
<span className="font-citation-mono text-[10px] text-secondary font-bold">RADAR LOOP</span>
</div>
<div className="mt-3">
<span className="font-label-md text-label-md font-bold text-on-surface block">Weekly Radar</span>
<p className="font-body-sm text-[11px] text-on-surface-variant mt-0.5 leading-tight">
              Colaba &amp; Veravali precipitation loops
            </p>
</div>
</div>

<div className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group">
<div className="flex items-center justify-between">
<div className="w-9 h-9 rounded-xl bg-secondary-fixed text-on-secondary-fixed-variant flex items-center justify-center group-hover:scale-105 transition-transform">
<span className="material-symbols-outlined text-[20px]">sailing</span>
</div>
<span className="font-citation-mono text-[10px] text-error font-bold">STAGE-II</span>
</div>
<div className="mt-3">
<span className="font-label-md text-label-md font-bold text-on-surface block">Fisheries &amp; Ports</span>
<p className="font-body-sm text-[11px] text-on-surface-variant mt-0.5 leading-tight">
              High sea wave warning: LC-III hoisted
            </p>
</div>
</div>

<div className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group">
<div className="flex items-center justify-between">
<div className="w-9 h-9 rounded-xl bg-tertiary-fixed text-on-tertiary-fixed flex items-center justify-center group-hover:scale-105 transition-transform">
<span className="material-symbols-outlined text-[20px]">agriculture</span>
</div>
<span className="font-citation-mono text-[10px] text-tertiary font-bold">ICAR SYNC</span>
</div>
<div className="mt-3">
<span className="font-label-md text-label-md font-bold text-on-surface block">Agri Advisory</span>
<p className="font-body-sm text-[11px] text-on-surface-variant mt-0.5 leading-tight">
              Kharif paddy transplant guidelines
            </p>
</div>
</div>
</section>

<section className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-on-primary">
<span className="material-symbols-outlined text-[16px]">smart_toy</span>
</div>
<span className="font-headline-sm text-headline-sm font-bold text-on-surface">WeatherGPT Copilot</span>
</div>
<span className="font-citation-mono text-citation-mono text-secondary font-semibold">Active Engine</span>
</div>

<div className="flex flex-col gap-1.5">
<span className="font-citation-mono text-citation-mono text-on-surface-variant">QUICK SITUATIONAL INQUIRIES</span>
<div className="flex flex-col gap-1.5">
<button className="text-left px-3 py-2 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center justify-between group">
<span>"When will heavy rain start today?"</span>
<span className="material-symbols-outlined text-outline group-hover:text-primary text-[16px]">north_east</span>
</button>
<button className="text-left px-3 py-2 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center justify-between group">
<span>"High tide timing at Marine Drive promenade"</span>
<span className="material-symbols-outlined text-outline group-hover:text-primary text-[16px]">north_east</span>
</button>
</div>
</div>

<form className="flex flex-col gap-2 mt-1" onSubmit={(e) => e.preventDefault()}>
<div className="relative flex items-center">
<input className="w-full pl-3 pr-20 py-3 rounded-xl bg-surface-container text-on-surface placeholder:text-on-surface-variant/70 font-body-md text-body-md focus:outline-none focus:bg-surface-container-low transition-colors shadow-inner" placeholder="Ask WeatherGPT: rain radar, coastal tide, crop advisory..." type="text"/>
<div className="absolute right-2 flex items-center gap-1">
<button className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-highest transition-colors" title="Voice Search" type="button">
<span className="material-symbols-outlined text-[20px]">mic</span>
</button>
<button className="p-1.5 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-colors shadow-sm" title="Submit Query" type="submit">
<span className="material-symbols-outlined text-[18px]">send</span>
</button>
</div>
</div>

<div className="flex items-start gap-1.5 px-1 font-citation-mono text-[10px] text-on-surface-variant leading-tight">
<span className="material-symbols-outlined text-[12px] text-secondary shrink-0 mt-0.5">verified</span>
<span>Grounded with Google Weather API, MoES &amp; INCOIS Real-time Observational Feeds (Zero Hallucination Protocol).</span>
</div>
</form>
</section>

<section className="rounded-2xl bg-surface-container-lowest p-space-md shadow-sm flex items-center gap-space-md">
<div className="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center shrink-0">
<span className="material-symbols-outlined text-primary text-[28px]">tsunami</span>
</div>
<div className="flex flex-col">
<div className="flex items-center gap-2">
<span className="font-label-md text-label-md font-bold text-on-surface">Arabian Sea Swell Alert</span>
<span className="px-1.5 py-0.2 rounded bg-tertiary-fixed text-on-tertiary-fixed font-citation-mono text-[9px] font-bold">MODERATE</span>
</div>
<p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
            Swell period: <strong>14.2s</strong> • Sea surface temp: <strong>29.4°C</strong>. Favourable for monsoonal convective squalls.
          </p>
</div>
</section>
</div>
</div>
</div>
  );
}
