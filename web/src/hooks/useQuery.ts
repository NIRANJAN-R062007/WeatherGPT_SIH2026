import { useEffect, useRef, useState } from 'react';

type Status = 'loading' | 'ok' | 'error';

interface QueryState<T> {
  status: Status;
  data?: T;
  error?: unknown;
  reload: () => void;
}

/**
 * Small data-fetching hook: runs `fn` whenever `deps` changes, aborts the
 * in-flight request on the next change or unmount, and ignores results from
 * a request that's no longer the latest one (stale-response guard).
 */
export function useQuery<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[]): QueryState<T> {
  const [status, setStatus] = useState<Status>('loading');
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<unknown>(undefined);
  const requestId = useRef(0);

  const run = () => {
    const id = ++requestId.current;
    const controller = new AbortController();
    setStatus('loading');
    setError(undefined);

    fn(controller.signal)
      .then((result) => {
        if (requestId.current !== id) return;
        setData(result);
        setStatus('ok');
      })
      .catch((err) => {
        if (requestId.current !== id) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err);
        setStatus('error');
      });

    return controller;
  };

  useEffect(() => {
    const controller = run();
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { status, data, error, reload: run };
}
