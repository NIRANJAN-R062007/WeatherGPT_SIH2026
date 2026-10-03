import type { ReactNode } from 'react';
import { cityLabel } from '../data/cities';
import type {
  AskError,
  AskOutcome,
  Grounding,
  LegendRow,
  WarningColour,
  WeatherProvenance,
} from '../lib/api';
import { COLOUR_BAR, COLOUR_TEXT, istTimestamp } from '../lib/warningUi';
import { PillButton } from './ui';
import { useT } from '../lib/i18n';

/** Where an answer is for. A demo city: its English name (the caller
 *  translates it). Any other place: the backend's `location.label`, already
 *  in the user's language ("Tiruchirappalli, Tamil Nadu", "your location
 *  (near …)"), so it is shown as is. */
function placeLabel(
  city: string | null | undefined,
  location: { label: string } | undefined,
  t: (s: string) => string,
) {
  if (city) return t(cityLabel(city));
  return location?.label ?? '';
}

/** router.legacy_day values -> a short human label. `next_<n>_days` is built
 *  by the backend, so it is parsed rather than enumerated. */
function dayLabel(day: string) {
  // classifyAsk's success/ungrounded/fallback split is structural (the API
  // has no single discriminant field across all branches), so a backend
  // response shaped unexpectedly could reach here with `day` missing —
  // degrade to a label instead of crashing the whole answer panel.
  if (typeof day !== 'string') return 'Unknown period';
  const span = /^next_(\d+)_days$/.exec(day);
  if (span) return `Next ${span[1]} days`;
  return day.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

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
  const t = useT();
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
        {t(p.is_live ? 'LIVE' : 'NOT LIVE')}
      </span>
      {p.issued && <span>{t('Issued {time}', { time: istTimestamp(p.issued) })}</span>}
      <span>{t('Retrieved {time}', { time: istTimestamp(p.retrieved_at) })}</span>
      <span className="text-ink-muted">
        {g.narration} · {g.provider}
        {g.attempts > 1 ? ` · ${t('{n} attempts', { n: g.attempts })}` : ''}
        {g.fallback_used ? ` · ${t('fell back to template')}` : ''}
      </span>
    </div>
  );
}

