import type { ReactNode } from 'react';
import { LANG_OPTIONS, useUiPrefs } from '../state/UiPrefsContext';

const PERSONAS = [
  { id: 'general', label: 'General Citizen', icon: 'person', blurb: 'Plain-language current conditions and forecast.' },
  { id: 'farmer', label: 'Farmer', icon: 'agriculture', blurb: 'Spraying and harvest-window framing on the same data.' },
  { id: 'fisherman', label: 'Fisherman', icon: 'sailing', blurb: 'Wind, swell and coastal-safety framing.' },
  { id: 'aviation', label: 'Aviation', icon: 'flight', blurb: 'METAR-style briefing language.' },
  { id: 'city-official', label: 'City Official', icon: 'apartment', blurb: 'Ward-level impact and disaster-response framing.' },
];

function SectionCard({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <section className="bg-surface-container-lowest rounded-xl shadow-sm p-space-lg flex flex-col gap-space-md">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-primary text-[20px]">{icon}</span>
        <h2 className="font-headline-sm text-headline-sm text-on-surface">{title}</h2>
      </div>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const { lang, setLang, unit, setUnit } = useUiPrefs();

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg font-bold text-on-surface">Settings</h1>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">
          These preferences change how WeatherGPT frames answers — never the underlying data.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
      <div className="lg:col-span-7 flex flex-col gap-space-lg">

      <SectionCard title="Account" icon="account_circle">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-primary-container flex items-center justify-center text-on-primary font-label-md font-semibold">
              RS
            </div>
            <div>
              <div className="font-body-sm text-body-sm text-on-surface-variant">Signed in with Google</div>
            </div>
          </div>
          <button
            type="button"
            className="px-4 py-2 rounded-full border border-outline-variant text-on-surface-variant font-label-md text-label-md hover:bg-surface-container-high transition-colors"
          >
            Sign out
          </button>
        </div>
      </SectionCard>

      <SectionCard title="Language" icon="translate">
        <p className="font-body-sm text-body-sm text-on-surface-variant -mt-2">
          All five languages, fully text-ready today — voice support is on the way!
        </p>
        <div className="flex flex-wrap gap-2">
          {LANG_OPTIONS.map((opt) => (
            <button
              key={opt.code}
              type="button"
              onClick={() => setLang(opt.code)}
              className={`px-4 py-2 rounded-full font-label-md text-label-md transition-colors ${
                lang === opt.code
                  ? 'bg-primary text-on-primary font-semibold shadow-sm'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Units" icon="straighten">
        <div className="flex items-center bg-surface-container-low p-1 rounded-full w-fit font-label-md text-label-md text-on-surface-variant">
          <button
            type="button"
            onClick={() => setUnit('C')}
            className={`px-4 py-1.5 rounded-full transition-colors ${
              unit === 'C' ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold' : 'hover:text-on-surface'
            }`}
          >
            Celsius (°C)
          </button>
          <button
            type="button"
            onClick={() => setUnit('F')}
            className={`px-4 py-1.5 rounded-full transition-colors ${
              unit === 'F' ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold' : 'hover:text-on-surface'
            }`}
          >
            Fahrenheit (°F)
          </button>
        </div>
      </SectionCard>

      </div>
      <div className="lg:col-span-5 flex flex-col gap-space-lg">

      <SectionCard title="Persona" icon="tune">
        <p className="font-body-sm text-body-sm text-on-surface-variant -mt-2">
          Same trusted numbers, framed the way that's most useful for your role.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PERSONAS.map((p, i) => (
            <label
              key={p.id}
              className="flex items-start gap-3 p-3 rounded-lg border border-outline-variant has-[:checked]:border-primary has-[:checked]:bg-surface-container-low cursor-pointer transition-colors"
            >
              <input type="radio" name="persona" defaultChecked={i === 0} className="mt-1" />
              <span className="material-symbols-outlined text-on-surface-variant text-[20px]">{p.icon}</span>
              <span className="flex flex-col">
                <span className="font-label-md text-label-md text-on-surface font-semibold">{p.label}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{p.blurb}</span>
              </span>
            </label>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Notifications" icon="notifications">
        <label className="flex items-center justify-between">
          <span className="font-label-md text-label-md text-on-surface">Proactive alert pushes</span>
          <input type="checkbox" defaultChecked className="w-5 h-5 accent-primary" />
        </label>
        <label className="flex items-center justify-between">
          <span className="font-label-md text-label-md text-on-surface">Daily forecast digest</span>
          <input type="checkbox" className="w-5 h-5 accent-primary" />
        </label>
      </SectionCard>

      </div>
      </div>
    </div>
  );
}
