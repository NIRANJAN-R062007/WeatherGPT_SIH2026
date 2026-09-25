import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

export type LangCode = 'en' | 'hi' | 'ta' | 'te' | 'mr';
export type Unit = 'C' | 'F';

const LANG_LABELS: Record<LangCode, string> = {
  en: 'EN',
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
}

const UiPrefsCtx = createContext<UiPrefs | null>(null);

// Visual-only for now (plan.md's real language switch narrates from
// data/i18n/ + Bhashini on the backend) — this just tracks which pill is
// selected and converts the mock temperatures shown in the UI.
export function UiPrefsProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<LangCode>('en');
  const [unit, setUnit] = useState<Unit>('C');

  const value = useMemo<UiPrefs>(
    () => ({
      lang,
      setLang,
      unit,
      setUnit,
      toCelsiusLabel: (celsius: number) =>
        unit === 'C' ? `${Math.round(celsius)}°C` : `${Math.round((celsius * 9) / 5 + 32)}°F`,
    }),
    [lang, unit],
  );

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
