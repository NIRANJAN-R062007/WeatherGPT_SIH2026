// Climate trends: how the selected city's rainfall and mean temperature have
// changed over about 30 years, from Open-Meteo's ERA5 reanalysis (GET /climate,
// lib/climate.ts; services/orchestrator/climate.py; mobile ClimatePage). The
// chart is a picture of the yearly figures; the trend sentence, and the list of
// every year under it, carry the same numbers as text.
//
// Every figure and the trend are computed server-side, in plain code, never by
// an LLM; this page only draws and words them. The source line "Open-Meteo /
// ERA5 reanalysis, not IMD station data", the credit link and the "computed by
// WeatherGPT" note are on the page in every state. A year with missing days is
// left out of the chart (a gap, never zero), and a trend that isn't
// statistically clear is worded "can't be told apart from year-to-year
// variation", never "no change" (plan.md §2 principle 3; climate.py's notes).
import { useEffect, useState } from 'react';
import PageFrame from '../components/PageFrame';
import { AppCard, ErrorPanel, Icon, IconDisc, LoadingPanel, PageHeader } from '../components/ui';
import {
  CLIMATE_PERIODS,
  METRIC_NAME,
  PERIOD_NAME,
  formatClimate,
  hasSlope,
  meanYearOf,
  niceStep,
  seriesOf,
  trendOf,
  trendValueAt,
  useClimate,
  type ClimateMetric,
  type ClimatePeriod,
  type ClimateResponse,
  type ClimateTrend,
  type YearValue,
} from '../lib/climate';
import { istTime, istDayMonth } from '../lib/format';
import { useT, type T } from '../lib/i18n';
import { useUiPrefs } from '../state/UiPrefsContext';

// A compact coordinate system so the axis text stays readable when the SVG is
// scaled down to a phone; the chart is capped in width so it isn't blown up on
// a desktop.
const W = 480;
const H = 300;
const PLOT = { left: 46, right: 8, top: 10, bottom: 26 };
const AXIS_FONT = 13;

/** One series as an SVG: bars for rainfall (they start at 0), a line with dots
 *  for temperature, and the trend line through the complete years. A year with
 *  missing data is a gap. No chart package: the figures are few. */
