export default function HistoryPage() {
  return (
    <div className="flex flex-col w-full">

<div className="relative w-full rounded-2xl overflow-hidden shadow-md mb-space-lg bg-surface-container-high">
<div className="w-full h-48 bg-cover bg-center" data-alt="Dramatic aerial view of Marine Drive Mumbai during Indian monsoon sunset, stormy dark slate clouds breaking with glowing amber sunbeams, high sea waves crashing violently against concrete tetrapods along the promenade, wet reflective asphalt with yellow and black taxis, authoritative atmospheric mood in deep navy blue, teal, and gold tones." style={{ backgroundImage: "url('/images/hero-marine-drive-history.jpg')" }}></div>
<div className="absolute inset-0 bg-gradient-to-r from-on-background/90 via-on-background/60 to-transparent flex items-center px-space-xl">
<div className="flex flex-col gap-1 max-w-xl text-surface-bright">
<div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-surface-bright/20 backdrop-blur-md w-fit">
<span className="w-2 h-2 rounded-full bg-secondary-container"></span>
<span className="font-citation-mono text-citation-mono uppercase tracking-wider text-surface-bright">Cryptographic Audit Trail</span>
</div>
<h1 className="font-headline-lg text-headline-lg text-surface-bright tracking-tight leading-tight">Query History &amp; Grounding Evidence Log</h1>
<p className="font-body-md text-body-md text-surface-container-high">Auditable archive of AI weather inquiries, telemetry citations, and model outputs verified against MoES &amp; IMD telemetry feeds.</p>
</div>
</div>
</div>

<div className="flex flex-col sm:flex-row items-center justify-between gap-space-md px-space-lg py-space-sm bg-surface-container-lowest rounded-xl shadow-sm mb-space-lg">
<div className="flex flex-wrap items-center gap-x-space-md gap-y-1 font-body-sm text-body-sm text-on-surface-variant">
<div className="flex items-center gap-1.5 text-on-surface font-label-md">
<span className="material-symbols-outlined text-[18px] text-primary">account_circle</span>
<span>rohit.sharma@gmail.com</span>
</div>
<span className="text-outline-variant">•</span>
<span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>Synced via Google Account</span>
<span className="text-outline-variant">•</span>
<span>Local encrypted cache intact</span>
<span className="text-outline-variant">•</span>
<span className="font-citation-mono text-citation-mono text-on-surface bg-surface-container px-2 py-0.5 rounded">ZERO TELEMETRY KEYS STORED</span>
</div>
<div className="flex items-center gap-space-sm self-end sm:self-center">
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low text-error hover:bg-error-container hover:text-on-error-container transition-colors font-label-md text-label-md" id="clearHistoryBtn" type="button">
<span className="material-symbols-outlined text-[18px]">delete_sweep</span>
<span>Clear History</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-colors shadow-sm font-label-md text-label-md" id="exportJsonBtn" type="button">
<span className="material-symbols-outlined text-[18px]">download</span>
<span>Export JSON</span>
</button>
</div>
</div>

<div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-space-md mb-space-lg">

<div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0" id="filterChipsContainer">
<button className="filter-chip active-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-primary text-on-primary shadow-sm transition-all whitespace-nowrap" data-filter="all" type="button">
        All Queries (28)
      </button>
<button className="filter-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-surface shadow-sm transition-all whitespace-nowrap" data-filter="alerts" type="button">
        Alerts (6)
      </button>
<button className="filter-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-surface shadow-sm transition-all whitespace-nowrap" data-filter="rain" type="button">
        Rainfall &amp; Monsoon (14)
      </button>
<button className="filter-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-surface shadow-sm transition-all whitespace-nowrap" data-filter="marine" type="button">
        Marine &amp; Ports (5)
      </button>
<button className="filter-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-surface shadow-sm transition-all whitespace-nowrap" data-filter="agri" type="button">
        Agricultural (3)
      </button>
</div>

<div className="relative w-full md:w-80 flex-shrink-0">
<span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-outline">
<span className="material-symbols-outlined text-[20px]">search</span>
</span>
<input className="w-full pl-10 pr-4 py-2 bg-surface-container-lowest text-on-surface placeholder:text-outline text-body-sm font-body-sm rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all" id="archiveSearchInput" placeholder="Search past weather queries, locations, or dates..." type="text"/>
</div>
</div>

<div className="grid grid-cols-1 xl:grid-cols-2 gap-space-lg mb-space-xl" id="queryArchiveGrid">

<div className="archive-card group flex flex-col justify-between bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm hover:shadow-md transition-all duration-300" data-category="rain" data-keywords="colaba mumbai rain thunderstorm outdoor evening">
<div className="flex flex-col gap-space-sm">
<div className="flex items-start justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2.5 py-0.5 rounded-full bg-surface-container-high text-primary font-citation-mono text-citation-mono font-medium">PRECIPITATION FORECAST</span>
<span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[14px]">location_on</span> Mumbai, Colaba
            </span>
</div>
<span className="font-citation-mono text-citation-mono text-outline shrink-0">Today, 08:34 IST</span>
</div>
<div className="flex items-baseline gap-2 mt-1">
<span className="material-symbols-outlined text-primary text-[20px] shrink-0">chat</span>
<h2 className="font-headline-sm text-headline-sm text-on-surface leading-snug">"Will it rain in Colaba, Mumbai this evening? Need to plan outdoor event."</h2>
</div>
<div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs mt-1">
<div className="flex items-center justify-between">
<span className="font-citation-mono text-citation-mono uppercase text-secondary font-semibold flex items-center gap-1">
<span className="material-symbols-outlined text-[16px]">verified</span> Grounded Synthesis
            </span>
<span className="font-citation-mono text-citation-mono text-outline">Confidence: 94.2%</span>
</div>
<p className="font-body-md text-body-md text-on-surface font-medium">
            82% Probability of thunderstorms. Peak rain anticipated around 18:30 IST (~12 mm/hr convective accumulation).
          </p>
<div className="flex items-center gap-3 mt-1 pt-1 text-on-surface-variant text-body-sm font-body-sm">
<div className="flex items-center gap-1 text-secondary font-medium">
<span className="material-symbols-outlined text-[16px]">storm</span> Convective Cell #4B Active
            </div>
<span className="text-outline-variant">•</span>
<span>Gusts up to 42 km/h</span>
</div>
</div>

<div className="flex flex-wrap items-center gap-2 mt-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider">Provenance:</span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            Google Weather API (GFS Hourly)
          </span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            IMD Station ID: 43003 (Colaba AWS)
          </span>
</div>
</div>

<div className="flex items-center justify-between pt-space-md mt-space-md bg-transparent">
<button className="evidence-inspect-btn inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container-high transition-colors font-label-md text-label-md" data-target="json-modal-1" type="button">
<span className="material-symbols-outlined text-[18px]">data_object</span>
<span>Evidence &amp; JSON</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed text-on-primary-fixed hover:bg-primary hover:text-on-primary transition-colors font-label-md text-label-md" type="button">
<span className="material-symbols-outlined text-[18px]">refresh</span>
<span>Ask again</span>
</button>
</div>
</div>

<div className="archive-card group flex flex-col justify-between bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm hover:shadow-md transition-all duration-300" data-category="marine alerts" data-keywords="marine drive high tide surge promenade safe wave mumbai">
<div className="flex flex-col gap-space-sm">
<div className="flex items-start justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-citation-mono text-citation-mono font-medium">HIGH TIDE &amp; COASTAL ALERT</span>
<span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[14px]">location_on</span> Mumbai, Marine Drive
            </span>
</div>
<span className="font-citation-mono text-citation-mono text-outline shrink-0">Yesterday, 19:15 IST</span>
</div>
<div className="flex items-baseline gap-2 mt-1">
<span className="material-symbols-outlined text-secondary text-[20px] shrink-0">chat</span>
<h2 className="font-headline-sm text-headline-sm text-on-surface leading-snug">"When is high tide today and is Marine Drive safe?"</h2>
</div>
<div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs mt-1">
<div className="flex items-center justify-between">
<span className="font-citation-mono text-citation-mono uppercase text-secondary font-semibold flex items-center gap-1">
<span className="material-symbols-outlined text-[16px]">verified</span> Grounded Synthesis
            </span>
<span className="font-citation-mono text-citation-mono text-error font-medium">Alert Level: Orange</span>
</div>
<p className="font-body-md text-body-md text-on-surface font-medium">
            Astronomical High Tide: 4.41m at 14:26 IST. Strict civic caution advised along promenade; tetrapod splash surge risk.
          </p>
<div className="flex items-center gap-3 mt-1 pt-1 text-on-surface-variant text-body-sm font-body-sm">
<div className="flex items-center gap-1 text-on-surface-variant font-medium">
<span className="material-symbols-outlined text-[16px]">tsunami</span> Swell Height: 3.2m
            </div>
<span className="text-outline-variant">•</span>
<span>INCOIS Warning Zone: MH-South-02</span>
</div>
</div>

<div className="flex flex-wrap items-center gap-2 mt-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider">Provenance:</span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            INCOIS Coastal Ocean Advisory Feeds
          </span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            MCGM Public Disaster Cell
          </span>
</div>
</div>

<div className="flex items-center justify-between pt-space-md mt-space-md bg-transparent">
<button className="evidence-inspect-btn inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container-high transition-colors font-label-md text-label-md" data-target="json-modal-2" type="button">
<span className="material-symbols-outlined text-[18px]">data_object</span>
<span>Evidence &amp; JSON</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed text-on-primary-fixed hover:bg-primary hover:text-on-primary transition-colors font-label-md text-label-md" type="button">
<span className="material-symbols-outlined text-[18px]">refresh</span>
<span>Ask again</span>
</button>
</div>
</div>

<div className="archive-card group flex flex-col justify-between bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm hover:shadow-md transition-all duration-300" data-category="agri" data-keywords="spray fungicide tomato crop nashik maharashtra agriculture rain humidity">
<div className="flex flex-col gap-space-sm">
<div className="flex items-start justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2.5 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant font-citation-mono text-citation-mono font-medium">AGRICULTURAL ADVISORY</span>
<span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[14px]">location_on</span> Nashik, Maharashtra
            </span>
</div>
<span className="font-citation-mono text-citation-mono text-outline shrink-0">16 Oct, 11:20 IST</span>
</div>
<div className="flex items-baseline gap-2 mt-1">
<span className="material-symbols-outlined text-tertiary text-[20px] shrink-0">chat</span>
<h2 className="font-headline-sm text-headline-sm text-on-surface leading-snug">"Can I spray fungicide on tomato crop tomorrow?"</h2>
</div>
<div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs mt-1">
<div className="flex items-center justify-between">
<span className="font-citation-mono text-citation-mono uppercase text-tertiary font-semibold flex items-center gap-1">
<span className="material-symbols-outlined text-[16px]">verified</span> Grounded Synthesis
            </span>
<span className="font-citation-mono text-citation-mono text-error font-medium">Advisory: Postpone Spray</span>
</div>
<p className="font-body-md text-body-md text-on-surface font-medium">
            Spray Window: Unfavorable. High relative humidity (84%) and scattered showers expected between 11:00 and 16:00 IST. High runoff risk.
          </p>
<div className="flex items-center gap-3 mt-1 pt-1 text-on-surface-variant text-body-sm font-body-sm">
<div className="flex items-center gap-1 text-on-surface font-medium">
<span className="material-symbols-outlined text-[16px]">water_drop</span> RH: 84%
            </div>
<span className="text-outline-variant">•</span>
<span>Recommended Window: Post-48h clearance</span>
</div>
</div>

<div className="flex flex-wrap items-center gap-2 mt-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider">Provenance:</span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            MoES Gramin Krishi Mausam Sewa (GKMS)
          </span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            KVK Nashik Agromet Bulletin #89
          </span>
</div>
</div>

<div className="flex items-center justify-between pt-space-md mt-space-md bg-transparent">
<button className="evidence-inspect-btn inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container-high transition-colors font-label-md text-label-md" data-target="json-modal-3" type="button">
<span className="material-symbols-outlined text-[18px]">data_object</span>
<span>Evidence &amp; JSON</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed text-on-primary-fixed hover:bg-primary hover:text-on-primary transition-colors font-label-md text-label-md" type="button">
<span className="material-symbols-outlined text-[18px]">refresh</span>
<span>Ask again</span>
</button>
</div>
</div>

<div className="archive-card group flex flex-col justify-between bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm hover:shadow-md transition-all duration-300" data-category="alerts" data-keywords="delhi aqi air quality anand vihar pm2.5 poor category pollution">
<div className="flex flex-col gap-space-sm">
<div className="flex items-start justify-between gap-2">
<div className="flex flex-wrap items-center gap-1.5">
<span className="px-2.5 py-0.5 rounded-full bg-error-container text-on-error-container font-citation-mono text-citation-mono font-medium">AIR QUALITY INDEX</span>
<span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-body-sm">
<span className="material-symbols-outlined text-[14px]">location_on</span> Delhi, Anand Vihar
            </span>
</div>
<span className="font-citation-mono text-citation-mono text-outline shrink-0">14 Oct, 07:45 IST</span>
</div>
<div className="flex items-baseline gap-2 mt-1">
<span className="material-symbols-outlined text-error text-[20px] shrink-0">chat</span>
<h2 className="font-headline-sm text-headline-sm text-on-surface leading-snug">"What is the AQI in Delhi today?"</h2>
</div>
<div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs mt-1">
<div className="flex items-center justify-between">
<span className="font-citation-mono text-citation-mono uppercase text-error font-semibold flex items-center gap-1">
<span className="material-symbols-outlined text-[16px]">warning</span> Grounded Synthesis
            </span>
<span className="font-citation-mono text-citation-mono text-on-surface-variant">CPCB Standard (SAMEER)</span>
</div>
<p className="font-body-md text-body-md text-on-surface font-medium">
            AQI 268 (Poor Category). PM2.5 primary pollutant measured at 162 µg/m³. Vulnerable individuals advised to minimize outdoor exertion.
          </p>
<div className="flex items-center gap-3 mt-1 pt-1 text-on-surface-variant text-body-sm font-body-sm">
<div className="flex items-center gap-1 text-error font-semibold">
<span className="material-symbols-outlined text-[16px]">masks</span> N95 Filter Advised
            </div>
<span className="text-outline-variant">•</span>
<span>Wind Speed: 4.8 km/h Calm</span>
</div>
</div>

<div className="flex flex-wrap items-center gap-2 mt-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider">Provenance:</span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            CPCB Open National Air Quality Feeds
          </span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            CAAQMS Anand Vihar Station
          </span>
</div>
</div>

<div className="flex items-center justify-between pt-space-md mt-space-md bg-transparent">
<button className="evidence-inspect-btn inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container-high transition-colors font-label-md text-label-md" data-target="json-modal-4" type="button">
<span className="material-symbols-outlined text-[18px]">data_object</span>
<span>Evidence &amp; JSON</span>
</button>
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed text-on-primary-fixed hover:bg-primary hover:text-on-primary transition-colors font-label-md text-label-md" type="button">
<span className="material-symbols-outlined text-[18px]">refresh</span>
<span>Ask again</span>
</button>
</div>
</div>
</div>

<div className="flex flex-col md:flex-row items-center justify-between gap-space-md p-space-lg rounded-2xl bg-surface-container-low mb-space-lg">
<div className="flex items-center gap-space-md">
<div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
<span className="material-symbols-outlined text-[28px]">verified_user</span>
</div>
<div className="flex flex-col">
<h3 className="font-headline-sm text-headline-sm text-on-surface">Civic Integrity &amp; Open Public-Good Architecture</h3>
<p className="font-body-sm text-body-sm text-on-surface-variant">
          WeatherGPT queries are cryptographically grounded against public datasets provided by the Ministry of Earth Sciences (MoES), IMD Doppler arrays, and Google Weather APIs.
        </p>
</div>
</div>
<div className="flex items-center gap-space-sm shrink-0">
<div className="px-3 py-1.5 rounded-lg bg-surface-container-lowest shadow-sm flex items-center gap-2">
<span className="material-symbols-outlined text-secondary text-[18px]">lock</span>
<span className="font-citation-mono text-citation-mono text-on-surface">SSL 256-BIT SYNC</span>
</div>
<div className="px-3 py-1.5 rounded-lg bg-surface-container-lowest shadow-sm flex items-center gap-2">
<span className="material-symbols-outlined text-primary text-[18px]">api</span>
<span className="font-citation-mono text-citation-mono text-on-surface">VERIFIABLE VIA API</span>
</div>
</div>
</div>

<div className="fixed inset-0 bg-on-background/40 backdrop-blur-sm z-50 hidden flex items-center justify-center p-space-md" id="jsonModalOverlay">
<div className="bg-surface-container-lowest rounded-2xl shadow-xl max-w-2xl w-full max-h-[870px] flex flex-col overflow-hidden">

<div className="px-space-lg py-space-md bg-surface-container-low flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-primary text-[22px]">terminal</span>
<span className="font-headline-sm text-headline-sm text-on-surface">Telemetry Evidence Grounding</span>
</div>
<button className="p-1 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant" id="closeModalBtn" type="button">
<span className="material-symbols-outlined text-[20px]">close</span>
</button>
</div>

<div className="p-space-lg overflow-y-auto flex flex-col gap-space-md bg-surface-container-lowest">
<div className="flex items-center justify-between text-body-sm text-on-surface-variant">
<span>Source: <strong className="text-on-surface font-citation-mono">IMD Doppler Network + GFS 0.25°</strong></span>
<span className="font-citation-mono text-citation-mono bg-surface-container px-2 py-0.5 rounded text-on-surface">SHA-256 Verified</span>
</div>
<pre className="p-space-md rounded-xl bg-on-background text-inverse-on-surface font-citation-mono text-citation-mono overflow-x-auto leading-relaxed" id="jsonContent"></pre>
</div>

<div className="px-space-lg py-space-sm bg-surface-container-low flex items-center justify-between">
<span className="font-citation-mono text-citation-mono text-outline">RESPONSE_LATENCY: 342ms • MODEL: WeatherGPT-v2-flash</span>
<button className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container-lowest hover:bg-surface-container text-on-surface font-label-md text-label-md shadow-sm transition-colors" id="copyJsonBtn" type="button">
<span className="material-symbols-outlined text-[16px]">content_copy</span>
<span>Copy Raw JSON</span>
</button>
</div>
</div>
</div>
</div>

  );
}
