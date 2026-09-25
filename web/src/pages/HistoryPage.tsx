export default function HistoryPage() {
  return (
    <div className="flex flex-col w-full">

<div className="flex flex-col gap-1 mb-space-lg p-space-lg rounded-2xl bg-surface-container-lowest shadow-sm">
<h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight leading-tight">Query History</h1>
<p className="font-body-md text-body-md text-on-surface-variant">Past weather queries and the grounded answers returned for them.</p>
</div>

<div className="flex flex-col sm:flex-row items-center justify-between gap-space-md px-space-lg py-space-sm bg-surface-container-lowest rounded-xl shadow-sm mb-space-lg">
<div className="flex flex-wrap items-center gap-x-space-md gap-y-1 font-body-sm text-body-sm text-on-surface-variant">
<div className="flex items-center gap-1.5 text-on-surface font-label-md">
<span className="material-symbols-outlined text-[18px] text-primary">account_circle</span>
<span>Signed in via Google Account</span>
</div>
</div>
<div className="flex items-center gap-space-sm self-end sm:self-center">
<button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low text-error hover:bg-error-container hover:text-on-error-container transition-colors font-label-md text-label-md" id="clearHistoryBtn" type="button">
<span className="material-symbols-outlined text-[18px]">delete_sweep</span>
<span>Clear History</span>
</button>
</div>
</div>

<div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-space-md mb-space-lg">

<div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0" id="filterChipsContainer">
<button className="filter-chip active-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-primary text-on-primary shadow-sm transition-all whitespace-nowrap" data-filter="all" type="button">
        All Queries
      </button>
<button className="filter-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-surface shadow-sm transition-all whitespace-nowrap" data-filter="alerts" type="button">
        Alerts
      </button>
<button className="filter-chip px-3 py-1.5 rounded-full font-label-md text-label-md bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-surface shadow-sm transition-all whitespace-nowrap" data-filter="rain" type="button">
        Rainfall &amp; Monsoon
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
</div>
<p className="font-body-md text-body-md text-on-surface font-medium">
            82% Probability of thunderstorms. Peak rain anticipated around 18:30 IST (~12 mm/hr convective accumulation).
          </p>
<div className="flex items-center gap-3 mt-1 pt-1 text-on-surface-variant text-body-sm font-body-sm">
<span>Gusts up to 42 km/h</span>
</div>
</div>

<div className="flex flex-wrap items-center gap-2 mt-1">
<span className="font-citation-mono text-citation-mono text-outline uppercase tracking-wider">Provenance:</span>
<span className="px-2 py-0.5 rounded bg-surface-container font-citation-mono text-citation-mono text-on-surface">
            Google Weather API — Hourly Forecast
          </span>
</div>
</div>

<div className="flex items-center justify-between pt-space-md mt-space-md bg-transparent">
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
<h3 className="font-headline-sm text-headline-sm text-on-surface">Grounding Guardrail</h3>
<p className="font-body-sm text-body-sm text-on-surface-variant">
          Every past answer above is checked against a live Google Weather API response before it reaches you — the LLM routes and narrates, it never invents a number.
        </p>
</div>
</div>
</div>

</div>
  );
}
