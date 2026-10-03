// Forecast — the pics/ mockup's Forecast (mobile forecast_page.dart): a
// "Days | Hourly" pill switch. Days is GET /forecast/daily's list (up to 10
// days; open a day for its rain, wind, humidity, UV and sun times), Hourly is
// /forecast/hourly's next 24 hours as a strip under a temperature curve.
// Every figure is the feed's own, never generated. A backend from before
// those routes (404) gets the /facts rows (today, tonight, tomorrow) and the
// banner that hands a 5-day question to Chat, as before. Saved figures
// (backend unreachable) show under a banner saying when they were saved.
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageFrame from '../components/PageFrame';
import {
  AppCard,
  ErrorPanel,
  Icon,
  IconDisc,
  InfoBanner,
  LoadingPanel,
  PageHeader,
  SavedDataBanner,
} from '../components/ui';
import WeatherGlyph from '../components/WeatherGlyph';
import {
  factCondition,
  factNumber,
  factText,
  figure,
  figureText,
  type FactsResult,
  type ForecastDay,
  type ForecastSeries,
} from '../lib/facts';
import {
  calendarDate,
  dayMonth as calendarDayMonth,
  forecastDayName,
  hoursMinutes,
  istClock,
  istDayMonth,
  millimetres,
  savedTimeLabel,
  sentenceCase,
} from '../lib/format';
import { useChat } from '../state/ChatContext';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useWeather } from '../state/WeatherContext';
import { useT, type T } from '../lib/i18n';

type View = 'days' | 'hourly';

interface Period {
  label: string;
  result: FactsResult | null;
  offset: number;
  night: boolean;
}

/** "27 Sep" with the month in the app language. */
const dayMonth = (t: T, s: string) => s.replace(/[A-Z][a-z]{2}/, (m) => t(m));

const pct = (v: number | null) => (v === null ? '—' : `${Math.round(v)}%`);

/** One /forecast/daily day: name + date | glyph | high / low + condition |
 *  rain chance; opened, the rest of its figures. */
function DayTile({ day, open, onToggle }: { day: ForecastDay; open: boolean; onToggle: () => void }) {
  const t = useT();
  const { toCelsiusValue } = useUiPrefs();
  const high = figure(day, 'high_c');
  const low = figure(day, 'low_c');
  const rain = figure(day, 'rain_probability_pct');
  const date = calendarDate(figureText(day, 'date'));
  const name = forecastDayName(t, figureText(day, 'label') ?? 'later', date);
  const condition = figureText(day, 'condition_label');
  // Read out as a sentence: on screen the rain chance is a droplet and a
  // number, which a screen reader would read as a bare "15%".
  const spoken = t('{day}, {date}: {condition}, high {high}, low {low}, {rain}% chance of rain', {
    day: name,
    date: date ? calendarDayMonth(t, date) : '',
    condition: condition ?? '',
    high: high === null ? '—' : `${toCelsiusValue(high)}°`,
    low: low === null ? '—' : `${toCelsiusValue(low)}°`,
    rain: rain === null ? '—' : Math.round(rain),
  });
  return (
    <AppCard pad="p-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-label={spoken}
        className="w-full flex flex-wrap items-center gap-x-space-md gap-y-1 px-space-md py-3 text-left rounded-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
      >
        <span className="w-24 sm:w-32 shrink-0">
          <span className="block font-label-md text-label-md font-bold text-ink">{name}</span>
          {date && <span className="block font-body-sm text-body-sm text-ink-muted">{calendarDayMonth(t, date)}</span>}
        </span>
        <span className="flex flex-1 min-w-[12rem] items-center gap-3">
          <WeatherGlyph condition={figureText(day, 'condition')} size={36} />
          <span className="flex-1 min-w-0">
            <span className="block font-label-md text-label-md font-semibold text-ink">
              {high === null ? '—' : toCelsiusValue(high)}° / {low === null ? '—' : toCelsiusValue(low)}°
            </span>
            <span className="block font-body-sm text-body-sm text-ink-muted line-clamp-2">{sentenceCase(condition)}</span>
          </span>
          <span className="flex items-center gap-0.5 font-body-sm text-body-sm font-semibold text-ink">
            <Icon name="water_drop" size={14} className="text-primary" />
            {pct(rain)}
          </span>
          <Icon name={open ? 'expand_less' : 'expand_more'} size={20} className="text-ink-muted" />
        </span>
      </button>
      {open && (
        <div className="mx-space-md mb-space-md pt-3 border-t border-card-border">
          <DayFigures day={day} />
        </div>
      )}
    </AppCard>
  );
}

/** An opened day's figures, three to a row (two on narrow screens), then
 *  its night. */
