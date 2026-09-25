import type { ReactNode } from 'react';
import { CITIES } from '../data/cities';
import type {
  AskError,
  AskOutcome,
  Grounding,
  LegendRow,
  WarningColour,
  WeatherProvenance,
} from '../lib/api';

/** Resolved city keys come back lowercase ("chennai"); data/cities.ts already
 *  mirrors data/cities.json, so use its English display name and only fall
 *  back to capitalising the key for a city this bundle doesn't list yet. */
function cityLabel(key: string) {
  const match = CITIES.find((c) => c.key === key);
  if (match) return match.name;
  return key.charAt(0).toUpperCase() + key.slice(1);
}

/** router.legacy_day values -> a short human label. `next_<n>_days` is built
 *  by the backend, so it is parsed rather than enumerated. */
function dayLabel(day: string) {
  const span = /^next_(\d+)_days$/.exec(day);
  if (span) return `Next ${span[1]} days`;
  return day.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

function istTimestamp(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d)} IST`;
}

// Static class strings: Tailwind's scanner can't see template-built names.
const COLOUR_BAR: Record<WarningColour, string> = {
  green: 'bg-imd-green',
  yellow: 'bg-imd-yellow',
  orange: 'bg-imd-orange',
  red: 'bg-imd-red',
};

const COLOUR_TEXT: Record<WarningColour, string> = {
  green: 'text-imd-green',
  yellow: 'text-imd-yellow',
  orange: 'text-imd-orange',
  red: 'text-imd-red',
};

function Notice({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed font-body-sm text-body-sm">
      <span className="material-symbols-outlined text-[14px] shrink-0 mt-0.5">translate</span>
      <span>{text}</span>
    </div>
  );
}

function Chip({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'primary' }) {
  const cls =
    tone === 'primary'
      ? 'bg-surface-container-high text-primary'
      : 'bg-surface-container text-on-surface-variant';
  return (
    <span className={`px-2 py-0.5 rounded-full font-citation-mono text-[10px] font-medium ${cls}`}>
      {children}
    </span>
  );
}

function WeatherProvenanceFooter({ p, g }: { p: WeatherProvenance; g: Grounding }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-space-xs border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
      <span className="flex items-center gap-1">
        <span className="material-symbols-outlined text-[12px]">database</span>
        {p.source}
      </span>
      <span
        className={
          p.is_live
            ? 'px-1.5 py-0.5 rounded bg-secondary-container text-on-secondary-container font-semibold'
            : 'px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-semibold'
        }
      >
        {p.is_live ? 'LIVE' : 'NOT LIVE'}
      </span>
      {p.issued && <span>Issued {istTimestamp(p.issued)}</span>}
      <span>Retrieved {istTimestamp(p.retrieved_at)}</span>
      <span className="text-outline">
        {g.narration} · {g.provider}
        {g.attempts > 1 ? ` · ${g.attempts} attempts` : ''}
        {g.fallback_used ? ' · fell back to template' : ''}
      </span>
    </div>
  );
}

function FigureList({ figures }: { figures: Grounding['figures'] }) {
  if (figures.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {figures.map((f, i) => (
        <span
          key={`${f.reading}-${i}`}
          title={f.matched ? `matched ${f.path ?? ''}` : 'no matching value in the source data'}
          className={`flex items-center gap-1 px-2 py-0.5 rounded font-citation-mono text-citation-mono ${
            f.matched
              ? 'bg-secondary-container text-on-secondary-container'
              : 'bg-error-container text-on-error-container'
          }`}
        >
          <span className="material-symbols-outlined text-[12px]">
            {f.matched ? 'check_circle' : 'cancel'}
          </span>
          {f.reading}
        </span>
      ))}
    </div>
  );
}

function Legend({ rows, highlight }: { rows: LegendRow[]; highlight?: WarningColour }) {
  return (
    <div className="flex flex-col gap-1">
      {rows.map((row) => (
        <div
          key={row.colour}
          className={`flex items-start gap-2 px-2 py-1 rounded-lg font-body-sm text-body-sm ${
            row.colour === highlight
              ? 'bg-surface-container text-on-surface'
              : 'text-on-surface-variant'
          }`}
        >
          <span className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${COLOUR_BAR[row.colour]}`} />
          <span>
            <strong className="font-semibold">{row.label}</strong> — {row.meaning}
          </span>
        </div>
      ))}
    </div>
  );
}

