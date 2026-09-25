import { LANG_OPTIONS, useUiPrefs } from '../state/UiPrefsContext';

export default function Topbar({ city = 'Mumbai, Maharashtra' }: { city?: string }) {
  const { lang, setLang, unit, setUnit } = useUiPrefs();

  return (
    <header className="fixed top-0 left-64 right-0 h-16 bg-surface-container-lowest/90 backdrop-blur-xl z-40 flex items-center justify-between px-space-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <div className="flex items-center gap-space-md">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container-low text-on-surface font-label-md text-label-md cursor-pointer hover:bg-surface-container transition-colors">
          <span className="material-symbols-outlined text-primary text-[18px]">location_on</span>
          <span className="font-medium">{city}</span>
          <span className="material-symbols-outlined text-on-surface-variant text-[16px]">expand_more</span>
        </div>
        <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-low font-citation-mono text-citation-mono text-on-surface-variant">
          <span className="w-2 h-2 rounded-full bg-secondary" />
          <span>Live IMD Open Feeds • 08:30 IST</span>
        </div>
      </div>
      <div className="flex items-center gap-space-md">
        <div className="flex items-center p-1 rounded-full bg-surface-container-low gap-0.5 text-label-md">
          {LANG_OPTIONS.map((opt) => (
            <button
              key={opt.code}
              type="button"
              onClick={() => setLang(opt.code)}
              className={`px-2 py-0.5 rounded-full text-xs transition-colors ${
                lang === opt.code
                  ? 'bg-primary text-on-primary font-medium shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface font-normal'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex items-center bg-surface-container-low p-1 rounded-full font-label-md text-label-md text-on-surface-variant">
          <button
            type="button"
            onClick={() => setUnit('C')}
            className={`px-2 py-0.5 rounded-full text-xs transition-colors ${
              unit === 'C' ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold' : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            °C
          </button>
          <button
            type="button"
            onClick={() => setUnit('F')}
            className={`px-2 py-0.5 rounded-full text-xs transition-colors ${
              unit === 'F' ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold' : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            °F
          </button>
        </div>
        <button
          type="button"
          className="relative p-2 rounded-full hover:bg-surface-container transition-colors text-on-surface-variant"
        >
          <span className="material-symbols-outlined text-[22px]">notifications</span>
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full" />
        </button>
        <div className="flex items-center gap-2.5 pl-2 border-l border-surface-container-high">
          <div className="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary font-label-md text-label-md font-semibold flex-none">
            RS
          </div>
          <div className="hidden sm:flex flex-col text-left">
            <span className="font-label-md text-label-md text-on-surface font-semibold leading-tight">Rohit Sharma</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant leading-none">Citizen Account</span>
          </div>
        </div>
      </div>
    </header>
  );
}
