// Live /facts for the selected city, shared by Home and Forecast so switching
// between them doesn't refetch (mobile/lib/state/weather_store.dart).
// Reloads whenever the city or language changes (condition labels come back
// localized). The day list and hourly series (/forecast/daily,
// /forecast/hourly) load beside it, each with its own error: a backend
// without those routes (404) still serves Home and the /facts rows.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import {
  FactsError,
  fetchDailyForecast,
  fetchFacts,
  fetchHourlyForecast,
  type FactsResult,
  type ForecastSeries,
} from '../lib/facts';
import { useUiPrefs } from './UiPrefsContext';

interface WeatherState {
  loading: boolean;
  /** Current conditions failed; the forecast periods are left empty too. */
  error: FactsError | null;
  /** current_weather/today — the Home now card. */
  current: FactsResult | null;
  /** Forecast entries: will_it_rain/today, current_weather/tonight, /tomorrow. */
  today: FactsResult | null;
  tonight: FactsResult | null;
  tomorrow: FactsResult | null;
  /** GET /forecast/daily and /forecast/hourly, null until they answer. */
  daily: ForecastSeries | null;
  hourly: ForecastSeries | null;
  dailyError: FactsError | null;
  hourlyError: FactsError | null;
}

interface WeatherCtx extends WeatherState {
  /** The day list has days to show (else the /facts rows stand in). */
  hasDaily: boolean;
  hasHourly: boolean;
  /** Still waiting on /forecast/daily. */
  dailyPending: boolean;
  hourlyPending: boolean;
  refresh: () => void;
}

const EMPTY: WeatherState = {
  loading: false,
  error: null,
  current: null,
  today: null,
  tonight: null,
  tomorrow: null,
  daily: null,
  hourly: null,
  dailyError: null,
  hourlyError: null,
};

const asFactsError = (err: unknown) =>
  err instanceof FactsError ? err : new FactsError('network', 'Something went wrong talking to the weather service.');

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
    setState((prev) => ({
      ...(cityChanged ? EMPTY : prev),
      loading: true,
      error: null,
      dailyError: null,
      hourlyError: null,
    }));
    const update = (patch: Partial<WeatherState>) => {
      if (id === requestId.current) setState((prev) => ({ ...prev, ...patch }));
    };

    // Each /facts reply on its own: only current conditions failing is an
    // error for the page; a forecast period that fails is just left empty.
    const facts = async () => {
      let failure: FactsError | null = null;
      const fetch = (intent = 'current_weather', day = 'today') =>
        fetchFacts({ city, lang, intent, day }).catch((err: unknown) => {
          if (intent === 'current_weather' && day === 'today') failure = asFactsError(err);
          return null;
        });
      const [current, today, tonight, tomorrow] = await Promise.all([
        fetch(),
        fetch('will_it_rain'),
        fetch('current_weather', 'tonight'),
        fetch('current_weather', 'tomorrow'),
      ]);
      update(
        failure
          ? { loading: false, error: failure, current: null, today: null, tonight: null, tomorrow: null }
          : { loading: false, error: null, current, today, tonight, tomorrow },
      );
    };
    const daily = fetchDailyForecast({ city, lang }).then(
      (daily) => update({ daily, dailyError: null }),
      (err: unknown) => update({ daily: null, dailyError: asFactsError(err) }),
    );
    const hourly = fetchHourlyForecast({ city, lang }).then(
      (hourly) => update({ hourly, hourlyError: null }),
      (err: unknown) => update({ hourly: null, hourlyError: asFactsError(err) }),
    );
    await Promise.all([facts(), daily, hourly]);
  }, []);

  useEffect(() => {
    void load(city, lang);
  }, [city, lang, load]);

  const refresh = useCallback(() => void load(city, lang), [city, lang, load]);

  const value: WeatherCtx = {
    ...state,
    hasDaily: (state.daily?.entries.length ?? 0) > 0,
    hasHourly: (state.hourly?.entries.length ?? 0) > 0,
    dailyPending: state.daily === null && state.dailyError === null,
    hourlyPending: state.hourly === null && state.hourlyError === null,
    refresh,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWeather() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWeather must be used inside WeatherProvider');
  return ctx;
}
