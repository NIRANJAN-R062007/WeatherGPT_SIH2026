import { useCallback, useState } from 'react';

function readValue<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

/**
 * Wraps localStorage read/write in try/catch — private browsing, blocked
 * site data, and old Safari can all throw on access. Falls back to a plain
 * in-memory value when storage isn't available.
 */
export function useLocalStorage<T>(key: string, fallback: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => readValue(key, fallback));

  const set = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // In-memory only for this session — acceptable for a preference.
      }
    },
    [key],
  );

  return [value, set];
}
