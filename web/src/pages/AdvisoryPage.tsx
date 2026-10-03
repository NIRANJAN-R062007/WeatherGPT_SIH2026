// Travel advice and Sowing advice (plan.md TFA-13; mobile advisory_page.dart),
// opened from the sidebar: a short conversation with POST /advisory/travel
// or /advisory/sowing (lib/advisory.ts). The backend asks for what it still
// needs (where from, where to, which day; which crop, which district), one
// question at a time, then answers with a verdict and the reasons behind it,
// all from weather data; the page shows the verdict as a coloured badge, the
// reasons for and against, any best time window, the sources, and the
// backend's disclaimer. The reasons come in English only, and the page says
// so.
import { useRef, useState, type FormEvent } from 'react';
import PageFrame from '../components/PageFrame';
import {
  ActionRow,
  AppCard,
  ErrorPanel,
  Icon,
  IconDisc,
  LiveBadge,
  LoadingPanel,
  PageHeader,
  PillButton,
  SectionTitle,
  Spinner,
  TagChip,
} from '../components/ui';
import { fetchAdvisory, slotLabels, type AdvisoryKind, type AdvisoryReply } from '../lib/advisory';
import { FactsError } from '../lib/facts';
import { COLOUR_HEX } from '../lib/warningUi';
import { useT } from '../lib/i18n';
import { useUiPrefs } from '../state/UiPrefsContext';

/** What each advisory says about itself, as ui_strings.json keys. */
const ABOUT: Record<AdvisoryKind, { title: string; lead: string; examples: string[]; icon: string }> = {
  travel: {
    title: 'Travel advice',
    lead: 'Ask whether the weather suits a trip: where from, where to, which day, and how you are going.',
    examples: ['Chennai to Madurai tomorrow by train', 'Can I drive from Bengaluru to Mumbai today?'],
    icon: 'route',
  },
  sowing: {
    title: 'Sowing advice',
    lead: 'Ask whether the weather suits sowing a crop in your district.',
    examples: ['When should I sow groundnut in Madurai?', 'Paddy in Coimbatore'],
    icon: 'agriculture',
  },
};

/** The verdict as a label, a tone and an icon. */
const VERDICT: Record<string, [string, string, string]> = {
  go: ['Go', COLOUR_HEX.green, 'check_circle'],
  suitable: ['Suitable', COLOUR_HEX.green, 'check_circle'],
  caution: ['Go with caution', COLOUR_HEX.orange, 'warning'],
  avoid: ['Avoid', COLOUR_HEX.red, 'block'],
  not_suitable: ['Not suitable', COLOUR_HEX.red, 'block'],
};

const FRESH = { slots: {}, asking: null };

interface Turn {
  id: number;
  text: string;
  reply: AdvisoryReply | null;
  error: FactsError | null;
}

/** The verdict, its reasons, the window and where it all came from. */
function Answer({ reply }: { reply: AdvisoryReply }) {
  const t = useT();
  const { lang } = useUiPrefs();
  const [label, tone, icon] = VERDICT[reply.verdict ?? ''] ?? [
    'Not available',
    'rgb(var(--c-on-surface-variant))',
    'help',
  ];
  const reasons = (glyph: string, color: string, lines: string[]) =>
    lines.map((line) => (
      <li key={line} className="flex items-start gap-1.5 font-body-md text-body-md text-on-surface">
        <Icon name={glyph} size={16} className="mt-1" style={{ color }} />
        <span>{line}</span>
      </li>
    ));
  return (
    <AppCard>
      <div className="flex items-center gap-3">
        <IconDisc icon={icon} color={tone} solid size={36} />
        {/* Ink, not the tone: the badge carries the colour, the text stays readable. */}
        <span className="font-headline-sm text-headline-sm font-bold text-ink">{t(label)}</span>
      </div>
      {Object.keys(reply.slots).length > 0 && (
        <div className="mt-space-sm flex flex-wrap gap-1.5">
          {slotLabels(t, reply.slots).map((s) => (
            <TagChip key={s}>{s}</TagChip>
          ))}
        </div>
      )}
      {(reply.pros.length > 0 || reply.cons.length > 0) && (
        <ul className="mt-1.5 flex flex-col gap-1.5">
          {reasons('add_circle', COLOUR_HEX.green, reply.pros)}
          {reasons('do_not_disturb_on', 'rgb(var(--c-error))', reply.cons)}
        </ul>
      )}
      {reply.window && (
        <p className="mt-space-sm font-label-md text-label-md font-semibold text-ink">
          {t('Best window: {start}–{end}', { start: reply.window.start, end: reply.window.end })}
        </p>
      )}
      {lang !== 'en' && (
        <p className="mt-space-sm font-body-sm text-body-sm text-ink-muted">{t('The reasons are shown in English.')}</p>
      )}
      {reply.sources.length > 0 && (
        <div className="mt-space-sm flex items-center gap-space-sm">
          <LiveBadge live={reply.allLive} />
          <span className="font-body-sm text-body-sm text-ink-muted">{reply.sources.join(' · ')}</span>
        </div>
      )}
      {reply.disclaimer && <p className="mt-space-sm font-body-sm text-body-sm text-ink-muted">{t(reply.disclaimer)}</p>}
    </AppCard>
  );
}

