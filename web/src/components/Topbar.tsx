import { useEffect, useRef, useState } from 'react';
import { CITIES } from '../data/cities';
import { useUiPrefs } from '../state/UiPrefsContext';

export default function Topbar() {
  const { city, setCity } = useUiPrefs();
  const selected = CITIES.find((c) => c.key === city);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  return (
    <header className="fixed top-0 left-64 right-0 h-16 bg-surface-container-lowest/90 backdrop-blur-xl z-40 flex items-center justify-between px-space-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <div className="flex items-center gap-space-md">
        <div className="relative" ref={rootRef}>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container-low text-on-surface font-label-md text-label-md cursor-pointer hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-primary text-[18px]">location_on</span>
            <span className="font-medium">{selected ? `${selected.name}, ${selected.region}` : city}</span>
            <span
              className={`material-symbols-outlined text-on-surface-variant text-[16px] transition-transform ${open ? 'rotate-180' : ''}`}
            >
              expand_more
            </span>
          </button>

          {open && (
            <div className="absolute left-0 top-full mt-1 w-56 rounded-xl bg-surface-container-lowest shadow-lg border border-outline-variant/30 py-1.5 z-50">
              {CITIES.map((c) => {
                const label = `${c.name}, ${c.region}`;
                const isActive = c.key === city;
                return (
                  <button
                    key={c.key}
                    type="button"
                    onClick={() => {
                      setCity(c.key);
                      setOpen(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left font-label-md text-label-md transition-colors ${
                      isActive
                        ? 'text-primary font-semibold bg-primary-container/10'
                        : 'text-on-surface hover:bg-surface-container-low'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {isActive ? 'radio_button_checked' : 'location_on'}
                    </span>
                    {label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-space-md">
        <button
          type="button"
          className="relative p-2 rounded-full hover:bg-surface-container transition-colors text-on-surface-variant"
        >
          <span className="material-symbols-outlined text-[22px]">notifications</span>
        </button>
      </div>
    </header>
  );
}
