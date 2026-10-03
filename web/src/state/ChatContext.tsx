// The Chat & Evidence transcript, kept above the routes so it survives
// switching pages (mobile keeps Chat alive in its IndexedStack), and the
// hand-off other pages use to ask a question in Chat: `askInChat(q)` asks it
// and opens /chat. Session-only: nothing here is persisted — the GPS fix
// included, which lives in memory only and is rounded to 2 decimals (~1 km)
// before it leaves the browser.
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AskError, askWeather, classifyAsk, type AskOutcome } from '../lib/api';
import { useAuth } from './AuthContext';
import { useUiPrefs } from './UiPrefsContext';
import { useT } from '../lib/i18n';

export interface ChatTurn {
  id: number;
  question: string;
  lang: string;
  /** "13:49 IST". */
  askedAt: string;
  outcome: AskOutcome | null;
  error: AskError | null;
}

export type LocateState = 'off' | 'locating' | 'on';

/** Why "Use my location" didn't give a fix. Never followed by picking a
 *  city for the user: they type a place or choose one themselves. */
export type LocateError = 'denied' | 'unavailable' | 'unsupported';

interface ChatCtx {
  turns: ChatTurn[];
  loading: boolean;
  /** `placeId`: a candidate tapped from an `ambiguous` reply. */
  ask: (text: string, opts?: { placeId?: string }) => void;
  locate: LocateState;
  locateError: LocateError | null;
  /** Ask the browser for a fix; on success, ask `text` (or "What's the
   *  weather here?") with it. Later questions keep using it until stopped. */
  shareLocation: (text?: string) => void;
  stopUsingLocation: () => void;
  /** Ask from another page: switches to Chat, which shows the answer. */
  askInChat: (text: string) => void;
}

const Ctx = createContext<ChatCtx | null>(null);

function istTimeNow() {
  return `${new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date())} IST`;
}

/** A fix travels snapped to the 0.05° grid (~5 km), as on mobile: enough
 *  for the weather, not enough to place a home. */
function snapToGrid(degrees: number) {
  return Number((Math.round(degrees / 0.05) * 0.05).toFixed(2));
}

function currentFix(): Promise<{ lat: number; lon: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject('unsupported' satisfies LocateError);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: snapToGrid(pos.coords.latitude), lon: snapToGrid(pos.coords.longitude) }),
      (err) => reject((err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable') satisfies LocateError),
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 600_000 },
    );
  });
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const { lang, city, persona } = useUiPrefs();
  const t = useT();
  const { getAccessToken } = useAuth();
  const navigate = useNavigate();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const busy = useRef(false);
  const nextId = useRef(1);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locate, setLocate] = useState<LocateState>('off');
  const [locateError, setLocateError] = useState<LocateError | null>(null);

  const ask = useCallback(
    async (text: string, opts: { placeId?: string; coords?: { lat: number; lon: number } } = {}) => {
      const question = text.trim();
      if (!question || busy.current) return;
      busy.current = true;
      setLoading(true);
      const id = nextId.current++;
      setTurns((prev) => [
        ...prev,
        { id, question, lang, askedAt: istTimeNow(), outcome: null, error: null },
      ]);
      let outcome: AskOutcome | null = null;
      let error: AskError | null = null;
      try {
        // A signed-in user's token makes the backend record the question to
        // their history (best-effort); a guest has none and isn't recorded.
        const token = (await getAccessToken()) ?? undefined;
        outcome = classifyAsk(
          await askWeather({
            text: question,
            lang,
            city,
            persona,
            token,
            coords: opts.coords ?? coords ?? undefined,
            placeId: opts.placeId,
          }),
        );
      } catch (err) {
        error = err instanceof AskError ? err : new AskError('network', 'Something went wrong talking to the weather service.');
      }
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, outcome, error } : t)));
      busy.current = false;
      setLoading(false);
    },
    [lang, city, persona, getAccessToken, coords],
  );

  const shareLocation = useCallback(
    async (text?: string) => {
      if (locate === 'locating') return;
      setLocate('locating');
      setLocateError(null);
      try {
        const fix = await currentFix();
        setCoords(fix);
        setLocate('on');
        void ask(text?.trim() || t("What's the weather here?"), { coords: fix });
      } catch (err) {
        setCoords(null);
        setLocate('off');
        setLocateError(err === 'denied' || err === 'unsupported' ? err : 'unavailable');
      }
    },
    [ask, locate, t],
  );

  const stopUsingLocation = useCallback(() => {
    setCoords(null);
    setLocate('off');
    setLocateError(null);
  }, []);

  const askInChat = useCallback(
    (text: string) => {
      navigate('/chat');
      void ask(text);
    },
    [ask, navigate],
  );

  const value = useMemo(
    () => ({
      turns,
      loading,
      ask: (q: string, opts?: { placeId?: string }) => void ask(q, opts),
      askInChat,
      locate,
      locateError,
      shareLocation: (q?: string) => void shareLocation(q),
      stopUsingLocation,
    }),
    [turns, loading, ask, askInChat, locate, locateError, shareLocation, stopUsingLocation],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChat() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useChat must be used inside ChatProvider');
  return ctx;
}