function DayFigures({ day }: { day: ForecastDay }) {
  const t = useT();
  const rainMm = figure(day, 'rain_mm');
  const wind = figure(day, 'wind_kmh');
  const uv = figure(day, 'uv_index');
  const sunrise = figureText(day, 'sunrise');
  const sunset = figureText(day, 'sunset');
  const daylight = sunrise && sunset ? (Date.parse(sunset) - Date.parse(sunrise)) / 60_000 : NaN;
  const night = figureText(day, 'night_condition_label');
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Figure icon="umbrella" label="Rain chance" value={pct(figure(day, 'rain_probability_pct'))} />
        <Figure icon="water_drop" label="Rainfall" value={rainMm === null ? '—' : millimetres(rainMm)} />
        <Figure icon="air" label="Wind" value={wind === null ? '—' : `${Math.round(wind)} km/h`} />
        <Figure icon="humidity_percentage" label="Humidity" value={pct(figure(day, 'humidity_pct'))} />
        <Figure icon="wb_sunny" label="UV index" value={uv === null ? '—' : String(Math.round(uv))} />
        <Figure icon="timelapse" label="Daylight" value={Number.isFinite(daylight) ? hoursMinutes(t, daylight) : '—'} />
        <Figure icon="wb_twilight" label="Sunrise" value={istClock(sunrise) || '—'} />
        <Figure icon="nights_stay" label="Sunset" value={istClock(sunset) || '—'} />
        <Figure icon="umbrella" label="Rain at night" value={pct(figure(day, 'night_rain_probability_pct'))} />
      </div>
      {night && (
        <div className="mt-3 flex items-center gap-space-sm font-body-sm text-body-sm text-ink-muted">
          <WeatherGlyph condition={figureText(day, 'night_condition')} night size={22} />
          {t('Night: {condition}', { condition: night })}
        </div>
      )}
    </>
  );
}

const COLUMN = 58;
const CURVE = 64;

/** The next 24 hours: a temperature curve over a row of hour columns (time,
 *  glyph, rain chance), scrolled sideways together. A caption marks the
 *  first hour ("Now") and each new day. */
