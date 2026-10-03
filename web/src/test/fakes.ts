// Test doubles for the lib/ tests (Vitest, Node): an in-memory localStorage
// and a scripted fetch that records what it was asked.
import { vi } from 'vitest';

export function fakeLocalStorage() {
  const items = new Map<string, string>();
  const storage = {
    getItem: (k: string) => items.get(k) ?? null,
    setItem: (k: string, v: string) => void items.set(k, String(v)),
    removeItem: (k: string) => void items.delete(k),
    clear: () => items.clear(),
    key: (i: number) => [...items.keys()][i] ?? null,
    get length() {
      return items.size;
    },
  };
  vi.stubGlobal('localStorage', storage);
  return items;
}

export interface Sent {
  url: string;
  method: string;
  body: unknown;
}

/** Each call gets `reply(url)`: a JSON body (200), a status, or a thrown
 *  error (no connection). */
export function fakeFetch(reply: (url: string) => unknown | { status: number } | Error) {
  const sent: Sent[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      sent.push({ url, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const r = reply(url);
      if (r instanceof Error) throw r;
      if (r && typeof r === 'object' && 'status' in r && Object.keys(r).length === 1) {
        return new Response('{}', { status: (r as { status: number }).status });
      }
      return new Response(JSON.stringify(r), { status: 200 });
    }),
  );
  return sent;
}