const ERROR_ICON: Record<AskError['kind'], string> = {
  network: 'wifi_off',
  timeout: 'timer_off',
  http: 'error',
  malformed: 'report',
};

export interface AskAnswerProps {
  asked: string | null;
  loading: boolean;
  outcome: AskOutcome | null;
  error: AskError | null;
  /** Legend + per-figure detail are hidden by default on the compact panel. */
  detail?: boolean;
}

/** Renders one /ask result. Every branch main.py can return gets its own
 *  treatment — in particular a refusal carries `message`, not `response`, and
 *  an unavailable warning is never shown as an all-clear. */
export default function AskAnswer({ asked, loading, outcome, error, detail = false }: AskAnswerProps) {
  if (!loading && !outcome && !error) return null;

  return (
    <div className="flex flex-col gap-space-sm">
      {asked && (
        <div className="flex items-baseline gap-1.5 font-body-sm text-body-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-[14px] text-outline shrink-0">chat</span>
          <span className="italic">“{asked}”</span>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 p-space-md rounded-xl bg-surface-container-low font-body-md text-body-md text-on-surface-variant">
          <span className="w-4 h-4 rounded-full border-2 border-outline-variant border-t-primary animate-spin" />
          Grounding an answer against live weather data…
        </div>
      )}

      {error && (
        <div className="flex flex-col gap-1 p-space-md rounded-xl bg-error-container text-on-error-container">
          <div className="flex items-center gap-1.5 font-label-md text-label-md font-semibold">
            <span className="material-symbols-outlined text-[18px]">{ERROR_ICON[error.kind]}</span>
            {error.kind === 'http'
              ? `Weather service error${error.status ? ` (HTTP ${error.status})` : ''}`
              : error.kind === 'timeout'
                ? 'Request timed out'
                : error.kind === 'malformed'
                  ? 'Unreadable reply'
                  : 'Weather service unreachable'}
          </div>
          <p className="font-body-md text-body-md">{error.message}</p>
        </div>
      )}

      {outcome?.kind === 'success' && (
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-low">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-secondary-container text-on-secondary-container font-citation-mono text-[10px] font-bold"
              title={`${outcome.data.grounding.matched} of ${outcome.data.grounding.total} figures matched the source data`}
            >
              <span className="material-symbols-outlined text-[12px]">verified_user</span>
              GROUNDED {outcome.data.grounding.matched}/{outcome.data.grounding.total}
            </span>
            <Chip tone="primary">{outcome.data.intent.replace(/_/g, ' ').toUpperCase()}</Chip>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {cityLabel(outcome.data.city)}
            </Chip>
            <Chip>{dayLabel(outcome.data.day)}</Chip>
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          <p className="font-body-lg text-body-lg text-on-surface leading-relaxed">
            {outcome.data.response}
          </p>

          {detail && <FigureList figures={outcome.data.grounding.figures} />}
          <WeatherProvenanceFooter p={outcome.data.provenance} g={outcome.data.grounding} />
        </div>
      )}

      {outcome?.kind === 'warnings' && (
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-low">
          <div className={`h-1.5 rounded-full ${COLOUR_BAR[outcome.data.warning.colour]}`} />

          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`flex items-center gap-1 font-label-md text-label-md font-bold ${COLOUR_TEXT[outcome.data.warning.colour]}`}
            >
              <span className="material-symbols-outlined text-[18px]">
                {outcome.data.status === 'active' ? 'warning' : 'check_circle'}
              </span>
              {outcome.data.warning.colour_label}
              {outcome.data.status === 'active' ? ' — in force' : ' — nothing in force'}
            </span>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {outcome.data.warning.district}
            </Chip>
            <Chip tone="primary">{outcome.data.warning.category_label}</Chip>
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          {/* The feed's own headline, verbatim — not narrated, not translated. */}
          <p className="font-body-lg text-body-lg text-on-surface leading-relaxed">
            {outcome.data.response}
          </p>
          <p className="font-body-md text-body-md text-on-surface-variant">
            {outcome.data.warning.advice}
          </p>

          {detail && <Legend rows={outcome.data.legend} highlight={outcome.data.warning.colour} />}

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-space-xs border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[12px]">campaign</span>
              {outcome.data.provenance.issued_by}
            </span>
            <span
              className={
                outcome.data.provenance.is_live
                  ? 'px-1.5 py-0.5 rounded bg-secondary-container text-on-secondary-container font-semibold'
                  : 'px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-semibold'
              }
            >
              {outcome.data.provenance.is_live ? 'LIVE FEED' : 'FIXTURE'}
            </span>
            <span>
              Valid {istTimestamp(outcome.data.provenance.valid_from)} →{' '}
              {istTimestamp(outcome.data.provenance.valid_to)}
            </span>
            <span className="text-outline">verbatim · {outcome.data.grounding.provider}</span>
          </div>
        </div>
      )}

      {outcome?.kind === 'warnings-unavailable' && (
        /* Deliberately neutral, never green: no verdict is not an all-clear. */
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="flex items-center gap-1 font-label-md text-label-md font-bold text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">help</span>
              No warning verdict
            </span>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {cityLabel(outcome.data.city)}
            </Chip>
            <Chip>STATUS: {outcome.data.status.toUpperCase()}</Chip>
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          <p className="font-body-md text-body-md text-on-surface">{outcome.data.message}</p>

          {detail && <Legend rows={outcome.data.legend} />}
        </div>
      )}

      {outcome?.kind === 'ungrounded' && (
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-error-container">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="flex items-center gap-1 font-label-md text-label-md font-bold text-on-error-container">
              <span className="material-symbols-outlined text-[18px]">gpp_maybe</span>
              Answer withheld — not grounded
            </span>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {cityLabel(outcome.data.city)}
            </Chip>
            <Chip>
              {outcome.data.grounding.matched}/{outcome.data.grounding.total} figures matched
            </Chip>
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          <p className="font-body-md text-body-md text-on-error-container">
            {outcome.data.message}
          </p>

          <div className="p-2 rounded-lg bg-surface-container-lowest flex flex-col gap-2">
            <FigureList figures={outcome.data.grounding.figures} />
            <WeatherProvenanceFooter p={outcome.data.provenance} g={outcome.data.grounding} />
          </div>
        </div>
      )}

      {outcome?.kind === 'fallback' && (
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="flex items-center gap-1 font-label-md text-label-md font-bold text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">info</span>
              No answer
            </span>
            <Chip tone="primary">{outcome.data.intent.replace(/_/g, ' ').toUpperCase()}</Chip>
            {/* Only the no_data branch carries a resolved city key. */}
            {outcome.data.city && (
              <Chip>
                <span className="material-symbols-outlined text-[11px] align-middle">
                  location_on
                </span>{' '}
                {cityLabel(outcome.data.city)}
              </Chip>
            )}
            {/* On unsupported_city the rejected name survives only in nlu.city. */}
            {!outcome.data.city && outcome.data.nlu.city && (
              <Chip>asked about “{outcome.data.nlu.city}”</Chip>
            )}
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          <p className="font-body-md text-body-md text-on-surface">{outcome.data.message}</p>
        </div>
      )}
    </div>
  );
}
