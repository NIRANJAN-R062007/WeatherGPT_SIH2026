import { useSearchParams } from 'react-router-dom';
import { ApiError, fetchWarning } from '../api/client';
import { warningStatus } from '../api/types';
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

  // The feed's verdict for this city. Anything short of one — the feed
  // switched off (every deploy's default), no fixture, an older backend
  // without `status` — is "unavailable" and renders as such, never as green.
  const result = status === 'ok' ? data : undefined;
  const verdict = result ? warningStatus(result) : null;
  const warning = result?.warning ?? null;
  const validity = warning
    ? formatDateRange(warning.valid_from, warning.valid_to, city?.timezone ?? 'Asia/Kolkata', lang)
    : '';

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

        {verdict === 'unavailable' && (
          <Notice variant="refusal">{t.warningsUnavailable}</Notice>
        )}

        {verdict === 'active' && warning && (
          <section
            aria-labelledby="warning-headline"
            className={`border-l-8 p-5 ${BANNER_CLASSES[warning.colour]}`}
          >
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink">
              {warning.colour_label} · {t.alert}
            </p>
            <h2 id="warning-headline" className="mt-2 break-words text-2xl text-ink">
              {warning.headline}
            </h2>
            <p className="mt-1 text-sm text-ink-dim">
              {warning.category_label} · {warning.district}
            </p>
            <p className="mt-3 text-sm text-ink">
              {t.valid}: {validity}
            </p>
            {/* Free text from the feed, English only — see web/README.md. */}
            <p className="mt-3 break-words text-ink" lang="en">
              {warning.advice}
            </p>
            <p className="mt-4 font-mono text-xs text-ink-faint">
              {warning.issued_by} · {warning.source}
            </p>
          </section>
        )}

        {verdict === 'clear' && warning && result && (
          <div className="rounded-sm border border-line p-5">
            <span aria-hidden className="inline-block h-3 w-3 rounded-full bg-imd-green" />
            <h2 className="mt-2 break-words text-2xl text-ink">{warning.headline}</h2>
            <p className="mt-1 break-words text-ink-dim">
              {t.noWarningBody} {result.city_name}.
            </p>
            <p className="mt-3 text-sm text-ink">
              {t.valid}: {validity}
            </p>
            <p className="mt-3 break-words text-ink" lang="en">
              {warning.advice}
            </p>
            <p className="mt-4 font-mono text-xs text-ink-faint">
              {warning.issued_by} · {warning.source}
            </p>
            <Placeholder ratio="4/3" glyph="flag" label={warning.headline} className="mt-4 max-w-xs" />
          </div>
        )}
      </div>

      {result?.legend && result.legend.length > 0 && (
        <Reveal className="mt-10">
          <div className="grid gap-px bg-line md:grid-cols-[8rem_1fr]">
            {result.legend.map((row) => (
              <div key={row.colour} className="contents">
                <div className="flex items-center gap-2 bg-paper p-3">
                  <span aria-hidden className={`h-3 w-3 rounded-sm ${SWATCH_CLASSES[row.colour]}`} />
                  <span className="text-sm text-ink">{row.label}</span>
                </div>
                <div className="bg-paper p-3 text-sm text-ink-dim">{row.meaning}</div>
              </div>
            ))}
          </div>
        </Reveal>
      )}
    </div>
  );
}
