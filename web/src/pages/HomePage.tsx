// Home — the pics/ persona mockups' Home (mobile home_page.dart): a persona
// greeting ("Good morning, Farmer!"), the current-conditions card, today's
// rain so far and daylight, four shortcut tiles, the outlook strip, the
// persona's illustrated panel and its Quick Actions. Every figure is live
// from the backend (WeatherContext): /facts for the card and the rain,
// /forecast/daily for the sun times and the strip's five days. A backend
// without /forecast/daily gets today / tonight / tomorrow from /facts in the
// strip, and the 5-Day tile asks Chat instead. When the backend can't be
// reached, the saved figures show under a banner saying when they were saved.
import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import PageFrame from '../components/PageFrame';
import { PersonaScenery } from '../components/scenery/Scenery';
import {
  ActionRow,
  AppCard,
  ErrorPanel,
  Icon,
  IconDisc,
  LiveBadge,
  LoadingPanel,
  SavedDataBanner,
  SectionTitle,
} from '../components/ui';
import WeatherGlyph from '../components/WeatherGlyph';
import { question, questionTitle } from '../data/personas';
import {
  factCondition,
  factIsLive,
  factNumber,
  factText,
  figure,
  figureText,
  type FactsResult,
  type ForecastDay,
  type Figures,
} from '../lib/facts';
import {
  calendarDate,
  forecastDayName,
  hoursMinutes,
  isNightIst,
  savedTimeLabel,
  istClock,
  istHour,
  istMinuteOfDay,
  istTime,
  millimetres,
  rainCategoryLabel,
  sentenceCase,
} from '../lib/format';
import { useChat } from '../state/ChatContext';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useWeather } from '../state/WeatherContext';
import { useT, type T } from '../lib/i18n';

/** "Good afternoon, Farmer!" — the persona's role, per the mockups. */
function greeting(t: T, hour: number, role: string) {
  const text = hour < 12 ? 'Good morning, {role}!' : hour < 17 ? 'Good afternoon, {role}!' : 'Good evening, {role}!';
  return t(text, { role: t(role) });
}

function Stat({ icon, label, value }: { icon: string; label: string; value: string }) {
  const t = useT();
  return (
    <div className="flex items-center gap-1.5 font-body-sm text-body-sm">
      <Icon name={icon} size={15} className="text-ink-muted" />
      <span className="flex-1 truncate text-ink-muted">{t(label)}</span>
      <span className="font-semibold text-ink">{value}</span>
    </div>
  );
}

/** The big current-conditions card. */
function NowCard() {
  const t = useT();
  const weather = useWeather();
  const { cityInfo, toCelsiusLabel } = useUiPrefs();
  const c = weather.current;

  let body;
  if (weather.error) {
    body = (
      <ErrorPanel
        icon="wifi_off"
        title="Live conditions unavailable"
        message={weather.error.message}
        messageArgs={weather.error.args}
        onRetry={weather.refresh}
      />
    );
  } else if (!c) {
    body = <LoadingPanel text={t('Loading live conditions for {city}…', { city: t(cityInfo.name) })} />;
  } else if (!c.facts) {
    body = (
      <p className="font-body-md text-body-md text-ink-muted">
        {c.message ?? t('No current conditions for this city right now.')}
      </p>
    );
  } else {
    const temp = factNumber(c, 'temp_c');
    const feels = factNumber(c, 'feels_like_c');
    const humidity = factNumber(c, 'humidity_pct');
    const wind = factNumber(c, 'wind_kmh');
    const rain = factNumber(weather.today, 'rain_probability_pct');
    const issued = factText(c, 'issued');
    body = (
      <>
        <div className="flex items-center gap-3">
          <WeatherGlyph condition={factCondition(c)} night={isNightIst()} size={64} />
          <div className="flex-1 min-w-0">
            <div className="font-headline-xl text-[34px] leading-tight font-bold text-ink">
              {temp === null ? '—' : toCelsiusLabel(temp)}
            </div>
            <div className="font-body-md text-body-md text-ink-muted line-clamp-2">
              {sentenceCase(c.condition_label)}
            </div>
            {feels !== null && (
              <div className="font-body-sm text-body-sm text-ink-muted">{t('Feels like {temp}', { temp: toCelsiusLabel(feels) })}</div>
            )}
          </div>
          <div className="w-px self-stretch my-1 bg-card-border" />
          <div className="flex-1 min-w-0 flex flex-col gap-1.5">
            <Stat icon="water_drop" label="Humidity" value={humidity === null ? '—' : `${Math.round(humidity)}%`} />
            <Stat icon="air" label="Wind" value={wind === null ? '—' : `${Math.round(wind)} km/h`} />
            <Stat icon="umbrella" label="Rain" value={rain === null ? '—' : `${Math.round(rain)}%`} />
          </div>
        </div>
        <div className="mt-3 flex items-center gap-space-sm">
          <LiveBadge live={factIsLive(c)} />
          {issued && (
            <span className="truncate font-citation-mono text-citation-mono text-ink-muted">
              {t('Updated {time}', { time: istTime(issued) })}
            </span>
          )}
        </div>
      </>
    );
  }
  return <AppCard wash>{body}</AppCard>;
}

