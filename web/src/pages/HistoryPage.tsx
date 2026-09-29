// Query history: the signed-in user's past /ask questions with the answers
// shown for them, from GET /history (lib/history.ts). Chat sends the user's
// token with every question, so signed-in questions are recorded server-side;
// a guest has no history and is invited to sign in. Filter chips group by
// intent, search matches the question, answer and city, "Ask again" re-asks
// in Chat, and "Clear history" erases everything (DELETE /history).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GradientButton, OutlineButton } from '../components/forms';
import PageFrame from '../components/PageFrame';
import {
  ActionRow,
  AppCard,
  ErrorPanel,
  Icon,
  IconDisc,
  LoadingPanel,
  PageHeader,
  PillButton,
  SectionTitle,
  Sheet,
  TagChip,
} from '../components/ui';
import { CITIES } from '../data/cities';
import { istDayMonth, istTime } from '../lib/format';
import { clearHistory, fetchHistory, HistoryError, matchesFilter, type HistoryFilter, type HistoryRow } from '../lib/history';
import { useAuth } from '../state/AuthContext';
import { useChat } from '../state/ChatContext';

const FILTERS: { id: HistoryFilter; label: string }[] = [
  { id: 'all', label: 'All queries' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'rain', label: 'Rain' },
];

const cityName = (key: string | null) => CITIES.find((c) => c.key === key)?.name ?? key ?? '';

function HistoryCard({ row, onAskAgain }: { row: HistoryRow; onAskAgain: (q: string) => void }) {
  const when = `${istDayMonth(row.created_at)}, ${istTime(row.created_at)}`;
  return (
    <AppCard pad="p-space-lg">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {row.city && <TagChip icon="location_on">{cityName(row.city)}</TagChip>}
          {row.intent && <TagChip tone="primary">{row.intent.replace(/_/g, ' ').toUpperCase()}</TagChip>}
          {row.lang && row.lang !== 'en' && <TagChip>{row.lang.toUpperCase()}</TagChip>}
        </div>
        <span className="shrink-0 font-citation-mono text-citation-mono text-outline">{when}</span>
      </div>
      <h2 className="mt-space-sm font-headline-sm text-headline-sm text-ink leading-snug break-words">“{row.query}”</h2>
      <div className="mt-space-sm p-space-md rounded-xl bg-tint">
        {row.response ? (
          <p className="font-body-md text-body-md text-ink">{row.response}</p>
        ) : (
          <p className="font-body-md text-body-md text-ink-muted">No answer was recorded for this question.</p>
        )}
      </div>
      <div className="mt-space-md">
        <PillButton icon="refresh" label="Ask again" onClick={() => onAskAgain(row.query)} />
      </div>
    </AppCard>
  );
}

function GuestHistory() {
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="Query history" subtitle="Past weather questions and the answers returned for them." />
      <div className="mt-space-lg flex flex-col gap-space-sm">
        <ActionRow icon="history" title="Your questions are saved to your account" trailing={null} />
        <ActionRow icon="devices" title="The same history on any device you sign in on" trailing={null} />
      </div>
      <div className="mt-space-xl flex flex-col gap-3">
        <GradientButton label="Sign in to see your history" onClick={() => navigate('/signin')} />
        <OutlineButton label="Create account" onClick={() => navigate('/signup')} />
      </div>
    </>
  );
}

