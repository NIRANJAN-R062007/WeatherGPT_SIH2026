// Forecast — the pics/ mockup's Forecast (mobile forecast_page.dart): a
// two-way switch over a list of day rows. GET /facts serves today, tonight
// and tomorrow (no hourly series, no structured 5-day breakdown), so the
// switch is "Days" (the rows) and "Details" (each period's figures plus
// provenance) rather than the mockup's "5 Days" / "Hourly"; the banner at
// the foot hands a 5-day question to Chat, where /ask narrates it.
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageFrame from '../components/PageFrame';
import { AppCard, ErrorPanel, Icon, IconDisc, InfoBanner, LiveBadge, LoadingPanel, PageHeader } from '../components/ui';
import WeatherGlyph from '../components/WeatherGlyph';
import { factCondition, factIsLive, factNumber, factText, type FactsResult } from '../lib/facts';
import { istDayMonth, sentenceCase } from '../lib/format';
import { useChat } from '../state/ChatContext';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useWeather } from '../state/WeatherContext';
import { useT, type T } from '../lib/i18n';

type View = 'days' | 'details';

interface Period {
  label: string;
  result: FactsResult | null;
  offset: number;
  night: boolean;
}

/** "27 Sep" with the month in the app language. */
const dayMonth = (t: T, s: string) => s.replace(/[A-Z][a-z]{2}/, (m) => t(m));

/** Label + date | glyph | high / low + condition. */
function DayRow({ p }: { p: Period }) {
  const t = useT();
  const { toCelsiusValue } = useUiPrefs();
  const r = p.result;
  const high = factNumber(r, 'high_c');
  const low = factNumber(r, 'low_c');
  let temps: string;
  if (!r?.facts) temps = '—';
  // Tonight's high/low are the whole day's — show only the low.
  else if (p.night) temps = low === null ? '—' : t('Low {temp}°', { temp: toCelsiusValue(low) });
  else temps = `${high === null ? '—' : toCelsiusValue(high)}° / ${low === null ? '—' : toCelsiusValue(low)}°`;

  return (
    <AppCard pad="px-space-md py-3">
      <div className="flex items-center gap-space-md">
        <div className="w-24 sm:w-32 shrink-0">
          <div className="font-label-md text-label-md font-bold text-ink">{t(p.label)}</div>
          <div className="font-body-sm text-body-sm text-ink-muted">
            {dayMonth(t, istDayMonth(factText(r, 'issued'), p.offset))}
          </div>
        </div>
        <WeatherGlyph condition={factCondition(r)} night={p.night} size={40} />
        <div className="flex-1 min-w-0">
          <div className="font-label-md text-label-md font-semibold text-ink">{temps}</div>
          <div className="font-body-sm text-body-sm text-ink-muted line-clamp-2">
            {r?.facts ? sentenceCase(r.condition_label) : (r?.message ?? t('No forecast for this period.'))}
          </div>
        </div>
      </div>
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

/** One period's figures, as served. */
function DetailCard({ p }: { p: Period }) {
  const t = useT();
  const { toCelsiusLabel } = useUiPrefs();
  const r = p.result;
  const high = factNumber(r, 'high_c');
  const low = factNumber(r, 'low_c');
  const rain = factNumber(r, 'rain_probability_pct');
  return (
    <AppCard>
      <div className="flex items-center gap-3">
        <WeatherGlyph condition={factCondition(r)} night={p.night} size={32} />
        <span className="flex-1 font-label-md text-label-md font-bold text-ink">
          {t(p.label)}, {dayMonth(t, istDayMonth(factText(r, 'issued'), p.offset))}
        </span>
        {r?.facts && <LiveBadge live={factIsLive(r)} />}
      </div>
      {!r?.facts ? (
        <p className="mt-3 font-body-sm text-body-sm text-ink-muted">{r?.message ?? t('No forecast for this period.')}</p>
      ) : (
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Figure icon="umbrella" label="Rain chance" value={rain === null ? '—' : `${Math.round(rain)}%`} />
          {p.night ? (
            <>
              <Figure icon="nights_stay" label="Overnight low" value={low === null ? '—' : toCelsiusLabel(low)} />
              <Figure icon="cloud" label="Sky" value={sentenceCase(r.condition_label)} />
            </>
          ) : (
            <>
              <Figure icon="thermostat" label="High" value={high === null ? '—' : toCelsiusLabel(high)} />
              <Figure icon="thermostat_auto" label="Low" value={low === null ? '—' : toCelsiusLabel(low)} />
            </>
          )}
        </div>
      )}
    </AppCard>
  );
}

function ProvenanceCard({ source }: { source: string | null }) {
  const t = useT();
  return (
    <AppCard>
      <div className="flex items-start gap-3">
        <IconDisc icon="verified" size={36} />
        <div>
          <div className="font-label-md text-label-md font-bold text-ink">{t('Forecast Provenance')}</div>
          <p className="mt-0.5 font-body-sm text-body-sm text-ink-muted">
            {source
              ? t(
                  'As served by {source}. Every figure above is read directly from that response — never generated by the language model.',
                  { source },
                )
              : t(
                  'Every figure on this page is read directly from the forecast feed — never generated by the language model.',
                )}
          </p>
        </div>
      </div>
    </AppCard>
  );
}

/** The mockup's "5 Days | Hourly" pill switch. */
function Switch({ value, onChange }: { value: View; onChange: (v: View) => void }) {
  const t = useT();
  const tab = (v: View, label: string) => (
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
      {tab('days', 'Days')}
      {tab('details', 'Details')}
    </div>
  );
}

export default function ForecastPage() {
  const [view, setView] = useState<View>('days');
  const weather = useWeather();
  const { askInChat } = useChat();
  const { cityInfo, personaInfo } = useUiPrefs();
  const t = useT();
  const city = t(cityInfo.name);
  const navigate = useNavigate();

  let body;
  if (weather.error) {
    body = (
      <ErrorPanel icon="wifi_off" title="Forecast unavailable" message={weather.error.message} onRetry={weather.refresh} />
    );
  } else if (!weather.today) {
    body = <LoadingPanel text="Loading the forecast…" />;
  } else {
    const periods: Period[] = [
      { label: 'Today', result: weather.today, offset: 0, night: false },
      { label: 'Tonight', result: weather.tonight, offset: 0, night: true },
      { label: 'Tomorrow', result: weather.tomorrow, offset: 1, night: false },
    ];
    body = (
      <>
        {periods.map((p) =>
          view === 'days' ? <DayRow key={p.label} p={p} /> : <DetailCard key={p.label} p={p} />,
        )}
        {view === 'details' && <ProvenanceCard source={factText(weather.today, 'source')} />}
      </>
    );
  }

  return (
    <PageFrame>
      <PageHeader title="Forecast" subtitle={personaInfo.forecastLead} />
      <div className="mt-space-md">
        <Switch value={view} onChange={setView} />
      </div>
      <div className="mt-space-md flex flex-col gap-2.5">{body}</div>
      <div className="mt-space-md flex flex-col gap-space-sm">
        <InfoBanner
          icon={personaInfo.icon}
          title="Need more days?"
          body={t('Ask for a 5-day forecast for {city} in Chat.', { city })}
          onClick={() => askInChat(t('5-day forecast for {city}', { city }))}
        />
        <InfoBanner
          icon="schedule"
          title="When's the best time to go outside?"
          body="See the best window today or tomorrow, and compare two times."
          onClick={() => navigate('/best-window')}
        />
      </div>
    </PageFrame>
  );
}
