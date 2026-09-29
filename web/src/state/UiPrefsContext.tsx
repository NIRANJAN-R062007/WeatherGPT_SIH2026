import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { CITIES, type City } from '../data/cities';
import { personaById, type Persona } from '../data/personas';
import { applyTheme, personaThemeFor, type PersonaTheme } from '../theme/personaTheme';

export type LangCode = 'en' | 'hi' | 'ta' | 'te' | 'mr';
export type Unit = 'C' | 'F';
/** Settings > Appearance. Every persona has a light and a dark palette. */
export type Appearance = 'light' | 'dark' | 'system';

const LANG_LABELS: Record<LangCode, string> = {
  en: 'EN',
  hi: 'हिन्दी',
  ta: 'தமிழ்',
  te: 'తెలుగు',
  mr: 'मराठी',
};

/** Settings' language picker names (mobile config.dart kLanguageLabels). */
export const LANG_NAMES: Record<LangCode, string> = {
  en: 'English',
  hi: 'हिन्दी',
  ta: 'தமிழ்',
  te: 'తెలుగు',
  mr: 'मराठी',
};

interface UiPrefs {
  lang: LangCode;
  setLang: (l: LangCode) => void;
  unit: Unit;
  setUnit: (u: Unit) => void;
  toCelsiusLabel: (celsius: number) => string;
  // Just the converted number, for callers that render their own °/unit
  // markup (e.g. a large hero digit next to a separately-styled unit letter).
  toCelsiusValue: (celsius: number) => number;
  // City key (data/cities.ts), shared so Topbar's picker and every page's
  // own /ask /warnings city hint stay in sync instead of drifting apart.
  city: string;
  setCity: (c: string) => void;
  cityInfo: City;
  /** persona.py id: /ask's `persona` param and the app-wide theme. */
  persona: string;
  setPersona: (id: string) => void;
  personaInfo: Persona;
  appearance: Appearance;
  setAppearance: (a: Appearance) => void;
  /** The active palette (persona × resolved light/dark). */
  theme: PersonaTheme;
  isDark: boolean;
}

const UiPrefsCtx = createContext<UiPrefs | null>(null);

// Persona and appearance survive a reload (a theme that resets on every
// refresh would flash the wrong colours); per-browser only, and the app
// works the same when storage is blocked.
const STORE_KEY = 'weathergpt.prefs';

function readStored(): { persona?: string; appearance?: Appearance } {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as { persona?: string; appearance?: Appearance }) : {};
  } catch {
    return {};
  }
}

function systemDark() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches === true;
}

// Language, unit and city are in-memory, as before. The persona picks the
// palette; Appearance picks its light or dark twin.
export function UiPrefsProvider({ children }: { children: ReactNode }) {
  const [stored] = useState(readStored);
  const [lang, setLang] = useState<LangCode>('en');
  const [unit, setUnit] = useState<Unit>('C');
  const [city, setCity] = useState('chennai');
  const [persona, setPersona] = useState(() => personaById(stored.persona ?? 'general').id);
  const [appearance, setAppearance] = useState<Appearance>(stored.appearance ?? 'light');
  const [prefersDark, setPrefersDark] = useState(systemDark);

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return;
    const onChange = () => setPrefersDark(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ persona, appearance }));
    } catch {
      // Not remembered — the defaults come back next visit.
    }
  }, [persona, appearance]);

  const isDark = appearance === 'dark' || (appearance === 'system' && prefersDark);
  const theme = personaThemeFor(persona, isDark ? 'dark' : 'light');

  // Before paint, so a page never shows one frame of the old palette; the
  // first install snaps, later changes cross-fade.
  const installed = useRef(false);
  useLayoutEffect(() => {
    applyTheme(theme, installed.current);
    installed.current = true;
  }, [theme]);

  const value = useMemo<UiPrefs>(() => {
    const toCelsiusValue = (celsius: number) =>
      unit === 'C' ? Math.round(celsius) : Math.round((celsius * 9) / 5 + 32);
    return {
      lang,
      setLang,
      unit,
      setUnit,
      toCelsiusLabel: (celsius: number) => `${toCelsiusValue(celsius)}°${unit}`,
      toCelsiusValue,
      city,
      setCity,
      cityInfo: CITIES.find((c) => c.key === city) ?? CITIES[0],
      persona,
      setPersona,
      personaInfo: personaById(persona),
      appearance,
      setAppearance,
      theme,
      isDark,
    };
  }, [lang, unit, city, persona, appearance, theme, isDark]);

  return <UiPrefsCtx.Provider value={value}>{children}</UiPrefsCtx.Provider>;
}

export function useUiPrefs() {
  const ctx = useContext(UiPrefsCtx);
  if (!ctx) throw new Error('useUiPrefs must be used inside UiPrefsProvider');
  return ctx;
}

export const LANG_OPTIONS: { code: LangCode; label: string }[] = (
  Object.keys(LANG_LABELS) as LangCode[]
).map((code) => ({ code, label: LANG_LABELS[code] }));