function SignedInHistory() {
  const { getAccessToken, signOut } = useAuth();
  const { askInChat } = useChat();
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [error, setError] = useState<HistoryError | null>(null);
  const [filter, setFilter] = useState<HistoryFilter>('all');
  const [search, setSearch] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setError(null);
    try {
      const token = await getAccessToken();
      if (!token) throw new HistoryError('auth', 'Your session has expired. Sign in again to see your history.');
      setRows(await fetchHistory(token));
    } catch (err) {
      setError(err instanceof HistoryError ? err : new HistoryError('network', 'Something went wrong loading your history.'));
    }
  }, [getAccessToken]);

  // Load once on open. `load` changes when the session refreshes, which must
  // not reload the list, so it is deliberately not a dependency.
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clear = async () => {
    setClearing(true);
    setClearError(null);
    try {
      const token = await getAccessToken();
      if (!token) throw new HistoryError('auth', 'Your session has expired. Sign in again to clear your history.');
      await clearHistory(token);
      setRows([]);
      setConfirming(false);
    } catch (err) {
      setClearError(err instanceof HistoryError ? err.message : 'Something went wrong clearing your history.');
    } finally {
      setClearing(false);
    }
  };

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (rows ?? []).filter(
      (r) =>
        matchesFilter(r, filter) &&
        (!q || `${r.query} ${r.response ?? ''} ${cityName(r.city)}`.toLowerCase().includes(q)),
    );
  }, [rows, filter, search]);

  let body;
  if (error) {
    body = (
      <div className="flex flex-col gap-space-sm">
        <ErrorPanel
          icon={error.kind === 'auth' ? 'lock' : 'cloud_off'}
          title={error.kind === 'auth' ? 'Sign in again' : 'History unavailable'}
          message={error.message}
          onRetry={error.kind === 'auth' ? undefined : load}
        />
        {error.kind === 'auth' && <OutlineButton label="Sign out and sign in again" icon="logout" onClick={() => void signOut()} />}
      </div>
    );
  } else if (rows === null) {
    body = <LoadingPanel text="Loading your history…" />;
  } else if (rows.length === 0) {
    body = (
      <ActionRow
        leading={<IconDisc icon="chat" solid />}
        title="No questions yet"
        subtitle="Ask something in Chat and it will show up here."
        onClick={() => askInChat('What is the weather like today?')}
      />
    );
  } else {
    body = (
      <>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-space-sm">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0" role="group" aria-label="Filter">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={filter === f.id}
                onClick={() => setFilter(f.id)}
                className={`px-3 py-1.5 rounded-full whitespace-nowrap font-label-md text-label-md font-semibold transition-colors ${
                  filter === f.id ? 'bg-primary text-on-primary' : 'bg-tint text-primary hover:bg-tint-strong'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <label className="relative w-full md:w-72 shrink-0">
            <span className="sr-only">Search history</span>
            <Icon name="search" size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search questions, answers, cities"
              className="w-full pl-10 pr-3 py-2.5 rounded-card bg-card border border-card-border font-body-md text-body-md text-ink placeholder:text-outline outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </label>
        </div>
        <div className="mt-space-md mb-space-sm">
          <SectionTitle text={`${shown.length} ${shown.length === 1 ? 'question' : 'questions'}`} />
        </div>
        {shown.length === 0 ? (
          <p className="font-body-md text-body-md text-ink-muted">Nothing matches that filter.</p>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-space-md">
            {shown.map((r) => (
              <HistoryCard key={r.id} row={r} onAskAgain={askInChat} />
            ))}
          </div>
        )}
        <div className="mt-space-xl max-w-sm">
          <OutlineButton label="Clear history" icon="delete_sweep" destructive onClick={() => setConfirming(true)} />
        </div>
        <Sheet open={confirming} onClose={() => !clearing && setConfirming(false)} title="Clear your history?">
          <p className="font-body-md text-body-md text-ink-muted">
            This permanently erases every saved question and answer from your account. It can't be undone.
          </p>
          {clearError && (
            <p role="alert" className="mt-space-sm font-body-md text-body-md text-error">
              {clearError}
            </p>
          )}
          <div className="mt-space-lg flex justify-end gap-2">
            <button
              type="button"
              disabled={clearing}
              onClick={() => setConfirming(false)}
              className="px-4 py-2 rounded-full font-label-md text-label-md font-semibold text-primary hover:bg-tint disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={clearing}
              onClick={() => void clear()}
              className="px-4 py-2 rounded-full font-label-md text-label-md font-semibold text-error hover:bg-error-container disabled:opacity-60"
            >
              {clearing ? 'Clearing…' : 'Clear history'}
            </button>
          </div>
        </Sheet>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Query history" subtitle="Past weather questions and the answers returned for them." />
      <div className="mt-space-lg">{body}</div>
    </>
  );
}

export default function HistoryPage() {
  const { isGuest, user } = useAuth();
  return <PageFrame showCityPill={false}>{isGuest || !user ? <GuestHistory /> : <SignedInHistory />}</PageFrame>;
}
