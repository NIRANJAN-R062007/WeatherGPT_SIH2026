// Alerts & Warnings — the pics/ mockup (mobile alerts_page.dart): a featured
// alert card, an Active Alerts list and a "stay prepared" banner, fed by
// GET /warnings for the selected city. The featured card is loading / error
// / "no verdict" (neutral, never green — no verdict is not an all-clear) /
// the IMD colour verdict, tinted by the feed's own colour, with its legend
// and provenance under "View details". The feed carries one warning per
// city, so the list holds at most that one. The colour legend comes from
// GET /glossary (the one shared wording) when it answers, marked when a
// translation hasn't had native review; /warnings' own legend otherwise.
// Emergency numbers (GET /hotlines) follow, each a tel: link; 112 shows even
// when the list can't be fetched. When the warnings service can't be
// reached, the saved reply shows under a banner saying when it was saved; a
// saved "nothing in force" is shown as no verdict, since it says nothing
// about now. Saved emergency numbers show as usual.
import { useEffect, useState } from 'react';
import { Legend } from '../components/AskAnswer';
import PageFrame from '../components/PageFrame';
import {
  ActionRow,
  AppCard,
  ErrorPanel,
  Icon,
  IconDisc,
  InfoBanner,
  LoadingPanel,
  PageHeader,
  SavedDataBanner,
  SectionTitle,
  TagChip,
} from '../components/ui';
import type { LegendRow, WarningColour } from '../lib/api';
import { calendarDate, dayMonth, savedTimeLabel } from '../lib/format';
import { fetchGlossary, glossaryLegend, legendReviewed, type Glossary } from '../lib/glossary';
import { EMERGENCY_HOTLINE, fetchHotlines, type Hotline, type HotlineList } from '../lib/hotlines';
import { useWarnings, type WarningsUnavailable, type WarningsVerdict } from '../lib/warnings';
import { COLOUR_HEX, istTimestamp } from '../lib/warningUi';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useT } from '../lib/i18n';

/** The colour legend from the glossary when it answered, else /warnings'
 *  own; a translation no native speaker has checked yet says so. */
function AlertsLegend({
  rows,
  glossary,
  highlight,
}: {
  rows: LegendRow[];
  glossary: Glossary | null;
  highlight?: WarningColour;
}) {
  const t = useT();
  const fromGlossary = glossaryLegend(glossary);
  return (
    <div className="flex flex-col gap-1">
      <Legend rows={fromGlossary ?? rows} highlight={highlight} />
      {fromGlossary && glossary && !legendReviewed(glossary) && (
        <p className="font-body-sm text-body-sm text-ink-muted">
          {t('These translations have not been reviewed by a native speaker yet.')}
        </p>
      )}
    </div>
  );
}

function NoVerdict({ data, glossary }: { data: WarningsUnavailable; glossary: Glossary | null }) {
  const t = useT();
  return (
    <AppCard className="!bg-surface-container-low !border-outline-variant">
      <div className="flex items-center gap-3">
        <IconDisc icon="help" color="rgb(var(--c-on-surface-variant))" />
        <div>
          <div className="font-label-md text-label-md font-bold text-ink">{t('No warning verdict')}</div>
          <div className="font-body-sm text-body-sm text-ink-muted">{t(data.city_name)}</div>
        </div>
      </div>
      <p className="mt-space-sm font-body-md text-body-md text-on-surface">
        {t("Weather warnings aren't available right now for {city} — this can't be read as an all-clear.", {
          city: t(data.city_name),
        })}
      </p>
      <div className="mt-space-sm">
        <AlertsLegend rows={data.legend} glossary={glossary} />
      </div>
    </AppCard>
  );
}

/** The featured card: tinted by the feed's own colour, headline up front,
 *  the legend and provenance behind "View details". */