/** A small card's icon + title row. */
function CardTitle({ icon, title, trailing }: { icon: string; title: string; trailing?: ReactNode }) {
  const t = useT();
  return (
    <div className="flex items-center gap-1.5">
      <Icon name={icon} size={16} className="text-primary" />
      <span className="flex-1 truncate font-label-md text-label-md font-semibold text-ink">{t(title)}</span>
      {trailing}
    </div>
  );
}

/** Millimetres since local midnight with the IMD category, or the last 24
 *  hours' total when the backend had no hourly history to sum. */
function RainCard({ rain, saved }: { rain: Figures; saved: boolean }) {
  const t = useT();
  const sinceMidnight = figure(rain, 'rain_so_far_mm');
  const mm = sinceMidnight ?? figure(rain, 'rain_last_24h_mm');
  const category = rainCategoryLabel(figureText(rain, 'rain_category'));
  return (
    <AppCard pad="p-3.5">
      <CardTitle
        icon="water_drop"
        title="Rain so far"
        trailing={
          saved ? <LiveBadge live={false} notLiveText="SAVED" /> : rain.is_live === true ? null : <LiveBadge live={false} />
        }
      />
      <div className="mt-2 font-headline-sm text-headline-sm text-ink">{mm === null ? '—' : millimetres(mm)}</div>
      {category && <div className="font-body-sm text-body-sm text-ink-muted">{t(category)}</div>}
      <div className="font-body-sm text-body-sm text-ink-muted">
        {t(sinceMidnight !== null ? 'Since midnight' : 'In the last 24 hours')}
      </div>
    </AppCard>
  );
}

/** Day length with a bar for how much of it has passed, and the sunrise and
 *  sunset times. The bar reads the IST clock time against the two, once a
 *  minute. */
