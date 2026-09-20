import { createContext, useContext, useMemo, type ReactNode } from 'react';
import type { City } from '../api/types';
import { fetchCities } from '../api/client';
import { useQuery } from '../hooks/useQuery';

interface CitiesValue {
  status: 'loading' | 'ok' | 'error';
  cities: City[];
  error?: unknown;
  reload: () => void;
  byKey: (key: string) => City | undefined;
}

const CitiesContext = createContext<CitiesValue | null>(null);

export function CitiesProvider({ children }: { children: ReactNode }) {
  const { status, data, error, reload } = useQuery((signal) => fetchCities(signal), []);
  const cities = useMemo(() => data?.cities ?? [], [data]);

  const value = useMemo<CitiesValue>(
    () => ({
      status,
      cities,
      error,
      reload,
      byKey: (key: string) => cities.find((c) => c.key === key),
    }),
    [status, cities, error, reload],
  );

  return <CitiesContext.Provider value={value}>{children}</CitiesContext.Provider>;
}

export function useCities(): CitiesValue {
  const ctx = useContext(CitiesContext);
  if (!ctx) throw new Error('useCities must be used within CitiesProvider');
  return ctx;
}
