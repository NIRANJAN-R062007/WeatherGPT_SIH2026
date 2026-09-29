// The Chat & Evidence transcript, kept above the routes so it survives
// switching pages (mobile keeps Chat alive in its IndexedStack), and the
// hand-off other pages use to ask a question in Chat: `askInChat(q)` asks it
// and opens /chat. Session-only: nothing here is persisted.
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AskError, askWeather, classifyAsk, type AskOutcome } from '../lib/api';
import { useAuth } from './AuthContext';
import { useUiPrefs } from './UiPrefsContext';

export interface ChatTurn {
  id: number;
  question: string;
  lang: string;
  /** "13:49 IST". */
  askedAt: string;
  outcome: AskOutcome | null;
  error: AskError | null;
}

interface ChatCtx {
  turns: ChatTurn[];
  loading: boolean;
  ask: (text: string) => void;
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

export function ChatProvider({ children }: { children: ReactNode }) {
  const { lang, city, persona } = useUiPrefs();
  const { getAccessToken } = useAuth();
  const navigate = useNavigate();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const busy = useRef(false);
  const nextId = useRef(1);

  const ask = useCallback(
    async (text: string) => {
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
        outcome = classifyAsk(await askWeather({ text: question, lang, city, persona, token }));
      } catch (err) {
        error = err instanceof AskError ? err : new AskError('network', 'Something went wrong talking to the weather service.');
      }
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, outcome, error } : t)));
      busy.current = false;
      setLoading(false);
    },
    [lang, city, persona, getAccessToken],
  );

  const askInChat = useCallback(
    (text: string) => {
      navigate('/chat');
      void ask(text);
    },
    [ask, navigate],
  );

  const value = useMemo(() => ({ turns, loading, ask: (t: string) => void ask(t), askInChat }), [turns, loading, ask, askInChat]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChat() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useChat must be used inside ChatProvider');
  return ctx;
}