export function Verdict({
  data,
  glossary,
  expanded,
  onToggle,
}: {
  data: WarningsVerdict;
  glossary: Glossary | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const t = useT();
  const w = data.warning;
  const tone = COLOUR_HEX[w.colour];
  const active = data.status === 'active';
  const title = active
    ? w.category_label
      ? t('{category} Alert', { category: w.category_label })
      : t('{colour} warning', { colour: w.colour_label })
    : t('No warnings in force');
  return (
    <AppCard
      style={{
        background: `linear-gradient(color-mix(in srgb, ${tone} 8%, transparent), color-mix(in srgb, ${tone} 8%, transparent)), rgb(var(--c-card))`,
        borderColor: `color-mix(in srgb, ${tone} 35%, transparent)`,
      }}
    >
      <div className="flex items-start gap-3">
        <IconDisc icon={active ? 'priority_high' : 'check'} solid color={tone} size={36} />
        <div className="flex-1 min-w-0">
          <div className="font-label-md text-[15px] font-bold" style={{ color: tone }}>
            {title}
          </div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <TagChip icon="location_on">{data.city_name}</TagChip>
            {w.colour_label && (
              <TagChip>
                {w.colour_label} — {t(active ? 'in force' : 'nothing in force')}
              </TagChip>
            )}
          </div>
          {/* The feed's own headline, verbatim — not narrated, not re-graded. */}
          <p className="mt-space-sm font-body-md text-body-md text-ink">{w.headline}</p>
          {/* Phase 7 B2: a fixture warning always carries its label, up front. */}
          {w.disclaimer && (
            <div className="mt-space-sm flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed font-body-sm text-body-sm">
              <Icon name="science" size={14} className="mt-0.5" />
              <span>{w.disclaimer}</span>
            </div>
          )}
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            className="mt-space-sm inline-flex items-center gap-1 px-3.5 py-1.5 rounded-full bg-card font-label-md text-label-md font-semibold text-primary hover:bg-tint"
          >
            {t(expanded ? 'Hide details' : 'View details')}
            <Icon name={expanded ? 'expand_less' : 'arrow_forward'} size={16} />
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-space-md flex flex-col gap-space-sm">
          {w.advice && <p className="font-body-md text-body-md text-ink-muted">{w.advice}</p>}
          <AlertsLegend rows={data.legend} glossary={glossary} highlight={w.colour} />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-space-xs border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
            <span className="flex items-center gap-1">
              <Icon name="campaign" size={12} />
              {w.issued_by}
            </span>
            <span>{t('Valid {from} → {to}', { from: istTimestamp(w.valid_from), to: istTimestamp(w.valid_to) })}</span>
            <span className="text-ink-muted">
              {t('source')}: {w.source}
            </span>
          </div>
        </div>
      )}
    </AppCard>
  );
}

/** One number: a card that opens the dialer, read out as "Call …, …". */
function HotlineRow({ line }: { line: Hotline }) {
  const t = useT();
  const emergency = line.dial === '112';
  return (
    <a
      href={`tel:${line.dial}`}
      aria-label={t('Call {name}, {number}', { name: t(line.name), number: line.number })}
      className="block rounded-card border border-card-border bg-card shadow-card px-3 py-2.5 transition hover:border-primary/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
    >
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <IconDisc icon={emergency ? 'emergency' : 'support_agent'} color={emergency ? 'rgb(var(--c-error))' : undefined} />
        <span className="flex-1 min-w-[8rem]">
          <span className="block font-label-md text-label-md font-semibold text-ink">{t(line.name)}</span>
          {line.note && <span className="block font-body-sm text-body-sm text-ink-muted">{t(line.note)}</span>}
        </span>
        <span className="ml-auto flex items-center gap-1.5 font-label-md text-[15px] font-bold text-primary">
          {line.number}
          <Icon name="call" size={18} />
        </span>
      </span>
    </a>
  );
}

/** The city's emergency numbers; 112 alone (with a note saying why) until
 *  or unless the list arrives. */
function Hotlines({ list, failed }: { list: HotlineList | null; failed: boolean }) {
  const t = useT();
  const checked = calendarDate(list?.checked);
  const footnote = failed
    ? t("Couldn't load the local numbers. 112 works anywhere in India.")
    : checked
      ? t('Checked against official government pages on {date}.', {
          date: `${dayMonth(t, checked)} ${checked.getUTCFullYear()}`,
        })
      : null;
  return (
    <div className="flex flex-col gap-space-sm">
      {(list?.lines ?? [EMERGENCY_HOTLINE]).map((line) => (
        <HotlineRow key={`${line.dial}-${line.name}`} line={line} />
      ))}
      {footnote && <p className="font-body-sm text-body-sm text-ink-muted">{footnote}</p>}
    </div>
  );
}