function DaylightCard({ sunrise, sunset, rise, set }: { sunrise: string; sunset: string; rise: number; set: number }) {
  const t = useT();
  const [minute, setMinute] = useState(() => istMinuteOfDay(new Date().toISOString()) ?? 0);
  useEffect(() => {
    const id = window.setInterval(() => setMinute(istMinuteOfDay(new Date().toISOString()) ?? 0), 60_000);
    return () => window.clearInterval(id);
  }, []);
  const passed = Math.min(1, Math.max(0, (minute - rise) / (set - rise)));
  const time = (icon: string, label: string, iso: string) => (
    <span className="inline-flex items-center gap-0.5 font-body-sm text-body-sm text-ink-muted">
      <Icon name={icon} size={13} className="text-primary" />
      <span className="sr-only">{t(label)}</span>
      {istClock(iso)}
    </span>
  );
  return (
    <AppCard pad="p-3.5">
      <CardTitle icon="wb_twilight" title="Daylight" />
      <div className="mt-2 font-headline-sm text-headline-sm text-ink">{hoursMinutes(t, set - rise)}</div>
      <div
        className="mt-2 h-1.5 rounded-full bg-tint overflow-hidden"
        role="progressbar"
        aria-label={t('Daylight')}
        aria-valuenow={Math.round(passed * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${passed * 100}%` }} />
      </div>
      <div className="mt-1.5 flex flex-wrap justify-between gap-x-2">
        {time('arrow_upward', 'Sunrise', sunrise)}
        {time('arrow_downward', 'Sunset', sunset)}
      </div>
    </AppCard>
  );
}

/** Rain so far today (/facts' `rain_so_far`) and today's daylight
 *  (/forecast/daily's first day), side by side; either alone fills the row. */
function TodayCards() {
  const weather = useWeather();
  const rain = weather.error ? null : weather.current?.rain_so_far;
  const today = weather.hasDaily ? weather.daily!.entries[0] : null;
  const sunrise = figureText(today, 'sunrise');
  const sunset = figureText(today, 'sunset');
  const rise = istMinuteOfDay(sunrise);
  const set = istMinuteOfDay(sunset);
  const daylight = sunrise && sunset && rise !== null && set !== null && set > rise;
  if (!rain && !daylight) return null;
  return (
    <div className={`grid gap-2.5 ${rain && daylight ? 'grid-cols-2' : ''}`}>
      {rain && <RainCard rain={rain} saved={!!weather.current?.savedAt} />}
      {daylight && <DaylightCard sunrise={sunrise} sunset={sunset} rise={rise} set={set} />}
    </div>
  );
}

function DailyCell({ day }: { day: ForecastDay }) {
  const t = useT();
  const { toCelsiusValue } = useUiPrefs();
  const high = figure(day, 'high_c');
  const low = figure(day, 'low_c');
  return (
    <div className="flex flex-col items-center gap-2 text-center min-w-0">
      <span className="truncate max-w-full font-label-md text-label-md font-semibold text-ink">
        {forecastDayName(t, figureText(day, 'label') ?? 'later', calendarDate(figureText(day, 'date')))}
      </span>
      <WeatherGlyph condition={figureText(day, 'condition')} size={30} />
      <span className="font-body-sm text-body-sm text-ink-muted whitespace-nowrap">
        {high !== null && <span className="font-semibold text-ink">{toCelsiusValue(high)}° </span>}
        {low !== null && `${toCelsiusValue(low)}°`}
      </span>
    </div>
  );
}

function DayCell({ label, result, night = false }: { label: string; result: FactsResult | null; night?: boolean }) {
  const t = useT();
  const { toCelsiusValue } = useUiPrefs();
  const high = factNumber(result, 'high_c');
  const low = factNumber(result, 'low_c');
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <span className="font-label-md text-label-md font-semibold text-ink">{t(label)}</span>
      <WeatherGlyph condition={factCondition(result)} night={night} size={34} />
      {!result?.facts ? (
        <span className="font-body-sm text-body-sm text-ink-muted">—</span>
      ) : (
        // Tonight's high/low are the whole day's, so only the overnight low.
        <span className="font-body-sm text-body-sm text-ink-muted">
          {!night && high !== null && <span className="font-semibold text-ink">{toCelsiusValue(high)}° </span>}
          {low !== null && (night ? t('Low {temp}°', { temp: toCelsiusValue(low) }) : ` ${toCelsiusValue(low)}°`)}
        </span>
      )}
    </div>
  );
}

/** Five days from /forecast/daily in one card, like the mockup's day
 *  columns; today / tonight / tomorrow from /facts on an older backend. */
function OutlookStrip() {
  const t = useT();
  const weather = useWeather();
  if (weather.hasDaily) {
    return (
      <AppCard wash pad="px-space-sm py-3.5">
        <div className="grid grid-cols-5">
          {weather.daily!.entries.slice(0, 5).map((day, i) => (
            <DailyCell key={figureText(day, 'date') ?? i} day={day} />
          ))}
        </div>
      </AppCard>
    );
  }
  if (weather.dailyPending) return <LoadingPanel text="Loading the outlook…" />;
  if (weather.error) {
    return (
      <AppCard>
        <p className="font-body-sm text-body-sm text-ink-muted">
          {t('The outlook will appear once the weather service answers.')}
        </p>
      </AppCard>
    );
  }
  if (!weather.today) return <LoadingPanel text="Loading the outlook…" />;
  return (
    <AppCard wash pad="px-space-sm py-3.5">
      <div className="grid grid-cols-3">
        <DayCell label="Today" result={weather.today} />
        <DayCell label="Tonight" result={weather.tonight} night />
        <DayCell label="Tomorrow" result={weather.tomorrow} />
      </div>
    </AppCard>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const { askInChat } = useChat();
  const { hasDaily, savedAt, refresh } = useWeather();
  const { cityInfo, personaInfo: persona } = useUiPrefs();
  const [hour, setHour] = useState(() => istHour());
  const t = useT();
  const city = t(cityInfo.name);

  useEffect(() => {
    const id = window.setInterval(() => setHour(istHour()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const tiles: [string, string, () => void][] = [
    ['today', 'Today', () => navigate('/forecast')],
    ['date_range', '5-Day', hasDaily ? () => navigate('/forecast') : () => askInChat(t('5-day forecast for {city}', { city }))],
    ['warning', 'Alerts', () => navigate('/alerts')],
    ['chat', 'Chat', () => navigate('/chat')],
  ];

  return (
    <PageFrame footer="none" wide>
      <div className="flex items-center gap-3">
        <button
          type="button"
          title={t('Change persona')}
          aria-label={t('Change persona')}
          onClick={() => navigate('/persona')}
          className="rounded-full transition hover:scale-105"
        >
          <IconDisc icon={persona.icon} size={52} solid />
        </button>
        <div className="min-w-0">
          <h1 className="font-headline-sm text-headline-sm md:text-headline-md font-bold text-ink">
            {greeting(t, hour, persona.role)}
          </h1>
          <p className="font-body-sm text-body-sm md:text-body-md text-ink-muted">{t(persona.homeLead)}</p>
        </div>
      </div>

      {savedAt && (
        <div className="mt-space-md">
          <SavedDataBanner
            message="Couldn't reach the weather service. These figures were saved at {time}."
            messageArgs={{ time: savedTimeLabel(t, savedAt) }}
            onRetry={refresh}
          />
        </div>
      )}

      <div className="mt-space-md grid gap-x-space-lg gap-y-space-md lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <NowCard />
          <TodayCards />
          <div className="grid grid-cols-4 gap-2.5">
            {tiles.map(([icon, label, onClick]) => (
              <AppCard key={label} pad="py-3" onClick={onClick}>
                <span className="flex flex-col items-center gap-1.5">
                  <Icon name={icon} size={26} fill className="text-primary" />
                  <span className="truncate font-label-md text-label-md font-semibold text-ink">{t(label)}</span>
                </span>
              </AppCard>
            ))}
          </div>
          <div className="mt-3">
            <SectionTitle text="Forecast" action="See all" onAction={() => navigate('/forecast')} />
          </div>
          <OutlookStrip />
        </div>

        <div className="flex flex-col gap-space-sm">
          <div className="relative h-[132px] lg:h-[180px] overflow-hidden rounded-card bg-gradient-to-b from-sky-top to-sky-bottom">
            <PersonaScenery slot="panel" />
          </div>
          <div className="mt-space-md mb-1">
            <SectionTitle text="Quick Actions" />
          </div>
          {persona.quickActions.map((q) => (
            <ActionRow
              key={q.template}
              icon={q.icon}
              title={questionTitle(q, city, t)}
              onClick={() => askInChat(question(q, city, t))}
            />
          ))}
        </div>
      </div>
    </PageFrame>
  );
}