export function ClimateChart({
  series,
  metric,
  trend,
  label,
}: {
  series: YearValue[];
  metric: ClimateMetric;
  trend: ClimateTrend | null;
  label: string;
}) {
  const known = series.filter((p): p is { year: number; value: number } => p.value !== null);
  if (known.length === 0) return null;
  const firstYear = series[0].year;
  const lastYear = series[series.length - 1].year;
  const n = lastYear - firstYear + 1;
  const meanYear = meanYearOf(series);
  const slope = hasSlope(trend) ? trend : null;

  let lo = Math.min(...known.map((p) => p.value));
  let hi = Math.max(...known.map((p) => p.value));
  if (slope) {
    for (const y of [firstYear, lastYear]) {
      const v = trendValueAt(slope, y, meanYear);
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  }
  if (metric === 'rain') lo = 0;
  const step = niceStep(hi - lo, 4);
  const yMin = metric === 'rain' ? 0 : Math.floor(lo / step) * step;
  let yMax = Math.ceil(hi / step) * step;
  if (yMax <= yMin) yMax = yMin + step;

  const plotW = W - PLOT.left - PLOT.right;
  const plotH = H - PLOT.top - PLOT.bottom;
  const x = (year: number) => PLOT.left + ((year - firstYear + 0.5) / n) * plotW;
  const y = (v: number) => PLOT.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const ticks: number[] = [];
  for (let v = yMin; v <= yMax + step / 2; v += step) ticks.push(v);
  const xLabels = [...new Set([firstYear, firstYear + Math.floor(n / 2), lastYear])];

  // The temperature line breaks at a missing year.
  const runs: { year: number; value: number }[][] = [];
  let run: { year: number; value: number }[] | null = null;
  for (const p of series) {
    if (p.value === null) {
      run = null;
    } else {
      if (!run) {
        run = [];
        runs.push(run);
      }
      run.push({ year: p.year, value: p.value });
    }
  }
  const lines = runs.filter((r) => r.length > 1);
  const barW = Math.max(2, (plotW / n) * 0.62);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="w-full max-w-2xl h-auto">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={PLOT.left} x2={W - PLOT.right} y1={y(v)} y2={y(v)} className="stroke-outline-variant" strokeWidth={0.8} opacity={0.6} />
          <text x={PLOT.left - 5} y={y(v)} textAnchor="end" dominantBaseline="middle" fontSize={AXIS_FONT} className="fill-ink-muted">
            {step < 1 ? v.toFixed(1) : v.toFixed(0)}
          </text>
        </g>
      ))}
      {xLabels.map((yr) => (
        <text key={yr} x={x(yr)} y={H - 7} textAnchor="middle" fontSize={AXIS_FONT} className="fill-ink-muted">
          {yr}
        </text>
      ))}
      {metric === 'rain' ? (
        known.map((p) => (
          <rect
            key={p.year}
            x={x(p.year) - barW / 2}
            y={y(p.value)}
            width={barW}
            height={Math.max(0, y(yMin) - y(p.value))}
            rx={2}
            className="fill-primary"
          />
        ))
      ) : (
        <>
          {lines.map((line) => (
            <polyline
              key={line[0].year}
              points={line.map((p) => `${x(p.year)},${y(p.value)}`).join(' ')}
              fill="none"
              strokeWidth={2}
              strokeLinejoin="round"
              className="stroke-primary"
            />
          ))}
          {known.map((p) => (
            <circle key={p.year} cx={x(p.year)} cy={y(p.value)} r={2.8} className="fill-primary" />
          ))}
        </>
      )}
      {slope && (
        <line
          x1={x(firstYear)}
          y1={y(trendValueAt(slope, firstYear, meanYear))}
          x2={x(lastYear)}
          y2={y(trendValueAt(slope, lastYear, meanYear))}
          strokeWidth={2.2}
          strokeDasharray="9 5"
          className="stroke-ink"
        />
      )}
    </svg>
  );
}

function Key({ mark, text }: { mark: 'bar' | 'dot' | 'dashed'; text: string }) {
  const t = useT();
  return (
    <span className="inline-flex items-center gap-1.5 font-body-sm text-body-sm text-ink-muted">
      <svg width={22} height={12} aria-hidden="true">
        {mark === 'bar' && <rect x={7} y={1} width={8} height={11} rx={2} className="fill-primary" />}
        {mark === 'dot' && (
          <>
            <line x1={0} x2={22} y1={6} y2={6} strokeWidth={2} className="stroke-primary" />
            <circle cx={11} cy={6} r={3} className="fill-primary" />
          </>
        )}
        {mark === 'dashed' && <line x1={0} x2={22} y1={6} y2={6} strokeWidth={2} strokeDasharray="5 3" className="stroke-ink" />}
      </svg>
      {t(text)}
    </span>
  );
}

/** The trend in words, from the server's numbers. Three honest cases: a clear
 *  trend, one that can't be told apart from year-to-year variation (which is
 *  not "no change"), and too few complete years to fit one. */
function TrendCard({
  metric,
  trend,
  minYears,
}: {
  metric: ClimateMetric;
  trend: ClimateTrend | null;
  minYears: number;
}) {
  const t = useT();
  let headline: string;
  let body: string;
  let args: Record<string, string | number>;
  if (!trend || !hasSlope(trend)) {
    headline = 'No trend';
    body = 'Not enough complete years to fit a trend: at least {min} are needed, and there are {n}.';
    args = { min: minYears, n: trend ? trend.n : 0 };
  } else {
    headline = 'Trend';
    const se = trend.stderr_per_decade;
    args = {
      slope: formatClimate(trend.slope_per_decade as number, metric, true),
      se: se === null ? '' : formatClimate(se, metric, true).replace('+', ''),
      n: trend.n,
      from: trend.first_year ?? '',
      to: trend.last_year ?? '',
      mean: formatClimate(trend.mean as number, metric),
    };
    body = trend.significant_95
      ? 'Change of {slope} per decade (± {se}) over {n} complete years, {from}–{to}. The average is {mean}. A change this size is clear of year-to-year variation at the 95% level.'
      : "Change of {slope} per decade (± {se}) over {n} complete years, {from}–{to}. The average is {mean}. This can't be told apart from year-to-year variation. That does not mean nothing has changed.";
  }
  return (
    <AppCard className="!bg-surface-container-low">
      <div className="flex items-center gap-3">
        <IconDisc icon="trending_up" solid size={36} />
        <h2 className="font-headline-sm text-headline-sm font-bold text-ink">{t(headline)}</h2>
      </div>
      <p className="mt-space-sm font-body-md text-body-md text-ink">{t(body, args)}</p>
    </AppCard>
  );
}

