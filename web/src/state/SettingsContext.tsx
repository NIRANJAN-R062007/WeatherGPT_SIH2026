import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react';
import type { Lang } from '../api/types';
import { useLocalStorage } from '../hooks/useLocalStorage';

const LANG_KEY = 'weathergpt.lang';
const CITY_KEY = 'weathergpt.city';
const VALID_LANGS: Lang[] = ['en', 'ta', 'hi', 'te', 'mr'];

interface SettingsValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  defaultCity: string;
  setDefaultCity: (city: string) => void;
}

const SettingsContext = createContext<SettingsValue | null>(null);

function validateLang(value: Lang): Lang {
  return VALID_LANGS.includes(value) ? value : 'en';
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [rawLang, setRawLang] = useLocalStorage<Lang>(LANG_KEY, 'en');
  const [defaultCity, setDefaultCity] = useLocalStorage<string>(CITY_KEY, 'chennai');
  const lang = validateLang(rawLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<SettingsValue>(
    () => ({ lang, setLang: setRawLang, defaultCity, setDefaultCity }),
    [lang, setRawLang, defaultCity, setDefaultCity],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