function FigureList({ figures }: { figures: Grounding['figures'] }) {
  const t = useT();
  if (figures.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {figures.map((f, i) => (
        <span
          key={`${f.reading}-${i}`}
          title={f.matched ? t('matched {path}', { path: f.path ?? '' }) : t('no matching value in the source data')}
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

export function Legend({ rows, highlight }: { rows: LegendRow[]; highlight?: WarningColour }) {
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
  /** Re-ask with a tapped place_id when the reply is `ambiguous`. Without it
   *  the candidates are listed but not tappable. */
  onPickPlace?: (placeId: string) => void;
  /** Share the browser's location and re-ask, when the reply is
   *  `needs_location` (no place named, none shared). */
  onUseLocation?: () => void;
}

/** Renders one /ask result. Every branch main.py can return gets its own
 *  treatment — in particular a refusal carries `message`, not `response`, and
 *  an unavailable warning is never shown as an all-clear. */
export default function AskAnswer({
  asked,
  loading,
  outcome,
  error,
  detail = false,
  onPickPlace,
  onUseLocation,
}: AskAnswerProps) {
  const t = useT();
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
          {t('Grounding an answer against live weather data…')}
        </div>
      )}

      {error && (
        <div className="flex flex-col gap-1 p-space-md rounded-xl bg-error-container text-on-error-container">
          <div className="flex items-center gap-1.5 font-label-md text-label-md font-semibold">
            <span className="material-symbols-outlined text-[18px]">{ERROR_ICON[error.kind]}</span>
            {error.kind === 'http'
              ? `${t('Weather service error')}${error.status ? ` (HTTP ${error.status})` : ''}`
              : t(
                  error.kind === 'timeout'
                    ? 'Request timed out'
                    : error.kind === 'malformed'
                      ? 'Unreadable reply'
                      : 'Weather service unreachable',
                )}
          </div>
          <p className="font-body-md text-body-md">{t(error.message)}</p>
        </div>
      )}

      {outcome?.kind === 'success' && (
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-low">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-secondary-container text-on-secondary-container font-citation-mono text-[10px] font-bold"
              title={t('{matched} of {total} figures matched the source data', {
                matched: outcome.data.grounding.matched,
                total: outcome.data.grounding.total,
              })}
            >
              <span className="material-symbols-outlined text-[12px]">verified_user</span>
              {t('GROUNDED {matched}/{total}', {
                matched: outcome.data.grounding.matched,
                total: outcome.data.grounding.total,
              })}
            </span>
            <Chip tone="primary">{t(outcome.data.intent.replace(/_/g, ' ').toUpperCase())}</Chip>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {placeLabel(outcome.data.city, outcome.data.location, t)}
            </Chip>
            <Chip>{t(dayLabel(outcome.data.day))}</Chip>
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          {/* whitespace-pre-line: the provenance footer (and an offline note)
              come on their own lines after the answer. */}
          <p className="font-body-lg text-body-lg text-on-surface leading-relaxed whitespace-pre-line">
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
              {' — '}
              {t(outcome.data.status === 'active' ? 'in force' : 'nothing in force')}
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

          <div className="flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-[14px] shrink-0 mt-0.5">science</span>
            <span>{outcome.data.warning.disclaimer}</span>
          </div>

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
              {t(outcome.data.provenance.is_live ? 'LIVE FEED' : 'FIXTURE')}
            </span>
            <span>
              {t('Valid {from} → {to}', {
                from: istTimestamp(outcome.data.provenance.valid_from),
                to: istTimestamp(outcome.data.provenance.valid_to),
              })}
            </span>
            <span className="text-ink-muted">
              {t('verbatim')} · {outcome.data.grounding.provider}
            </span>
          </div>
        </div>
      )}

      {outcome?.kind === 'warnings-unavailable' && (
        /* Deliberately neutral, never green: no verdict is not an all-clear. */
        <div className="flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="flex items-center gap-1 font-label-md text-label-md font-bold text-on-surface-variant">
              <span className="material-symbols-outlined text-[18px]">help</span>
              {t('No warning verdict')}
            </span>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {t(cityLabel(outcome.data.city))}
            </Chip>
            <Chip>
              {t('STATUS')}: {t(outcome.data.status).toUpperCase()}
            </Chip>
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
              {t('Answer withheld — not grounded')}
            </span>
            <Chip>
              <span className="material-symbols-outlined text-[11px] align-middle">location_on</span>{' '}
              {placeLabel(outcome.data.city, outcome.data.location, t)}
            </Chip>
            <Chip>
              {t('{matched}/{total} figures matched', {
                matched: outcome.data.grounding.matched,
                total: outcome.data.grounding.total,
              })}
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
              {t(
                outcome.data.ambiguous?.length
                  ? 'Which place?'
                  : outcome.data.not_found
                    ? 'Place not found'
                    : 'No answer',
              )}
            </span>
            <Chip tone="primary">{t(outcome.data.intent.replace(/_/g, ' ').toUpperCase())}</Chip>
            {/* Only the no_data branch carries a resolved city key. */}
            {outcome.data.city && (
              <Chip>
                <span className="material-symbols-outlined text-[11px] align-middle">
                  location_on
                </span>{' '}
                {t(cityLabel(outcome.data.city))}
              </Chip>
            )}
            {/* On unsupported_city the rejected name survives only in nlu.city. */}
            {!outcome.data.city && outcome.data.nlu.city && (
              <Chip>{t('asked about “{city}”', { city: outcome.data.nlu.city })}</Chip>
            )}
          </div>

          {outcome.data.notice && <Notice text={outcome.data.notice} />}

          <p className="font-body-md text-body-md text-on-surface">{outcome.data.message}</p>

          {/* Several places share the name: one button each, district under
              the label; a tap re-asks the same question for that place_id.
              Never picks one on the user's behalf. */}
          {outcome.data.ambiguous && outcome.data.ambiguous.length > 0 && (
            <div className="flex flex-wrap gap-space-xs" role="group" aria-label={t('Choose a place')}>
              {outcome.data.ambiguous.map((c) => (
                <button
                  key={c.place_id}
                  type="button"
                  disabled={!onPickPlace}
                  onClick={() => onPickPlace?.(c.place_id)}
                  className="flex flex-col items-start text-left px-3 py-2 rounded-lg border border-card-border bg-card hover:bg-tint disabled:cursor-default"
                  data-testid="place-candidate"
                >
                  <span className="font-label-md text-label-md text-on-surface">{c.label}</span>
                  {c.district && (
                    <span className="font-body-sm text-body-sm text-on-surface-variant">{c.district}</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Not in the gazetteer: offer the nearest known place, never
              answered for it unasked. */}
          {outcome.data.not_found && outcome.data.nearest && onPickPlace && (
            <div>
              <PillButton
                icon="near_me"
                label={t('Use {place}', { place: outcome.data.nearest.label })}
                onClick={() => onPickPlace(outcome.data.nearest!.place_id)}
              />
            </div>
          )}
          {outcome.data.needs_location && onUseLocation && (
            <div>
              <PillButton icon="my_location" label="Use my location" onClick={onUseLocation} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