/** The source line, credit link, "computed by WeatherGPT" note and licence and
 *  terms links — on every state of the page. */
export function ClimateSource({ data }: { data: ClimateResponse }) {
  const t = useT();
  const link = (href: string, text: string) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center min-h-12 font-label-md text-label-md text-primary underline"
    >
      {text}
    </a>
  );
  return (
    <div className="flex flex-col gap-space-sm">
      <div className="flex items-start gap-1.5 px-3 py-2.5 rounded-xl bg-tint font-body-sm text-body-sm text-ink-muted">
        <Icon name="info" size={16} className="mt-0.5 text-primary" />
        <span>
          {t(data.changes_note)} {t(data.calendar_note)}
        </span>
      </div>
      {/* The source line, exactly as the server sends it (CLM-5's wording). */}
      <div className="font-citation-mono text-citation-mono text-on-surface-variant">{data.label}</div>
      <div className="flex flex-wrap gap-x-space-md">
        {link(data.credit.url, data.credit.text)}
        {link(data.licence_url, t('Licence'))}
        {link(data.terms_url, t('Terms of use'))}
      </div>
    </div>
  );
}

function PillSwitch<V extends string>({
  value,
  options,
  onChange,
}: {
  value: V;
  options: { value: V; label: string }[];
  onChange: (v: V) => void;
}) {
  const t = useT();
  return (
    <div role="tablist" className="flex gap-1 p-1 rounded-full bg-tint">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={`flex-1 min-h-12 py-2.5 rounded-full font-label-md text-label-md transition-colors ${
            o.value === value ? 'bg-accent-gradient text-on-primary font-bold' : 'text-ink font-medium hover:bg-tint-strong'
          }`}
        >
          {t(o.label)}
        </button>
      ))}
    </div>
  );
}

function missingLabel(t: T) {
  return t('Missing days — left out');
}

/** Everything below the header once data has arrived; exported so it renders in
 *  tests without the fetch. */
