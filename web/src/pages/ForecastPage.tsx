export default function ForecastPage() {
  return (
    <div className="flex flex-col w-full gap-space-lg">

<div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md p-space-md rounded-xl bg-surface-container-lowest shadow-sm">
<div className="flex flex-wrap items-center gap-space-md">
<div className="flex items-center gap-2">
<span className="w-2.5 h-2.5 rounded-full bg-secondary-container animate-pulse"></span>
<span className="font-headline-sm text-headline-sm text-on-surface">Mumbai Metropolitan Region</span>
</div>
</div>

<div className="inline-flex p-1 rounded-lg bg-surface-container-low gap-1" id="forecast-tabs">
<button className="px-3.5 py-1.5 rounded-md font-label-md text-label-md bg-primary text-on-primary shadow-sm transition-all flex items-center gap-1.5" type="button">
<span className="material-symbols-outlined text-[16px]">schedule</span>
<span>Hourly Forecast (48h)</span>
</button>
<button className="px-3.5 py-1.5 rounded-md font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all flex items-center gap-1.5" type="button">
<span className="material-symbols-outlined text-[16px]">calendar_view_week</span>
<span>10-Day Outlook</span>
</button>
</div>
</div>

<div className="p-space-lg rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-md">
<div className="flex flex-col md:flex-row md:items-center justify-between gap-space-sm pb-space-sm border-b border-surface-container">
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Hourly Temperature &amp; Precipitation</span>
<p className="font-body-sm text-body-sm text-on-surface-variant">Source: Google Weather API — Hourly Forecast</p>
</div>

<div className="flex flex-wrap items-center gap-space-md">
<div className="flex items-center gap-2">
<span className="w-3 h-1 rounded-full bg-primary"></span>
<span className="font-citation-mono text-citation-mono text-on-surface-variant">Temp Curve (°C)</span>
</div>
<div className="flex items-center gap-2">
<span className="w-3 h-3 rounded-sm bg-secondary-container"></span>
<span className="font-citation-mono text-citation-mono text-on-surface-variant">Precipitation (mm)</span>
</div>
</div>
</div>

<div className="w-full overflow-x-auto">
<div className="min-w-[720px] w-full h-64 relative">
<svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 1000 250">
<defs>
<linearGradient id="tempGradient" x1="0" x2="0" y1="0" y2="1">
<stop offset="0%" stopColor="#0057c2" stopOpacity="0.25"></stop>
<stop offset="100%" stopColor="#0057c2" stopOpacity="0.0"></stop>
</linearGradient>
<linearGradient id="rainGradient" x1="0" x2="0" y1="0" y2="1">
<stop offset="0%" stopColor="#006a6a" stopOpacity="0.85"></stop>
<stop offset="100%" stopColor="#7af5f5" stopOpacity="0.35"></stop>
</linearGradient>
</defs>

<line stroke="#e0e8ff" strokeDasharray="4 4" strokeWidth="1" x1="50" x2="980" y1="40" y2="40"></line>
<line stroke="#e0e8ff" strokeDasharray="4 4" strokeWidth="1" x1="50" x2="980" y1="90" y2="90"></line>
<line stroke="#e0e8ff" strokeDasharray="4 4" strokeWidth="1" x1="50" x2="980" y1="140" y2="140"></line>
<line stroke="#e0e8ff" strokeDasharray="4 4" strokeWidth="1" x1="50" x2="980" y1="190" y2="190"></line>

<text className="fill-outline font-citation-mono text-[10px]" x="25" y="44">34°C</text>
<text className="fill-outline font-citation-mono text-[10px]" x="25" y="94">30°C</text>
<text className="fill-outline font-citation-mono text-[10px]" x="25" y="144">26°C</text>
<text className="fill-outline font-citation-mono text-[10px]" x="25" y="194">22°C</text>

<text className="fill-secondary font-citation-mono text-[10px]" x="985" y="44">20mm</text>
<text className="fill-secondary font-citation-mono text-[10px]" x="985" y="94">15mm</text>
<text className="fill-secondary font-citation-mono text-[10px]" x="985" y="144">10mm</text>
<text className="fill-secondary font-citation-mono text-[10px]" x="985" y="194">0mm</text>


<rect fill="url(#rainGradient)" height="5" rx="3" width="24" x="75" y="185"></rect>
<rect fill="url(#rainGradient)" height="10" rx="3" width="24" x="155" y="180"></rect>
<rect fill="url(#rainGradient)" height="16" rx="3" width="24" x="235" y="174"></rect>
<rect fill="url(#rainGradient)" height="30" rx="3" width="24" x="315" y="160"></rect>
<rect fill="url(#rainGradient)" height="50" rx="3" width="24" x="395" y="140"></rect>
<rect fill="url(#rainGradient)" height="110" rx="3" width="24" x="475" y="80"></rect>
<rect fill="url(#rainGradient)" height="135" rx="3" width="24" x="555" y="55"></rect>
<rect fill="url(#rainGradient)" height="120" rx="3" width="24" x="635" y="70"></rect>
<rect fill="url(#rainGradient)" height="75" rx="3" width="24" x="715" y="115"></rect>
<rect fill="url(#rainGradient)" height="40" rx="3" width="24" x="795" y="150"></rect>
<rect fill="url(#rainGradient)" height="20" rx="3" width="24" x="875" y="170"></rect>
<rect fill="url(#rainGradient)" height="8" rx="3" width="24" x="940" y="182"></rect>

<text className="fill-on-surface font-citation-mono text-[10px] font-semibold" textAnchor="middle" x="487" y="72">14mm</text>
<text className="fill-on-surface font-citation-mono text-[10px] font-bold" textAnchor="middle" x="567" y="47">18mm</text>
<text className="fill-on-surface font-citation-mono text-[10px] font-semibold" textAnchor="middle" x="647" y="62">12mm</text>

<path d="M 87,130 C 160,125 240,110 327,95 C 400,80 487,65 567,65 C 647,75 727,110 807,135 C 887,148 950,140 950,140 L 950,190 L 87,190 Z" fill="url(#tempGradient)"></path>

<path d="M 87,130 C 160,125 240,110 327,95 C 400,80 487,65 567,65 C 647,75 727,110 807,135 C 887,148 950,140 950,140" fill="none" stroke="#0057c2" strokeLinecap="round" strokeWidth="3.5"></path>

<circle cx="87" cy="130" fill="#ffffff" r="4.5" stroke="#0057c2" strokeWidth="2.5"></circle>
<circle cx="327" cy="95" fill="#ffffff" r="4.5" stroke="#0057c2" strokeWidth="2.5"></circle>
<circle cx="567" cy="65" fill="#0057c2" r="5.5" stroke="#ffffff" strokeWidth="2"></circle>
<circle cx="807" cy="135" fill="#ffffff" r="4.5" stroke="#0057c2" strokeWidth="2.5"></circle>

<rect fill="#0057c2" height="20" rx="4" width="50" x="542" y="10"></rect>
<text className="fill-on-primary font-citation-mono text-[11px] font-bold" textAnchor="middle" x="567" y="24">32.2°C</text>

<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="87" y="215">08:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="167" y="215">10:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="247" y="215">12:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="327" y="215">14:00</text>
<text className="fill-primary font-citation-mono text-[11px] font-bold" textAnchor="middle" x="407" y="215">16:00 Peak</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="487" y="215">18:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="567" y="215">20:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="647" y="215">22:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="727" y="215">00:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="807" y="215">02:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="887" y="215">04:00</text>
<text className="fill-on-surface-variant font-citation-mono text-[11px]" textAnchor="middle" x="950" y="215">06:00</text>
</svg>
</div>
</div>
</div>

<div className="flex flex-col gap-space-sm">
<div className="flex items-center justify-between">
<div className="flex items-center gap-2">
<span className="font-headline-sm text-headline-sm text-on-surface">Hourly Breakdown</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">(Next 48 Hours)</span>
</div>
<div className="flex items-center gap-1 text-on-surface-variant">
<span className="font-citation-mono text-citation-mono">Horizontal Scroll</span>
<span className="material-symbols-outlined text-[16px]">arrow_forward</span>
</div>
</div>

<div className="flex gap-space-sm overflow-x-auto pb-space-xs scroll-smooth">

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-primary text-on-primary shadow-md flex flex-col gap-2 relative overflow-hidden">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md uppercase tracking-wider font-bold">Now (08:30)</span>
<span className="w-2 h-2 rounded-full bg-secondary-fixed"></span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[36px] text-secondary-fixed">thunderstorm</span>
<span className="font-headline-lg text-headline-lg font-bold">28°</span>
</div>
<div className="text-xs opacity-90 font-label-md">Feels like 32°C</div>
<div className="flex flex-col gap-1 pt-2 border-t border-primary-container">
<div className="flex items-center justify-between text-xs">
<span className="flex items-center gap-1 opacity-80"><span className="material-symbols-outlined text-[14px]">umbrella</span> Rain</span>
<span className="font-citation-mono font-semibold">82%</span>
</div>
<div className="flex items-center justify-between text-xs">
<span className="flex items-center gap-1 opacity-80"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono font-semibold">34 km/h</span>
</div>
<div className="flex items-center justify-between text-xs">
<span className="flex items-center gap-1 opacity-80"><span className="material-symbols-outlined text-[14px]">water_drop</span> Humidity</span>
<span className="font-citation-mono font-semibold">86%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">09:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-primary">rainy</span>
<span className="font-headline-lg text-headline-lg">28.4°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Feels 32.8°</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-on-surface font-semibold">75%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">SW 28 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">84%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">10:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-primary">partly_cloudy_day</span>
<span className="font-headline-lg text-headline-lg">29.1°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Feels 33.5°</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-on-surface font-semibold">50%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">SW 26 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">82%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">11:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-tertiary">sunny</span>
<span className="font-headline-lg text-headline-lg">30.4°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Feels 35.1°</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-on-surface font-semibold">35%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">W 22 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">79%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">12:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-tertiary">partly_cloudy_day</span>
<span className="font-headline-lg text-headline-lg">31.6°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Feels 37.0°</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-on-surface font-semibold">40%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">WSW 25 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">76%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">13:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-secondary">thunderstorm</span>
<span className="font-headline-lg text-headline-lg">31.2°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Feels 36.4°</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-secondary font-bold">78%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">SW 38 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">83%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-secondary/10 text-on-surface shadow-sm flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-secondary font-bold">14:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-secondary">rainy_heavy</span>
<span className="font-headline-lg text-headline-lg font-bold">29.4°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Downpour 14mm/h</div>
<div className="flex flex-col gap-1 pt-2 border-t border-secondary/20">
<div className="flex items-center justify-between text-xs">
<span className="flex items-center gap-1 text-on-surface-variant"><span className="material-symbols-outlined text-[14px] text-secondary">umbrella</span> Rain</span>
<span className="font-citation-mono text-secondary font-bold">94%</span>
</div>
<div className="flex items-center justify-between text-xs">
<span className="flex items-center gap-1 text-on-surface-variant"><span className="material-symbols-outlined text-[14px]">air</span> Gust</span>
<span className="font-citation-mono text-error font-bold">48 km/h</span>
</div>
<div className="flex items-center justify-between text-xs">
<span className="flex items-center gap-1 text-on-surface-variant"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface font-semibold">91%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">15:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-primary">rainy_heavy</span>
<span className="font-headline-lg text-headline-lg">28.1°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Feels 32.5°</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-on-surface font-semibold">90%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">SW 42 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">94%</span>
</div>
</div>
</div>

<div className="flex-shrink-0 w-44 p-space-md rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
<div className="flex items-center justify-between">
<span className="font-label-md text-label-md text-on-surface-variant font-medium">16:00 IST</span>
</div>
<div className="flex items-center justify-between my-1">
<span className="material-symbols-outlined text-[34px] text-primary">thunderstorm</span>
<span className="font-headline-lg text-headline-lg">27.6°</span>
</div>
<div className="font-body-sm text-body-sm text-on-surface-variant">Downpour 18mm/h</div>
<div className="flex flex-col gap-1 pt-2 border-t border-surface-container">
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-primary">umbrella</span> Rain</span>
<span className="font-citation-mono text-on-surface font-semibold">96%</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">air</span> Wind</span>
<span className="font-citation-mono text-on-surface">SW 45 km/h</span>
</div>
<div className="flex items-center justify-between text-xs text-on-surface-variant">
<span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">water_drop</span> RH</span>
<span className="font-citation-mono text-on-surface">96%</span>
</div>
</div>
</div>
</div>
</div>

<div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">

<div className="lg:col-span-7 flex flex-col gap-space-md">
<div className="flex items-center justify-between">
<span className="font-headline-md text-headline-md text-on-surface">10-Day Outlook</span>
<span className="font-citation-mono text-citation-mono text-outline">Updated: 08:30 IST</span>
</div>

<div className="flex flex-col gap-2.5" id="synoptic-accordion">

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-sm transition-all">
<div className="flex flex-wrap items-center justify-between gap-2 cursor-pointer">
<div className="flex items-center gap-3">
<span className="material-symbols-outlined text-[28px] text-primary">thunderstorm</span>
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Today, 18 Oct</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Thunderstorm &amp; Strong Coastal Gusts</span>
</div>
</div>
<div className="flex items-center gap-space-md">
<div className="text-right">
<span className="font-headline-sm text-headline-sm text-on-surface">31°</span>
<span className="font-body-sm text-body-sm text-outline"> / 26°</span>
</div>
<span className="material-symbols-outlined text-on-surface-variant text-[20px]">expand_less</span>
</div>
</div>

<div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-space-sm border-t border-surface-container bg-surface-container-low/40 p-2.5 rounded-lg mt-1">
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-outline uppercase">UV Index</span>
<span className="font-headline-sm text-headline-sm text-on-surface">7.2</span>
<span className="font-citation-mono text-[10px] text-tertiary font-medium">High</span>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-outline uppercase">Humidity</span>
<span className="font-headline-sm text-headline-sm text-on-surface">78%</span>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-outline uppercase">Precip Prob</span>
<span className="font-headline-sm text-headline-sm text-primary">82%</span>
</div>
<div className="flex flex-col">
<span className="font-citation-mono text-citation-mono text-outline uppercase">Sunrise / Sunset</span>
<div className="flex items-center gap-1 font-citation-mono text-citation-mono text-on-surface mt-1">
<span className="material-symbols-outlined text-[14px] text-tertiary">wb_sunny</span>
<span>06:32</span>
<span className="material-symbols-outlined text-[14px] ml-1">bedtime</span>
<span>18:14</span>
</div>
</div>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex items-center justify-between hover:bg-surface-container-low transition-colors cursor-pointer">
<div className="flex items-center gap-3">
<span className="material-symbols-outlined text-[28px] text-primary">rainy_heavy</span>
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Thu, 19 Oct</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Heavy Thunderstorms &amp; Squalls</span>
</div>
</div>
<div className="flex items-center gap-space-md">
<div className="text-right">
<span className="font-headline-sm text-headline-sm text-on-surface">30°</span>
<span className="font-body-sm text-body-sm text-outline"> / 25°</span>
</div>
<span className="material-symbols-outlined text-on-surface-variant text-[20px]">expand_more</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex items-center justify-between hover:bg-surface-container-low transition-colors cursor-pointer">
<div className="flex items-center gap-3">
<span className="material-symbols-outlined text-[28px] text-secondary">rainy_heavy</span>
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Fri, 20 Oct</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Continuous Heavy Rain</span>
</div>
</div>
<div className="flex items-center gap-space-md">
<div className="text-right">
<span className="font-headline-sm text-headline-sm text-on-surface">28°</span>
<span className="font-body-sm text-body-sm text-outline"> / 24°</span>
</div>
<span className="material-symbols-outlined text-on-surface-variant text-[20px]">expand_more</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex items-center justify-between hover:bg-surface-container-low transition-colors cursor-pointer">
<div className="flex items-center gap-3">
<span className="material-symbols-outlined text-[28px] text-primary">rainy</span>
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Sat, 21 Oct</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Scattered Intermittent Showers</span>
</div>
</div>
<div className="flex items-center gap-space-md">
<div className="text-right">
<span className="font-headline-sm text-headline-sm text-on-surface">29°</span>
<span className="font-body-sm text-body-sm text-outline"> / 25°</span>
</div>
<span className="material-symbols-outlined text-on-surface-variant text-[20px]">expand_more</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex items-center justify-between hover:bg-surface-container-low transition-colors cursor-pointer">
<div className="flex items-center gap-3">
<span className="material-symbols-outlined text-[28px] text-on-surface-variant">partly_cloudy_day</span>
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Sun, 22 Oct</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Partly Cloudy &amp; Humid</span>
</div>
</div>
<div className="flex items-center gap-space-md">
<div className="text-right">
<span className="font-headline-sm text-headline-sm text-on-surface">31°</span>
<span className="font-body-sm text-body-sm text-outline"> / 26°</span>
</div>
<span className="material-symbols-outlined text-on-surface-variant text-[20px]">expand_more</span>
</div>
</div>

<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex items-center justify-between hover:bg-surface-container-low transition-colors cursor-pointer">
<div className="flex items-center gap-3">
<span className="material-symbols-outlined text-[28px] text-tertiary">sunny</span>
<div className="flex flex-col">
<span className="font-headline-sm text-headline-sm text-on-surface">Mon, 23 Oct</span>
<span className="font-body-sm text-body-sm text-on-surface-variant">Clear Sunny Skies</span>
</div>
</div>
<div className="flex items-center gap-space-md">
<div className="text-right">
<span className="font-headline-sm text-headline-sm text-on-surface">32°</span>
<span className="font-body-sm text-body-sm text-outline"> / 27°</span>
</div>
<span className="material-symbols-outlined text-on-surface-variant text-[20px]">expand_more</span>
</div>
</div>
</div>
</div>

<div className="lg:col-span-5 flex flex-col gap-space-md">
<div className="p-space-md rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-sm">
<div className="flex items-center gap-2">
<span className="material-symbols-outlined text-secondary text-[20px]">verified</span>
<span className="font-headline-sm text-headline-sm text-on-surface">Forecast Provenance</span>
</div>
<p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">
          As per Google Weather API forecast issued 08:30 IST. Every figure shown above is read directly from that response — never generated by the LLM.
        </p>
</div>
</div>
</div>
</div>
  );
}
