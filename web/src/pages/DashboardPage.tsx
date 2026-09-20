import { useSearchParams } from 'react-router-dom';
import { fetchFacts } from '../api/client';
import type { Facts } from '../api/types';
import { CityPicker } from '../components/CityPicker';
import { MetaLine } from '../components/MetaLine';
import { Notice } from '../components/Notice';
import { Placeholder } from '../components/Placeholder';
import { Skeleton } from '../components/Skeleton';
import { formatTime } from '../i18n/format';
import { useT } from '../i18n/strings';
import { useQuery } from '../hooks/useQuery';
import { useCities } from '../state/CitiesContext';
import { useSettings } from '../state/SettingsContext';
import { ApiError } from '../api/client';

function conditionGlyph(condition?: string): 'sun' | 'cloud' | 'rain' | 'thunder' | 'wind' {
  if (!condition) return 'cloud';
  const c = condition.toLowerCase();
  if (c.includes('thunder')) return 'thunder';
  if (c.includes('rain')) return 'rain';
  if (c === 'clear' || c === 'mostly clear' || c.includes('clear')) return 'sun';
  if (c.includes('wind')) return 'wind';
  if (c.includes('cloud')) return 'cloud';
  return 'cloud';
}

function Stat({
  label,
  value,
  suffix,
  notReportedLabel,
}: {
  label: string;
  value: string | null;
  suffix?: string;
  notReportedLabel: string;
}) {
  return (
    <div className="bg-paper p-4">
      <p className="font-mono text-xs uppercase tracking-[0.14em] text-ink-faint">{label}</p>
      {value === null ? (
        <p className="mt-1 text-2xl text-ink-faint" aria-label={notReportedLabel}>
          —
        </p>
      ) : (
        <p className="mt-1 text-2xl tabular-nums text-ink">
          {value}
          {suffix && <span className="ml-1 font-mono text-sm text-ink-faint">{suffix}</span>}
        </p>
      )}
    </div>
  );
}

export function DashboardPage() {
  const { lang, defaultCity } = useSettings();
  const { status: citiesStatus, cities, byKey } = useCities();
  const [params, setParams] = useSearchParams();
  const t = useT(lang);

  const cityKey = params.get('city') ?? defaultCity;
  const city = byKey(cityKey);

  const setCity = (key: string) => {
    const next = new URLSearchParams(params);
    next.set('city', key);
    setParams(next, { replace: true });
  };

  const { status, data, error, reload } = useQuery(
    (signal) => fetchFacts(cityKey, lang, signal),
    [cityKey, lang],
  );

  if (citiesStatus === 'loading') {
    return <Skeleton kind="lines" count={4} />;
  }

  if (citiesStatus === 'error') {
    return (
      <Notice variant="error" onRetry={reload} retryLabel={t.retry}>
        {t.errNetwork}
      </Notice>
    );
  }

  const facts: Facts | undefined = status === 'ok' && 'facts' in data! ? data.facts : undefined;
  const hasMessage = status === 'ok' && data && 'message' in data;

  return (
    <div>
      <CityPicker
        cities={cities}
        value={cityKey}
        onChange={setCity}
        lang={lang}
        legend={t.city}
        name="dashboard-city"
      />

      <Placeholder ratio="3/1" glyph="skyline" label={t.cityImage} className="mt-4 w-full" />

      <div className="mt-6 grid gap-8 md:grid-cols-[14rem_1fr]">
        <div className="min-w-0">
          <MetaLine
            items={[
              city?.names[lang]?.toUpperCase(),
              facts?.issued ? formatTime(facts.issued, city?.timezone ?? 'Asia/Kolkata', lang) : undefined,
              facts?.source,
            ]}
            badge={
              facts && facts.is_live !== undefined
                ? { label: facts.is_live ? t.liveData : t.fixtureData, fixture: !facts.is_live }
                : undefined
            }
          />
          {city?.region.en && <p className="mt-2 text-sm text-ink-dim">{city.region[lang === 'ta' ? 'ta' : 'en'] ?? city.region.en}</p>}
        </div>

        <div className="min-w-0">
          {status === 'loading' && <Skeleton kind="stat" />}

          {status === 'error' && (
            <Notice variant="error" onRetry={reload} retryLabel={t.retry}>
              {error instanceof ApiError
                ? error.kind === 'timeout'
                  ? t.errTimeout
                  : error.kind === 'network'
                    ? t.errNetwork
                    : error.status === 429
                      ? t.errRate
                      : `${t.errHttp} (${error.status ?? '?'})`
                : t.errNetwork}
            </Notice>
          )}

          {hasMessage && status === 'ok' && 'message' in data! && (
            <Notice variant="refusal">{data.message}</Notice>
          )}

          {facts && (
            <>
              <div className="flex flex-wrap items-end gap-6 break-words">
                <p className="text-7xl font-medium tabular-nums text-ink md:text-8xl">
                  {facts.temp_c ?? '—'}
                  <span className="text-3xl align-top">°C</span>
                </p>
                <Placeholder ratio="1/1" glyph={conditionGlyph(facts.condition)} label={facts.condition ?? ''} className="h-16 w-16" />
              </div>
              <p className="mt-1 break-words text-2xl text-ink-dim">
                {status === 'ok' && 'condition_label' in data! ? data.condition_label : facts.condition}
              </p>

              <div className="mt-6 grid grid-cols-2 gap-px bg-line md:grid-cols-4">
                <Stat
                  label={t.feelsLike}
                  value={facts.feels_like_c !== undefined ? `${facts.feels_like_c}°C` : null}
                  notReportedLabel={t.notReported}
                />
                <Stat
                  label={t.humidity}
                  value={facts.humidity_pct !== undefined ? `${facts.humidity_pct}%` : null}
                  notReportedLabel={t.notReported}
                />
                <Stat
                  label={t.wind}
                  value={facts.wind_kmh !== undefined ? `${facts.wind_kmh} km/h` : null}
                  suffix={facts.wind_dir}
                  notReportedLabel={t.notReported}
                />
                <Stat
                  label={t.uvIndex}
                  value={facts.uv_index !== undefined ? `${facts.uv_index}` : null}
                  notReportedLabel={t.notReported}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
