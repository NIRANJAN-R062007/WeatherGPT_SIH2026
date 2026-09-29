// Live /facts for the selected city, shared by Home and Forecast so switching
// between them doesn't refetch (mobile/lib/state/weather_store.dart).
// Reloads whenever the city or language changes (condition labels come back
// localized).
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { FactsError, fetchFacts, type FactsResult } from '../lib/facts';
import { useUiPrefs } from './UiPrefsContext';

interface WeatherState {
  loading: boolean;
  error: FactsError | null;
  /** current_weather/today — the Home now card. */
  current: FactsResult | null;
  /** Forecast entries: will_it_rain/today, current_weather/tonight, /tomorrow. */
  today: FactsResult | null;
  tonight: FactsResult | null;
  tomorrow: FactsResult | null;
}

interface WeatherCtx extends WeatherState {
  refresh: () => void;
}

const EMPTY: WeatherState = { loading: false, error: null, current: null, today: null, tonight: null, tomorrow: null };

const Ctx = createContext<WeatherCtx | null>(null);

export function WeatherProvider({ children }: { children: ReactNode }) {
  const { city, lang } = useUiPrefs();
  const [state, setState] = useState<WeatherState>(EMPTY);
  // Bumped on every load; a reply whose id no longer matches is stale (a
  // fast city switch), same as lib/useAsk.ts.
  const requestId = useRef(0);
  const lastCity = useRef<string | null>(null);

  const load = useCallback(async (city: string, lang: string) => {
    const id = ++requestId.current;
    const cityChanged = city !== lastCity.current;
    lastCity.current = city;
    // Never show the previous city's numbers under the new city's name.
    setState((prev) => ({ ...(cityChanged ? EMPTY : prev), loading: true, error: null }));
    try {
      const [current, today, tonight, tomorrow] = await Promise.all([
        fetchFacts({ city, lang }),
        fetchFacts({ city, lang, intent: 'will_it_rain', day: 'today' }),
        fetchFacts({ city, lang, day: 'tonight' }),
        fetchFacts({ city, lang, day: 'tomorrow' }),
      ]);
      if (id !== requestId.current) return;
      setState({ loading: false, error: null, current, today, tonight, tomorrow });
    } catch (err) {
      if (id !== requestId.current) return;
      const error =
        err instanceof FactsError
          ? err
          : new FactsError('network', 'Something went wrong talking to the weather service.');
      setState({ ...EMPTY, error });
    }
  }, []);

  useEffect(() => {
    void load(city, lang);
  }, [city, lang, load]);

  const refresh = useCallback(() => void load(city, lang), [city, lang, load]);

  return <Ctx.Provider value={{ ...state, refresh }}>{children}</Ctx.Provider>;
}

export function useWeather() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWeather must be used inside WeatherProvider');
  return ctx;
}