function HourlyStrip({ hourly }: { hourly: ForecastSeries }) {
  const t = useT();
  const { toCelsiusValue, toCelsiusLabel } = useUiPrefs();
  const hours = hourly.entries;
  const first = calendarDate(figureText(hours[0], 'date'));
  const temps = hours.map((h) => figure(h, 'temp_c'));
  const known = temps.filter((c): c is number => c !== null);
  const lo = Math.min(...known);
  const hi = Math.max(...known);
  const top = 24; // room for a label over the highest point
  const bottom = CURVE - 6;
  const at = (i: number) => {
    const c = temps[i];
    if (c === null) return null;
    const y = hi === lo ? (top + bottom) / 2 : bottom - ((c - lo) / (hi - lo)) * (bottom - top);
    return { x: COLUMN * (i + 0.5), y };
  };
  // A smooth line through the known hours; a missing hour breaks it.
  let path = '';
  let prev: { x: number; y: number } | null = null;
  for (let i = 0; i < hours.length; i++) {
    const p = at(i);
    if (!p) {
      prev = null;
      continue;
    }
    if (!prev) path += `M${p.x},${p.y}`;
    else {
      const mid = (prev.x + p.x) / 2;
      path += `C${mid},${prev.y} ${mid},${p.y} ${p.x},${p.y}`;
    }
    prev = p;
  }

  const captionFor = (i: number) => {
    if (i === 0) return t('Now');
    const date = figureText(hours[i], 'date');
    if (date === figureText(hours[i - 1], 'date')) return null;
    const d = calendarDate(date);
    const label = first && d && d.getTime() - first.getTime() === 86_400_000 ? 'tomorrow' : '';
    return forecastDayName(t, label, d);
  };

  const width = hours.length * COLUMN;
  return (
    <AppCard wash pad="py-3.5">
      <div className="overflow-x-auto px-space-sm" tabIndex={0} role="group" aria-label={t('Hourly')}>
        <div style={{ width }}>
          <div className="flex" aria-hidden="true">
            {hours.map((_, i) => (
              <span
                key={i}
                style={{ width: COLUMN }}
                className="shrink-0 truncate text-center font-body-sm text-[11px] leading-4 font-bold text-ink"
              >
                {captionFor(i)}
              </span>
            ))}
          </div>
          <svg width={width} height={CURVE} aria-hidden="true" className="block">
            <path d={path} fill="none" stroke="rgb(var(--c-primary))" strokeWidth={2} strokeLinecap="round" />
            {hours.map((_, i) => {
              const p = at(i);
              if (!p) return null;
              return (
                <g key={i}>
                  <circle cx={p.x} cy={p.y} r={3} fill="rgb(var(--c-primary))" />
                  <text
                    x={p.x}
                    y={p.y - 7}
                    textAnchor="middle"
                    className="font-label-md"
                    fontSize={13}
                    fontWeight={600}
                    fill="rgb(var(--c-ink))"
                  >
                    {toCelsiusValue(temps[i]!)}°
                  </text>
                </g>
              );
            })}
          </svg>
          <div className="flex">
            {hours.map((h, i) => {
              const temp = figure(h, 'temp_c');
              const rain = figure(h, 'rain_probability_pct');
              const time = figureText(h, 'local_time') ?? '';
              return (
                <div
                  key={i}
                  role="img"
                  aria-label={t('{time}: {temp}, {condition}, {rain}% chance of rain', {
                    time,
                    temp: temp === null ? '—' : toCelsiusLabel(temp),
                    condition: figureText(h, 'condition_label') ?? '',
                    rain: rain === null ? '—' : Math.round(rain),
                  })}
                  style={{ width: COLUMN }}
                  className="shrink-0 flex flex-col items-center gap-0.5"
                >
                  <WeatherGlyph condition={figureText(h, 'condition')} night={h.is_daytime === false} size={28} />
                  <span className="font-body-sm text-body-sm text-ink">{time}</span>
                  <span className="flex items-center font-body-sm text-[11px] text-ink-muted">
                    <Icon name="water_drop" size={11} className="text-primary" />
                    {pct(rain)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AppCard>
  );
}

/** Label + date | glyph | high / low + condition — a /facts period, for a
 *  backend without /forecast/daily. */
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
        <span>{t(label)}</span>
      </div>
      <div className="mt-0.5 font-headline-sm text-[16px] text-ink">{value}</div>
    </div>
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
      className={`flex-1 min-h-12 py-2.5 rounded-full font-label-md text-label-md transition-colors ${
        v === value ? 'bg-accent-gradient text-on-primary font-bold' : 'text-ink font-medium hover:bg-tint-strong'
      }`}
    >
      {t(label)}
    </button>
  );
  return (
    <div role="tablist" className="flex gap-1 p-1 rounded-full bg-tint">
      {tab('days', 'Days')}
      {tab('hourly', 'Hourly')}
    </div>
  );
}

export default function ForecastPage() {
  const [view, setView] = useState<View>('days');
  // The day list's opened row.
  const [open, setOpen] = useState<number | null>(null);
  const weather = useWeather();
  const { askInChat } = useChat();
  const { cityInfo, personaInfo } = useUiPrefs();
  const t = useT();
  const city = t(cityInfo.name);
  const navigate = useNavigate();

  let body;
  if (view === 'days') {
    if (weather.hasDaily) {
      const daily = weather.daily!;
      body = (
        <>
          {daily.entries.map((day, i) => (
            <DayTile
              key={figureText(day, 'date') ?? i}
              day={day}
              open={open === i}
              onToggle={() => setOpen(open === i ? null : i)}
            />
          ))}
          <ProvenanceCard source={daily.source} />
        </>
      );
    } else if (weather.dailyPending) {
      body = <LoadingPanel text="Loading the forecast…" />;
    } else if (weather.error) {
      body = (
        <ErrorPanel
          icon="wifi_off"
          title="Forecast unavailable"
          message={weather.error.message}
          messageArgs={weather.error.args}
          onRetry={weather.refresh}
        />
      );
    } else if (!weather.today) {
      body = <LoadingPanel text="Loading the forecast…" />;
    } else {
      const periods: Period[] = [
        { label: 'Today', result: weather.today, offset: 0, night: false },
        { label: 'Tonight', result: weather.tonight, offset: 0, night: true },
        { label: 'Tomorrow', result: weather.tomorrow, offset: 1, night: false },
      ];
      body = periods.map((p) => <DayRow key={p.label} p={p} />);
    }
  } else if (weather.hasHourly) {
    body = (
      <>
        <HourlyStrip hourly={weather.hourly!} />
        <ProvenanceCard source={weather.hourly!.source} />
      </>
    );
  } else if (weather.hourlyPending) {
    body = <LoadingPanel text="Loading the hourly forecast…" />;
  } else if (weather.hourlyError && weather.hourlyError.status !== 404) {
    body = (
      <ErrorPanel
        icon="wifi_off"
        title="Hourly forecast unavailable"
        message={weather.hourlyError.message}
        messageArgs={weather.hourlyError.args}
        onRetry={weather.refresh}
      />
    );
  } else {
    body = (
      <AppCard>
        <p className="font-body-md text-body-md text-ink-muted">
          {weather.hourlyError
            ? t("This weather service doesn't serve an hourly forecast yet.")
            : t('No hourly forecast for {city} right now.', { city })}
        </p>
      </AppCard>
    );
  }

  return (
    <PageFrame>
      <PageHeader title="Forecast" subtitle={personaInfo.forecastLead} />
      {weather.savedAt && (
        <div className="mt-space-md">
          <SavedDataBanner
            message="Couldn't reach the weather service. These figures were saved at {time}."
            messageArgs={{ time: savedTimeLabel(t, weather.savedAt) }}
            onRetry={weather.refresh}
          />
        </div>
      )}
      <div className="mt-space-md">
        <Switch value={view} onChange={setView} />
      </div>
      <div className="mt-space-md flex flex-col gap-2.5">{body}</div>
      <div className="mt-space-md flex flex-col gap-space-sm">
        {!weather.hasDaily && !weather.dailyPending && (
          <InfoBanner
            icon={personaInfo.icon}
            title="Need more days?"
            body={t('Ask for a 5-day forecast for {city} in Chat.', { city })}
            onClick={() => askInChat(t('5-day forecast for {city}', { city }))}
          />
        )}
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
