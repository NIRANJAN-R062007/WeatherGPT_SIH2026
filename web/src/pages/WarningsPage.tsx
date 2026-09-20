import { useSearchParams } from 'react-router-dom';
import { ApiError, fetchWarning } from '../api/client';
import type { WarningColour } from '../api/types';
import { CityPicker } from '../components/CityPicker';
import { Notice } from '../components/Notice';
import { Placeholder } from '../components/Placeholder';
import { Reveal } from '../components/Reveal';
import { Skeleton } from '../components/Skeleton';
import { formatDateRange } from '../i18n/format';
import { useT } from '../i18n/strings';
import { useQuery } from '../hooks/useQuery';
import { useCities } from '../state/CitiesContext';
import { useSettings } from '../state/SettingsContext';

const BANNER_CLASSES: Record<WarningColour, string> = {
  green: 'border-imd-green bg-imd-green-tint',
  yellow: 'border-imd-yellow bg-imd-yellow-tint',
  orange: 'border-imd-orange bg-imd-orange-tint',
  red: 'border-imd-red bg-imd-red-tint',
};

const SWATCH_CLASSES: Record<WarningColour, string> = {
  green: 'bg-imd-green',
  yellow: 'bg-imd-yellow',
  orange: 'bg-imd-orange',
  red: 'bg-imd-red',
};

export function WarningsPage() {
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
    (signal) => fetchWarning(cityKey, lang, signal),
    [cityKey, lang],
  );

  const legend: { colour: WarningColour; word: string; meaning: string }[] = [
    { colour: 'green', word: t.colourGreen, meaning: t.colourMeaningGreen },
    { colour: 'yellow', word: t.colourYellow, meaning: t.colourMeaningYellow },
    { colour: 'orange', word: t.colourOrange, meaning: t.colourMeaningOrange },
    { colour: 'red', word: t.colourRed, meaning: t.colourMeaningRed },
  ];

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

  return (
    <div>
      <CityPicker
        cities={cities}
        value={cityKey}
        onChange={setCity}
        lang={lang}
        legend={t.city}
        name="warnings-city"
      />

      <div className="mt-6">
        {status === 'loading' && <Skeleton kind="banner" />}

        {status === 'error' && error instanceof ApiError && error.status === 404 && (
          <Notice variant="refusal">{t.unknownCity}</Notice>
        )}

        {status === 'error' && !(error instanceof ApiError && error.status === 404) && (
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

        {status === 'ok' && data?.warning && (
          <section
            aria-labelledby="warning-headline"
            className={`border-l-8 p-5 ${BANNER_CLASSES[data.warning.colour]}`}
          >
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink">
              {legend.find((l) => l.colour === data.warning!.colour)?.word} · {t.alert}
            </p>
            <h2 id="warning-headline" className="mt-2 break-words text-2xl text-ink">
              {data.warning.headline}
            </h2>
            <p className="mt-1 text-sm text-ink-dim">
              {data.warning.category} · {data.warning.district}
            </p>
            <p className="mt-3 text-sm text-ink">
              {t.valid}: {formatDateRange(data.warning.valid_from, data.warning.valid_to, city?.timezone ?? 'Asia/Kolkata', lang)}
            </p>
            <p className="mt-3 break-words text-ink" lang="en">
              {data.warning.advice}
            </p>
            <p className="mt-4 font-mono text-xs text-ink-faint">
              {data.warning.issued_by} · {data.warning.source}
            </p>
          </section>
        )}

        {status === 'ok' && data && !data.warning && (
          <div className="rounded-sm border border-line p-5">
            <span aria-hidden className="inline-block h-3 w-3 rounded-full bg-imd-green" />
            <h2 className="mt-2 text-2xl text-ink">{t.noWarning}</h2>
            <p className="mt-1 break-words text-ink-dim">
              {t.noWarningBody} {data.city_name}.
            </p>
            <Placeholder ratio="4/3" glyph="flag" label={t.noWarning} className="mt-4 max-w-xs" />
          </div>
        )}
      </div>

      <Reveal className="mt-10">
        <div className="grid gap-px bg-line md:grid-cols-[8rem_1fr]">
          {legend.map((row) => (
            <div key={row.colour} className="contents">
              <div className="flex items-center gap-2 bg-paper p-3">
                <span aria-hidden className={`h-3 w-3 rounded-sm ${SWATCH_CLASSES[row.colour]}`} />
                <span className="text-sm text-ink">{row.word}</span>
              </div>
              <div className="bg-paper p-3 text-sm text-ink-dim">{row.meaning}</div>
            </div>
          ))}
        </div>
      </Reveal>
    </div>
  );
}