export function ClimateBody({
  data,
  metric,
  period,
  onMetric,
  onPeriod,
}: {
  data: ClimateResponse;
  metric: ClimateMetric;
  period: ClimatePeriod;
  onMetric: (m: ClimateMetric) => void;
  onPeriod: (p: ClimatePeriod) => void;
}) {
  const t = useT();
  const series = seriesOf(data, period, metric);
  const trend = trendOf(data, period, metric);
  const known = series.filter((p) => p.value !== null).length;
  const missing = series.length - known;
  const title = t('{metric} — {period}', { metric: t(METRIC_NAME[metric]), period: t(PERIOD_NAME[period]) });
  const chartLabel = t('Chart: {title}, {from} to {to}. The same figures are listed below.', {
    title,
    from: series[0]?.year ?? '',
    to: series[series.length - 1]?.year ?? '',
  });

  return (
    <>
      {!data.is_live && (
        <div className="flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed font-body-sm text-body-sm">
          <Icon name="history" size={14} className="mt-0.5" />
          <span>
            {t('Snapshot taken {time} — not live data.', {
              time: `${istDayMonth(data.retrieved_at)}, ${istTime(data.retrieved_at)}`,
            })}
          </span>
        </div>
      )}
      <PillSwitch
        value={metric}
        onChange={onMetric}
        options={[
          { value: 'rain', label: 'Rainfall' },
          { value: 'temperature', label: 'Temperature' },
        ]}
      />
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('Period')}>
        {CLIMATE_PERIODS.map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={p === period}
            onClick={() => onPeriod(p)}
            className={`min-h-12 px-3 rounded-lg font-label-md text-label-md ${
              p === period ? 'bg-primary-fixed text-on-primary-fixed font-bold' : 'bg-surface-container text-ink font-medium hover:bg-surface-container-high'
            }`}
          >
            {t(PERIOD_NAME[p])}
          </button>
        ))}
      </div>

      <AppCard pad="p-space-md">
        <h2 className="font-headline-sm text-headline-sm font-bold text-ink">{title}</h2>
        <div className="mt-space-sm">
          {known === 0 ? (
            <p className="font-body-md text-body-md text-ink-muted">{t('No complete years to draw for this period.')}</p>
          ) : (
            <ClimateChart series={series} metric={metric} trend={trend} label={chartLabel} />
          )}
        </div>
        <div className="mt-space-sm flex flex-wrap gap-x-space-md gap-y-1">
          <Key mark={metric === 'rain' ? 'bar' : 'dot'} text={metric === 'rain' ? 'Total for the year' : 'Average for the year'} />
          {hasSlope(trend) && <Key mark="dashed" text="Trend line" />}
        </div>
        {missing > 0 && (
          <p className="mt-space-xs font-body-sm text-body-sm text-ink-muted">
            {missing === 1
              ? t('One year with missing days is left out, not drawn as zero.')
              : t('{count} years with missing days are left out, not drawn as zero.', { count: missing })}
          </p>
        )}
      </AppCard>

      <TrendCard metric={metric} trend={trend} minYears={data.min_trend_years} />

      <details>
        <summary className="cursor-pointer min-h-12 flex items-center font-label-md text-label-md font-semibold text-primary">
          {t('Show every year')}
        </summary>
        <ul className="flex flex-col gap-0.5">
          {[...series].reverse().map((p) => (
            <li key={p.year} className="flex gap-3 py-0.5">
              <span className="w-16 font-citation-mono text-citation-mono text-on-surface-variant">{p.year}</span>
              <span className={`font-body-md text-body-md ${p.value === null ? 'text-ink-muted' : 'text-ink'}`}>
                {p.value === null ? missingLabel(t) : formatClimate(p.value, metric)}
              </span>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}

export default function ClimatePage() {
  const t = useT();
  const { city, cityInfo } = useUiPrefs();
  const { loading, data, error, load } = useClimate();
  const [metric, setMetric] = useState<ClimateMetric>('rain');
  const [period, setPeriod] = useState<ClimatePeriod>('year');

  useEffect(() => {
    void load(city);
  }, [city, load]);

  const cityName = t(cityInfo.name);
  const ready = data && data.status === 'ok' && (data.annual?.length ?? 0) > 0;

  return (
    <PageFrame>
      <PageHeader
        title="Climate trends"
        subtitle={t('How rainfall and temperature in {city} have changed over about 30 years.', { city: cityName })}
      />
      <div className="mt-space-lg flex flex-col gap-space-md">
        {loading ? (
          <LoadingPanel text="Fetching the climate history…" />
        ) : error ? (
          <ErrorPanel icon="wifi_off" title="Climate trends unavailable" message={error.message} onRetry={() => void load(city)} />
        ) : data && !ready ? (
          <>
            <AppCard className="!bg-surface-container-low !border-outline-variant">
              <div className="flex items-center gap-3">
                <IconDisc icon="help" color="rgb(var(--c-on-surface-variant))" />
                <div className="font-label-md text-label-md font-bold text-ink">{t('No climate history')}</div>
              </div>
              <p className="mt-space-sm font-body-md text-body-md text-on-surface">
                {t("The climate history for {city} isn't available right now — this can't be read as no change.", {
                  city: cityName,
                })}
              </p>
            </AppCard>
            <ClimateSource data={data} />
          </>
        ) : data ? (
          <>
            <ClimateBody data={data} metric={metric} period={period} onMetric={setMetric} onPeriod={setPeriod} />
            <ClimateSource data={data} />
          </>
        ) : null}
      </div>
    </PageFrame>
  );
}
