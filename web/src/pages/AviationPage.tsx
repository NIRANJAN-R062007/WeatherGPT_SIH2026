// Airport weather: the current METAR and TAF for the selected city's airport,
// from GET /aviation (lib/aviation.ts; services/orchestrator/aviation.py).
// Each report shows its plain-language briefing (English only — the decoders'
// fixed templates), the code exactly as issued, and whether it is live or an
// offline snapshot, dated. A missing report is "not available", never fair
// weather (plan.md §2 principle 3), and the page always carries the
// not-for-flight-planning disclaimer.
import { useEffect } from 'react';
import PageFrame from '../components/PageFrame';
import { AppCard, ErrorPanel, Icon, IconDisc, LiveBadge, LoadingPanel, PageHeader, SectionTitle, TagChip } from '../components/ui';
import { istDayMonth } from '../lib/format';
import { useAviation, type AviationReport } from '../lib/aviation';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useT } from '../lib/i18n';

function ReportCard({
  icon,
  title,
  subtitle,
  report,
  missing,
}: {
  icon: string;
  title: string;
  subtitle: string;
  report: AviationReport | null;
  missing: string;
}) {
  const t = useT();
  const stamp = report?.decoded.observed ?? report?.decoded.issued;
  return (
    <AppCard pad="p-space-lg">
      <div className="flex items-start gap-3">
        <IconDisc icon={icon} solid size={36} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-headline-sm text-headline-sm font-bold text-ink">{t(title)}</h2>
            {report && <LiveBadge live={report.is_live} />}
          </div>
          <div className="font-body-sm text-body-sm text-ink-muted">{t(subtitle)}</div>
        </div>
      </div>

      {report === null ? (
        <p className="mt-space-md font-body-md text-body-md text-ink-muted">{t(missing)}</p>
      ) : (
        <>
          {!report.is_live && (
            <div className="mt-space-md flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed font-body-sm text-body-sm">
              <Icon name="history" size={14} className="mt-0.5" />
              <span>
                {t('Snapshot taken {time} — not a live report.', { time: istDayMonth(report.retrieved_at) })}
              </span>
            </div>
          )}
          {/* The decoders only ever write English. */}
          <ul lang="en" className="mt-space-md flex flex-col gap-space-sm">
            {report.lines.map((line, i) => (
              <li key={i} className="font-body-md text-body-md text-ink">
                {line}
              </li>
            ))}
          </ul>
          <div className="mt-space-md flex flex-wrap items-center gap-x-3 gap-y-1 pt-space-sm border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
            {stamp && (
              <span>
                {t(report.decoded.observed ? 'Observed' : 'Issued')} {stamp.time_ist} IST · {stamp.time_utc} UTC
              </span>
            )}
            <span className="text-outline">
              {t('source')}: {report.source}
            </span>
          </div>
          <details className="mt-space-sm">
            <summary className="cursor-pointer font-label-md text-label-md font-semibold text-primary">
              {t('Show the code as issued')}
            </summary>
            <code className="mt-space-xs block break-words p-space-sm rounded-lg bg-surface-container-low font-citation-mono text-citation-mono text-on-surface">
              {report.raw}
            </code>
          </details>
        </>
      )}
    </AppCard>
  );
}

export default function AviationPage() {
  const t = useT();
  const { city, cityInfo } = useUiPrefs();
  const { loading, data, error, load } = useAviation();

  useEffect(() => {
    void load(city);
  }, [city, load]);

  const where = data?.station_name ? `${data.station_name} airport (${data.station})` : `${cityInfo.name} airport`;

  return (
    <PageFrame>
      <PageHeader
        title="Airport weather"
        subtitle={t('The latest METAR and TAF for {city} airport, decoded into plain language.', { city: t(cityInfo.name) })}
      />
      <div className="mt-space-lg flex flex-col gap-space-md">
        {loading ? (
          <LoadingPanel text="Fetching the airport reports…" />
        ) : error ? (
          <ErrorPanel
            icon="wifi_off"
            title="Airport weather unavailable"
            message={error.message}
            onRetry={() => void load(city)}
          />
        ) : data && data.status === 'unavailable' ? (
          <AppCard className="!bg-surface-container-low !border-outline-variant">
            <div className="flex items-center gap-3">
              <IconDisc icon="help" color="rgb(var(--c-on-surface-variant))" />
              <div>
                <div className="font-label-md text-label-md font-bold text-ink">{t('No airport reports')}</div>
                <div className="font-body-sm text-body-sm text-ink-muted">{where}</div>
              </div>
            </div>
            <p className="mt-space-sm font-body-md text-body-md text-on-surface">
              {t("The airport reports for {city} aren't available right now — this can't be read as fair weather.", {
                city: t(cityInfo.name),
              })}
            </p>
          </AppCard>
        ) : data ? (
          <>
            <div className="flex flex-wrap gap-1.5">
              <TagChip icon="flight">{where}</TagChip>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-space-md items-start">
              <div className="flex flex-col gap-space-sm">
                <SectionTitle text="Current observation" />
                <ReportCard
                  icon="visibility"
                  title="METAR"
                  subtitle="What the airport is reporting now"
                  report={data.metar}
                  missing="No METAR is available for this airport right now."
                />
              </div>
              <div className="flex flex-col gap-space-sm">
                <SectionTitle text="Airport forecast" />
                <ReportCard
                  icon="schedule"
                  title="TAF"
                  subtitle="Forecast for the airport's next 24–30 hours"
                  report={data.taf}
                  missing="No TAF is available for this airport right now."
                />
              </div>
            </div>
            <div className="flex items-start gap-1.5 px-3 py-2 rounded-xl bg-tint font-body-sm text-body-sm text-ink-muted">
              <Icon name="info" size={16} className="mt-0.5 text-primary" />
              <span>{data.disclaimer}</span>
            </div>
          </>
        ) : null}
      </div>
    </PageFrame>
  );
}
