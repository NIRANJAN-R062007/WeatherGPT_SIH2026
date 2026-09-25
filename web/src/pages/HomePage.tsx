export default function HomePage() {
  return (
    <div className="flex flex-col w-full gap-space-lg">

<section className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-lg">

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-end">

<div className="lg:col-span-6 flex flex-col sm:flex-row items-start sm:items-center gap-space-lg">
<div className="flex items-baseline gap-2">
<span className="font-metric-display text-metric-display text-on-surface font-extrabold leading-none tracking-tighter">
            29°
          </span>
<span className="font-headline-sm text-headline-sm text-on-surface-variant">C</span>
</div>
<div className="flex flex-col">
<div className="flex items-center gap-2 text-primary font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[26px]">partly_cloudy_day</span>
            Partly Cloudy
          </div>
<div className="flex items-center gap-3 mt-1 font-body-md text-body-md text-on-surface-variant">
<span>Feels like <strong className="font-semibold text-on-surface">33°C</strong></span>
</div>
</div>
</div>

<div className="lg:col-span-6 flex flex-col justify-end bg-surface-container-low p-space-md rounded-xl">
<div className="flex items-center justify-between font-citation-mono text-citation-mono text-on-surface-variant mb-1">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-tertiary">wb_sunny</span> Sunrise 06:32 IST</span>
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-tertiary">bedtime</span> Sunset 18:14 IST</span>
</div>
<div className="flex items-center justify-end font-citation-mono text-citation-mono text-on-surface-variant mt-1">
<span className="px-2 py-0.5 rounded bg-surface-container text-on-surface font-semibold">UV Index: 4.8 (Moderate)</span>
</div>
</div>
</div>

<div className="grid grid-cols-3 gap-2 pt-space-md bg-surface-container-low rounded-xl p-3">
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-on-surface-variant">HUMIDITY</span>
<div className="flex items-center gap-1 text-on-surface font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-primary">humidity_high</span>
          78%
        </div>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-on-surface-variant">WIND</span>
<div className="flex items-center gap-1 text-on-surface font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-primary">north_east</span>
          14 km/h
        </div>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-on-surface-variant">PRECIPITATION</span>
<div className="flex items-center gap-1 text-on-surface font-headline-sm text-headline-sm font-semibold">
<span className="material-symbols-outlined text-[18px] text-primary">rainy</span>
          35%
        </div>
</div>
</div>
</section>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">

<div className="lg:col-span-8 flex flex-col gap-space-lg">

<section className="p-3.5 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between hover:bg-surface-container-low transition-colors cursor-pointer group max-w-xs">
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
<button className="text-left px-3 py-2 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md transition-colors flex items-center justify-between group">
<span>"When will heavy rain start today?"</span>
<span className="material-symbols-outlined text-outline group-hover:text-primary text-[16px]">north_east</span>
</button>
</div>
</div>

<form className="flex flex-col gap-2 mt-1" onSubmit={(e) => e.preventDefault()}>
<div className="relative flex items-center">
<input className="w-full pl-3 pr-20 py-3 rounded-xl bg-surface-container text-on-surface placeholder:text-on-surface-variant/70 font-body-md text-body-md focus:outline-none focus:bg-surface-container-low transition-colors shadow-inner" placeholder="Ask WeatherGPT..." type="text"/>
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
<span>Grounded with Google Weather API — every number traceable to a live API response.</span>
</div>
</form>
</section>
</div>
</div>
</div>
  );
}