function Reply({ turn }: { turn: Turn }) {
  if (turn.error) {
    return (
      <ErrorPanel icon="wifi_off" title="Advice unavailable" message={turn.error.message} messageArgs={turn.error.args} />
    );
  }
  if (!turn.reply) return <LoadingPanel text="Checking the weather for your plan…" />;
  if (turn.reply.status !== 'ok') {
    return (
      <AppCard>
        <div className="flex items-start gap-3">
          <IconDisc icon="help" size={32} />
          <p className="font-body-md text-body-md text-ink" role="status">
            {turn.reply.question}
          </p>
        </div>
      </AppCard>
    );
  }
  return <Answer reply={turn.reply} />;
}

/** Mounted with `key={kind}` (App.tsx), so Travel and Sowing each start
 *  their own conversation. */
export default function AdvisoryPage({ kind }: { kind: AdvisoryKind }) {
  const t = useT();
  const { lang } = useUiPrefs();
  const about = ABOUT[kind];
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  // Carried from the last reply into the next turn.
  const [carried, setCarried] = useState<{ slots: Record<string, string>; asking: string | null }>(FRESH);
  const nextId = useRef(1);

  const send = async (raw: string) => {
    const question = raw.trim();
    if (!question || busy) return;
    const id = nextId.current++;
    setTurns((prev) => [...prev, { id, text: question, reply: null, error: null }]);
    setText('');
    setBusy(true);
    let reply: AdvisoryReply | null = null;
    let error: FactsError | null = null;
    try {
      reply = await fetchAdvisory(kind, { text: question, lang, ...carried });
      setCarried({ slots: reply.slots, asking: reply.status === 'ok' ? null : reply.asking });
    } catch (err) {
      error = err instanceof FactsError ? err : new FactsError('network', 'Something went wrong talking to the weather service.');
    }
    setTurns((prev) => prev.map((turn) => (turn.id === id ? { ...turn, reply, error } : turn)));
    setBusy(false);
  };

  const startOver = () => {
    if (busy) return;
    setTurns([]);
    setCarried(FRESH);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };

  return (
    <PageFrame>
      <PageHeader title={about.title} subtitle={about.lead} />
      <div className="mt-space-md flex flex-col gap-space-sm">
        {turns.length === 0 ? (
          <>
            <SectionTitle text="Try asking" />
            {about.examples.map((example) => (
              <ActionRow key={example} icon={about.icon} title={example} onClick={() => void send(t(example))} />
            ))}
          </>
        ) : (
          <>
            {turns.map((turn) => (
              <div key={turn.id} className="flex flex-col gap-space-sm" aria-live="polite">
                <div className="ml-12 self-end px-space-md py-3 rounded-2xl bg-accent-gradient text-on-primary font-body-md text-body-md">
                  {turn.text}
                </div>
                <Reply turn={turn} />
              </div>
            ))}
            <div>
              <PillButton icon="restart_alt" label="Start over" onClick={startOver} />
            </div>
          </>
        )}
      </div>
      <form
        onSubmit={onSubmit}
        className="mt-space-md flex items-center gap-2 pl-3 pr-1 py-1 rounded-card border border-card-border bg-card shadow-card"
      >
        <input
          className="flex-1 min-w-0 min-h-12 bg-transparent border-0 outline-none font-body-md text-body-md text-ink placeholder:text-outline"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t(carried.asking ? 'Your answer…' : 'Ask a question…')}
          aria-label={t(carried.asking ? 'Your answer…' : 'Ask a question…')}
        />
        <button
          type="submit"
          disabled={busy || text.trim() === ''}
          aria-label={t('Send')}
          title={t('Send')}
          className="shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-primary hover:bg-tint disabled:opacity-60"
        >
          {busy ? <Spinner className="w-5 h-5 border-outline-variant border-t-primary" /> : <Icon name="send" size={22} fill />}
        </button>
      </form>
    </PageFrame>
  );
}