export default function AlertsPage() {
  const t = useT();
  const { lang, city, cityInfo, personaInfo } = useUiPrefs();
  const { loading, data, error, load } = useWarnings();
  // Details stay open only for the city they were opened on.
  const [expandedFor, setExpandedFor] = useState<string | null>(null);
  const expanded = expandedFor === city;
  const setExpanded = (open: boolean) => setExpandedFor(open ? city : null);
  // Each reply is kept with the city + language it answers, so one for a
  // city or language no longer shown is never displayed.
  const key = `${city}|${lang}`;
  const [hotlines, setHotlines] = useState<{ key: string; list: HotlineList | null } | null>(null);
  const [glossary, setGlossary] = useState<{ lang: string; glossary: Glossary | null } | null>(null);

  // Fetch on mount and whenever the selected city or language changes.
  useEffect(() => {
    void load(city, lang);
    const key = `${city}|${lang}`;
    fetchHotlines({ city, lang }).then(
      (list) => setHotlines({ key, list }),
      () => setHotlines({ key, list: null }),
    );
    fetchGlossary({ lang }).then(
      (g) => setGlossary({ lang, glossary: g }),
      () => setGlossary({ lang, glossary: null }),
    );
  }, [city, lang, load]);
  const shownHotlines = hotlines?.key === key ? hotlines : null;
  const shownGlossary = glossary?.lang === lang ? glossary.glossary : null;

  const active = data?.status === 'active';
  // A saved "nothing in force" says nothing about now.
  const verdict = data && data.status !== 'unavailable' && (!data.savedAt || active) ? data : null;

  return (
    <PageFrame>
      <PageHeader title="Alerts & Warnings" subtitle={personaInfo.alertsLead} />
      {!loading && data?.savedAt && (
        <div className="mt-space-lg">
          <SavedDataBanner
            message="Couldn't reach the warnings service. This was saved at {time}; newer warnings can't be checked now."
            messageArgs={{ time: savedTimeLabel(t, data.savedAt) }}
            onRetry={() => void load(city, lang)}
          />
        </div>
      )}
      <div className="mt-space-lg">
        {loading ? (
          <LoadingPanel text="Checking current warnings…" />
        ) : error ? (
          <ErrorPanel
            icon="wifi_off"
            title="Warnings service unreachable"
            message={error.message}
            onRetry={() => void load(city, lang)}
          />
        ) : verdict ? (
          <Verdict data={verdict} glossary={shownGlossary} expanded={expanded} onToggle={() => setExpanded(!expanded)} />
        ) : data ? (
          <NoVerdict data={data as WarningsUnavailable} glossary={shownGlossary} />
        ) : null}
      </div>

      <div className="mt-space-lg mb-space-sm">
        <SectionTitle text="Active Alerts" />
      </div>
      {active && verdict ? (
        <ActionRow
          icon="warning"
          iconColor={COLOUR_HEX[verdict.warning.colour]}
          title={verdict.warning.category_label || verdict.warning.colour_label}
          subtitle={verdict.city_name}
          detail={verdict.warning.valid_to ? t('Until {time}', { time: istTimestamp(verdict.warning.valid_to) }) : undefined}
          onClick={() => setExpanded(true)}
        />
      ) : (
        <AppCard>
          <div className="flex items-center gap-3">
            <IconDisc icon="notifications" size={36} />
            <p className="font-body-md text-body-md text-ink-muted">
              {verdict
                ? t('No active alerts for {city}.', { city: t(cityInfo.name) })
                : t('Alerts for {city} will be listed here when the warnings feed has a verdict.', { city: t(cityInfo.name) })}
            </p>
          </div>
        </AppCard>
      )}

      <div className="mt-space-lg mb-space-sm">
        <SectionTitle text="Emergency numbers" />
      </div>
      <Hotlines list={shownHotlines?.list ?? null} failed={shownHotlines !== null && shownHotlines.list === null} />

      <div className="mt-space-lg">
        <InfoBanner
          icon={personaInfo.icon}
          title="Stay prepared."
          body="Check for updates regularly — they refresh whenever you open this page."
        />
      </div>
      <div className="mt-space-md">
        <AppCard>
          <div className="flex items-center gap-2">
            <Icon name="verified" size={18} className="text-primary" />
            <span className="font-label-md text-label-md font-semibold text-ink">{t('Source')}</span>
          </div>
          <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
            {t(
              "The colour code and headline are the warning feed's own, shown verbatim — WeatherGPT explains a colour, it never re-grades one. The source line on each verdict names the feed that answered.",
            )}
          </p>
        </AppCard>
      </div>
    </PageFrame>
  );
}
