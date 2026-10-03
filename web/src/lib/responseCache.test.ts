import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeLocalStorage } from '../test/fakes';
import { fetchOrSaved, MAX_SAVED_AGE_MS, readSaved, replyKey, writeSaved } from './responseCache';

let items: Map<string, string>;
beforeEach(() => {
  items = fakeLocalStorage();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('responseCache', () => {
  it('keys a GET by path and its parameters in a fixed order', () => {
    expect(replyKey('/facts', { lang: 'en', city: 'chennai' })).toBe('/facts?city=chennai&lang=en');
  });

  it('a copy older than a week is not used', async () => {
    writeSaved('k', { a: 1 }, new Date(Date.now() - MAX_SAVED_AGE_MS - 60_000));
    await expect(fetchOrSaved('k', () => Promise.reject(new Error('down')), () => true)).rejects.toThrow('down');
  });

  it('a damaged entry or blocked storage reads as nothing saved', () => {
    items.set('weathergpt.saved:k', '{not json');
    expect(readSaved('k')).toBeNull();
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
    });
    expect(readSaved('k')).toBeNull();
    expect(() => writeSaved('k', {})).not.toThrow();
  });
});
