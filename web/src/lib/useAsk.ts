import { useCallback, useRef, useState } from 'react';
import { AskError, askWeather, classifyAsk, type AskOutcome } from './api';

export interface AskState {
  /** The question the displayed result answers (not the live input value). */
  asked: string | null;
  loading: boolean;
  outcome: AskOutcome | null;
  error: AskError | null;
}

const IDLE: AskState = { asked: null, loading: false, outcome: null, error: null };

/** Shared /ask call state for a composer: one in-flight request at a time,
 *  late replies from a superseded request dropped. */
export function useAsk() {
  const [state, setState] = useState<AskState>(IDLE);
  // Bumped on every submit; a reply whose id no longer matches is stale.
  const requestId = useRef(0);

  const ask = useCallback(async (text: string, lang?: string, city?: string, token?: string) => {
    const question = text.trim();
    if (!question) return;

    const id = ++requestId.current;
    setState({ asked: question, loading: true, outcome: null, error: null });

    try {
      const data = await askWeather({ text: question, lang, city, token });
      if (requestId.current !== id) return;
      setState({ asked: question, loading: false, outcome: classifyAsk(data), error: null });
    } catch (err) {
      if (requestId.current !== id) return;
      const error =
        err instanceof AskError
          ? err
          : new AskError('network', 'Something went wrong talking to the weather service.');
      setState({ asked: question, loading: false, outcome: null, error });
    }
  }, []);

  const reset = useCallback(() => {
    requestId.current += 1;
    setState(IDLE);
  }, []);

  return { ...state, ask, reset };
}
