// Best Time & What-if — plan.md §8 Phase 9, WIE-13: a best-window card (the
// longest suitable run of hours today or tomorrow) and a what-if comparison
// view (two named times of day, the lower-rain-chance one named), both from
// the Weather Intelligence Engine's deterministic rules (lib/intelligence.ts;
// services/orchestrator/weather_intelligence/). Nothing here is narrated by
// an LLM — every figure is read straight from the engine's result
// (plan.md §2 principle 7), the same discipline as Forecast and Alerts.
// Reached from the sidebar, a Forecast banner and a Chat banner.
import { useEffect, useState } from 'react';
import PageFrame from '../components/PageFrame';
import { AppCard, ErrorPanel, Icon, IconDisc, LoadingPanel, PageHeader, PillButton, SectionTitle, TagChip } from '../components/ui';
import { type Day, useBestWindow, useScenario } from '../lib/intelligence';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useT } from '../lib/i18n';

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}:00`);

/** The mockup's pill switch, reused from Forecast's "Days | Details". */
function DaySwitch({ value, onChange }: { value: Day; onChange: (v: Day) => void }) {
  const t = useT();
  const tab = (v: Day, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={v === value}
      onClick={() => onChange(v)}
      className={`flex-1 py-2.5 rounded-full font-label-md text-label-md transition-colors ${
        v === value ? 'bg-accent-gradient text-on-primary font-bold' : 'text-ink font-medium hover:bg-tint-strong'
      }`}
    >
      {t(label)}
    </button>
  );
  return (
    <div role="tablist" className="flex gap-1 p-1 rounded-full bg-tint">
      {tab('today', 'Today')}
      {tab('tomorrow', 'Tomorrow')}
    </div>
  );
}

function BestWindowCard({ city, day }: { city: string; day: Day }) {
  const t = useT();
  const { loading, data, error, load } = useBestWindow();

  useEffect(() => {
    void load(city, day);
  }, [city, day, load]);

  if (loading) return <LoadingPanel text="Finding the best window…" />;
  if (error) {
    return (
      <ErrorPanel icon="wifi_off" title="Best window unavailable" message={error.message} onRetry={() => void load(city, day)} />
    );
  }
  if (!data) return null;

  if (data.status === 'unavailable') {
    return (
      <AppCard className="!bg-surface-container-low !border-outline-variant">
        <div className="flex items-center gap-3">
          <IconDisc icon="help" color="rgb(var(--c-on-surface-variant))" />
          <div className="font-label-md text-label-md font-bold text-ink">{t('No hourly forecast to check')}</div>
        </div>
        <p className="mt-space-sm font-body-md text-body-md text-on-surface">
          {t(
            "There's no hourly forecast for {city} {day} right now — this can't be read as a suitable or unsuitable window.",
            { city: t(data.city_name), day: t(day) },
          )}
        </p>
      </AppCard>
    );
  }

  if (data.status === 'no_suitable_window') {
    return (
      <AppCard className="!bg-surface-container-low !border-outline-variant">
        <div className="flex items-center gap-3">
          <IconDisc icon="block" color="rgb(var(--c-on-surface-variant))" />
          <div className="font-label-md text-label-md font-bold text-ink">{t('No suitable window')}</div>
        </div>
        <p className="mt-space-sm font-body-md text-body-md text-on-surface">
          {t(
            "Every hour {day} in {city} was checked against rain under 20%, 20–32°C and wind under 25 km/h — none passed. That's a real result, not a guess.",
            { city: t(data.city_name), day: t(day) },
          )}
        </p>
      </AppCard>
    );
  }

  const w = data.window!;
  return (
    <AppCard wash>
      <div className="flex items-start gap-3">
        <IconDisc icon="check" solid size={36} />
        <div className="flex-1 min-w-0">
          <div className="font-headline-sm text-headline-sm font-bold text-ink">
            {w.start_local} – {w.end_local}
          </div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <TagChip icon="location_on">{data.city_name}</TagChip>
            <TagChip>{t('more suitable for being outdoors')}</TagChip>
          </div>
        </div>
      </div>
      <div className="mt-space-md grid grid-cols-3 gap-2">
        <Figure icon="thermostat" label="Avg temp" value={`${w.avg_temp_c}°C`} />
        <Figure icon="umbrella" label="Max rain chance" value={`${w.max_rain_probability_pct}%`} />
        <Figure icon="air" label="Max wind" value={`${w.max_wind_kmh} km/h`} />
      </div>
      {data.provenance && (
        <div className="mt-space-md pt-space-sm border-t border-outline-variant/40 font-citation-mono text-citation-mono text-on-surface-variant">
          {t('source')}: {data.provenance.source}
        </div>
      )}
    </AppCard>
  );
}

function Figure({ icon, label, value }: { icon: string; label: string; value: string }) {
  const t = useT();
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 font-body-sm text-body-sm text-ink-muted">
        <Icon name={icon} size={14} className="text-primary" />
        <span className="truncate">{t(label)}</span>
      </div>
      <div className="mt-0.5 font-headline-sm text-[16px] text-ink">{value}</div>
    </div>
  );
}

function ScenarioHourCard({
  time,
  result,
  better,
}: {
  time: string;
  result: { available: boolean; temp_c?: number; rain_probability_pct?: number; wind_kmh?: number; suitable?: boolean } | undefined;
  better: boolean;
}) {
  const t = useT();
  return (
    <AppCard className={better ? '!border-primary' : ''}>
      <div className="flex items-center gap-2">
        <span className="font-label-md text-label-md font-bold text-ink">{time}</span>
        {better && <TagChip tone="primary">{t('lower rain chance')}</TagChip>}
      </div>
      {!result || !result.available ? (
        <p className="mt-space-sm font-body-sm text-body-sm text-ink-muted">{t('Not available in this forecast.')}</p>
      ) : (
        <div className="mt-space-sm grid grid-cols-3 gap-2">
          <Figure icon="thermostat" label="Temp" value={`${result.temp_c}°C`} />
          <Figure icon="umbrella" label="Rain" value={`${result.rain_probability_pct}%`} />
          <Figure icon="air" label="Wind" value={`${result.wind_kmh} km/h`} />
        </div>
      )}
    </AppCard>
  );
}

function WhatIfView({ city, day }: { city: string; day: Day }) {
  const t = useT();
  const [timeA, setTimeA] = useState('09:00');
  const [timeB, setTimeB] = useState('17:00');
  const { loading, data, error, compare, reset } = useScenario();

  // A city/day switch invalidates a comparison already on screen.
  useEffect(() => {
    reset();
  }, [city, day, reset]);

  const byTime = Object.fromEntries((data?.hours ?? []).map((h) => [h.time, h]));

  return (
    <div className="flex flex-col gap-space-sm">
      <div className="flex flex-wrap items-center gap-space-sm">
        <select
          value={timeA}
          onChange={(e) => setTimeA(e.target.value)}
          className="px-3 py-2 rounded-lg bg-card border border-card-border font-label-md text-label-md text-ink"
        >
          {HOUR_OPTIONS.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
        <span className="font-body-sm text-body-sm text-ink-muted">vs</span>
        <select
          value={timeB}
          onChange={(e) => setTimeB(e.target.value)}
          className="px-3 py-2 rounded-lg bg-card border border-card-border font-label-md text-label-md text-ink"
        >
          {HOUR_OPTIONS.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
        <PillButton icon="compare_arrows" label="Compare" onClick={() => void compare(city, day, [timeA, timeB])} />
      </div>
      {loading && <LoadingPanel text="Comparing…" />}
      {error && <ErrorPanel icon="wifi_off" title="Comparison unavailable" message={error.message} onRetry={() => void compare(city, day, [timeA, timeB])} />}
      {data && data.status === 'unavailable' && (
        <AppCard className="!bg-surface-container-low !border-outline-variant">
          <p className="font-body-md text-body-md text-on-surface">
            {t("There's no hourly forecast for {city} {day} right now to compare against.", {
              city: t(data.city_name),
              day: t(day),
            })}
          </p>
        </AppCard>
      )}
      {data && data.status === 'ok' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
          <ScenarioHourCard time={timeA} result={byTime[timeA]} better={data.better_time === timeA} />
          <ScenarioHourCard time={timeB} result={byTime[timeB]} better={data.better_time === timeB} />
        </div>
      )}
    </div>
  );
}

export default function BestWindowPage() {
  const t = useT();
  const [day, setDay] = useState<Day>('today');
  const { cityInfo } = useUiPrefs();

  return (
    <PageFrame>
      <PageHeader
        title="Best Time & What-if"
        subtitle="When conditions are most suitable to be outdoors, and how two times of day compare — decided by rules, not the language model."
      />
      <div className="mt-space-md">
        <DaySwitch value={day} onChange={setDay} />
      </div>
      <div className="mt-space-md mb-space-sm">
        <SectionTitle text="Best window" />
      </div>
      <BestWindowCard city={cityInfo.key} day={day} />
      <div className="mt-space-lg mb-space-sm">
        <SectionTitle text="What if I go at a different time?" />
      </div>
      <WhatIfView city={cityInfo.key} day={day} />
      <div className="mt-space-lg flex items-start gap-1.5 px-3 py-2 rounded-xl bg-tint font-body-sm text-body-sm text-ink-muted">
        <Icon name="info" size={16} className="mt-0.5 text-primary" />
        <span>
          {t(
            'A window is "more suitable", never "safe" — rain under 20%, 20–32°C and wind under 25 km/h, checked against the hourly forecast, the same rules every time regardless of persona. A colour-code warning for {city} always comes from Alerts, not from here.',
            { city: t(cityInfo.name) },
          )}
        </span>
      </div>
    </PageFrame>
  );
}
