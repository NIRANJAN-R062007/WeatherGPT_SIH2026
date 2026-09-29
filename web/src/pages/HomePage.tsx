// Home — the pics/ persona mockups' Home (mobile home_page.dart): a persona
// greeting ("Good morning, Farmer!"), the current-conditions card, four
// shortcut tiles, the outlook strip, the persona's illustrated panel and its
// Quick Actions. Every figure is live from GET /facts (WeatherContext).
// /facts serves today, tonight and tomorrow only, so the strip shows those
// three; longer ranges are one tap away as a Quick Action, which Chat
// answers through /ask.
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageFrame from '../components/PageFrame';
import { PersonaScenery } from '../components/scenery/Scenery';
import { ActionRow, AppCard, ErrorPanel, Icon, IconDisc, LiveBadge, LoadingPanel, SectionTitle } from '../components/ui';
import WeatherGlyph from '../components/WeatherGlyph';
import { question, questionTitle } from '../data/personas';
import { factCondition, factIsLive, factNumber, factText, type FactsResult } from '../lib/facts';
import { isNightIst, istHour, istTime, sentenceCase } from '../lib/format';
import { useChat } from '../state/ChatContext';
import { useUiPrefs } from '../state/UiPrefsContext';
import { useWeather } from '../state/WeatherContext';

/** "Good afternoon, Farmer!" — the persona's role, per the mockups. */
function greeting(hour: number, role: string) {
  const part = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
  return `Good ${part}, ${role}!`;
}

function Stat({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 font-body-sm text-body-sm">
      <Icon name={icon} size={15} className="text-ink-muted" />
      <span className="flex-1 truncate text-ink-muted">{label}</span>
      <span className="font-semibold text-ink">{value}</span>
    </div>
  );
}

/** The big current-conditions card. */
function NowCard() {
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
        onRetry={weather.refresh}
      />
    );
  } else if (!c) {
    body = <LoadingPanel text={`Loading live conditions for ${cityInfo.name}…`} />;
  } else if (!c.facts) {
    body = (
      <p className="font-body-md text-body-md text-ink-muted">
        {c.message ?? 'No current conditions for this city right now.'}
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
              <div className="font-body-sm text-body-sm text-ink-muted">Feels like {toCelsiusLabel(feels)}</div>
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
              Updated {istTime(issued)}
            </span>
          )}
        </div>
      </>
    );
  }
  return <AppCard wash>{body}</AppCard>;
}

function DayCell({ label, result, night = false }: { label: string; result: FactsResult | null; night?: boolean }) {
  const { toCelsiusValue } = useUiPrefs();
  const high = factNumber(result, 'high_c');
  const low = factNumber(result, 'low_c');
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <span className="font-label-md text-label-md font-semibold text-ink">{label}</span>
      <WeatherGlyph condition={factCondition(result)} night={night} size={34} />
      {!result?.facts ? (
        <span className="font-body-sm text-body-sm text-ink-muted">—</span>
      ) : (
        // Tonight's high/low are the whole day's, so only the overnight low.
        <span className="font-body-sm text-body-sm text-ink-muted">
          {!night && high !== null && <span className="font-semibold text-ink">{toCelsiusValue(high)}° </span>}
          {low !== null && (night ? `Low ${toCelsiusValue(low)}°` : ` ${toCelsiusValue(low)}°`)}
        </span>
      )}
    </div>
  );
}

/** Today / Tonight / Tomorrow in one card, like the mockup's day columns. */
function OutlookStrip() {
  const weather = useWeather();
  if (weather.error) {
    return (
      <AppCard>
        <p className="font-body-sm text-body-sm text-ink-muted">
          The outlook will appear once the weather service answers.
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
  const { cityInfo, personaInfo: persona } = useUiPrefs();
  const [hour, setHour] = useState(() => istHour());
  const city = cityInfo.name;

  useEffect(() => {
    const id = window.setInterval(() => setHour(istHour()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const tiles: [string, string, () => void][] = [
    ['today', 'Today', () => navigate('/forecast')],
    ['date_range', '5-Day', () => askInChat(`5-day forecast for ${city}`)],
    ['warning', 'Alerts', () => navigate('/alerts')],
    ['chat', 'Chat', () => navigate('/chat')],
  ];

  return (
    <PageFrame footer="none" wide>
      <div className="flex items-center gap-3">
        <button
          type="button"
          title="Change persona"
          aria-label="Change persona"
          onClick={() => navigate('/persona')}
          className="rounded-full transition hover:scale-105"
        >
          <IconDisc icon={persona.icon} size={52} solid />
        </button>
        <div className="min-w-0">
          <h1 className="font-headline-sm text-headline-sm md:text-headline-md font-bold text-ink">
            {greeting(hour, persona.role)}
          </h1>
          <p className="font-body-sm text-body-sm md:text-body-md text-ink-muted">{persona.homeLead}</p>
        </div>
      </div>

      <div className="mt-space-md grid gap-x-space-lg gap-y-space-md lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <NowCard />
          <div className="grid grid-cols-4 gap-2.5">
            {tiles.map(([icon, label, onClick]) => (
              <AppCard key={label} pad="py-3" onClick={onClick}>
                <span className="flex flex-col items-center gap-1.5">
                  <Icon name={icon} size={26} fill className="text-primary" />
                  <span className="truncate font-label-md text-label-md font-semibold text-ink">{label}</span>
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
              title={questionTitle(q, city)}
              onClick={() => askInChat(question(q, city))}
            />
          ))}
        </div>
      </div>
    </PageFrame>
  );
}
