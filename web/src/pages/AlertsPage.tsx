// Alerts & Warnings — the pics/ mockup (mobile alerts_page.dart): a featured
// alert card, an Active Alerts list and a "stay prepared" banner, fed by
// GET /warnings for the selected city. The featured card is loading / error
// / "no verdict" (neutral, never green — no verdict is not an all-clear) /
// the IMD colour verdict, tinted by the feed's own colour, with its legend
// and provenance under "View details". The feed carries one warning per
// city, so the list holds at most that one.
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
  SectionTitle,
  TagChip,
} from '../components/ui';
import { useWarnings, type WarningsUnavailable, type WarningsVerdict } from '../lib/warnings';
import { COLOUR_HEX, istTimestamp } from '../lib/warningUi';
import { useUiPrefs } from '../state/UiPrefsContext';

function NoVerdict({ data }: { data: WarningsUnavailable }) {
  return (
    <AppCard className="!bg-surface-container-low !border-outline-variant">
      <div className="flex items-center gap-3">
        <IconDisc icon="help" color="rgb(var(--c-on-surface-variant))" />
        <div>
          <div className="font-label-md text-label-md font-bold text-ink">No warning verdict</div>
          <div className="font-body-sm text-body-sm text-ink-muted">{data.city_name}</div>
        </div>
      </div>
      <p className="mt-space-sm font-body-md text-body-md text-on-surface">
        Weather warnings aren't available right now for {data.city_name} — this can't be read as an all-clear.
      </p>
      <div className="mt-space-sm">
        <Legend rows={data.legend} />
      </div>
    </AppCard>
  );
}

/** The featured card: tinted by the feed's own colour, headline up front,
 *  the legend and provenance behind "View details". */
function Verdict({ data, expanded, onToggle }: { data: WarningsVerdict; expanded: boolean; onToggle: () => void }) {
  const w = data.warning;
  const tone = COLOUR_HEX[w.colour];
  const active = data.status === 'active';
  const title = active ? (w.category_label ? `${w.category_label} Alert` : `${w.colour_label} warning`) : 'No warnings in force';
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
                {w.colour_label}
                {active ? ' — in force' : ' — nothing in force'}
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
            {expanded ? 'Hide details' : 'View details'}
            <Icon name={expanded ? 'expand_less' : 'arrow_forward'} size={16} />
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-space-md flex flex-col gap-space-sm">
          {w.advice && <p className="font-body-md text-body-md text-ink-muted">{w.advice}</p>}
          <Legend rows={data.legend} highlight={w.colour} />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-space-xs border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
            <span className="flex items-center gap-1">
              <Icon name="campaign" size={12} />
              {w.issued_by}
            </span>
            <span>
              Valid {istTimestamp(w.valid_from)} → {istTimestamp(w.valid_to)}
            </span>
            <span className="text-outline">source: {w.source}</span>
          </div>
        </div>
      )}
    </AppCard>
  );
}

export default function AlertsPage() {
  const { lang, city, cityInfo, personaInfo } = useUiPrefs();
  const { loading, data, error, load } = useWarnings();
  // Details stay open only for the city they were opened on.
  const [expandedFor, setExpandedFor] = useState<string | null>(null);
  const expanded = expandedFor === city;
  const setExpanded = (open: boolean) => setExpandedFor(open ? city : null);

  // Fetch on mount and whenever the selected city or language changes.
  useEffect(() => {
    void load(city, lang);
  }, [city, lang, load]);

  const verdict = data && data.status !== 'unavailable' ? data : null;
  const active = verdict?.status === 'active';

  return (
    <PageFrame>
      <PageHeader title="Alerts & Warnings" subtitle={personaInfo.alertsLead} />
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
          <Verdict data={verdict} expanded={expanded} onToggle={() => setExpanded(!expanded)} />
        ) : data ? (
          <NoVerdict data={data as WarningsUnavailable} />
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
          detail={verdict.warning.valid_to ? `Until ${istTimestamp(verdict.warning.valid_to)}` : undefined}
          onClick={() => setExpanded(true)}
        />
      ) : (
        <AppCard>
          <div className="flex items-center gap-3">
            <IconDisc icon="notifications" size={36} />
            <p className="font-body-md text-body-md text-ink-muted">
              {verdict
                ? `No active alerts for ${cityInfo.name}.`
                : `Alerts for ${cityInfo.name} will be listed here when the warnings feed has a verdict.`}
            </p>
          </div>
        </AppCard>
      )}

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
            <span className="font-label-md text-label-md font-semibold text-ink">Source</span>
          </div>
          <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
            The colour code and headline are the warning feed's own, shown verbatim — WeatherGPT explains a colour, it
            never re-grades one. The source line on each verdict names the feed that answered.
          </p>
        </AppCard>
      </div>
    </PageFrame>
  );
}
