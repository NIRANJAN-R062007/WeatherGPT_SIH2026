import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiBase } from '../config';
import { CityPicker } from '../components/CityPicker';
import { Reveal } from '../components/Reveal';
import { LANGUAGES, useT } from '../i18n/strings';
import type { Lang } from '../api/types';
import { useCities } from '../state/CitiesContext';
import { useSettings } from '../state/SettingsContext';

export function SettingsPage() {
  const { lang, setLang, defaultCity, setDefaultCity } = useSettings();
  const { cities } = useCities();
  const t = useT(lang);
  const [savedVisible, setSavedVisible] = useState(false);

  useEffect(() => {
    if (!savedVisible) return;
    const timer = window.setTimeout(() => setSavedVisible(false), 1500);
    return () => window.clearTimeout(timer);
  }, [savedVisible]);

  const flash = () => setSavedVisible(true);

  return (
    <div className="space-y-10">
      <Reveal>
        <fieldset>
          <legend className="mb-3 text-lg text-ink">{t.language}</legend>
          <div className="space-y-2">
            {LANGUAGES.map((l) => (
              <div key={l.code} className="flex items-center gap-2">
                <input
                  type="radio"
                  id={`settings-lang-${l.code}`}
                  name="settings-lang"
                  value={l.code}
                  checked={lang === l.code}
                  onChange={() => {
                    setLang(l.code as Lang);
                    flash();
                  }}
                  className="h-4 w-4 accent-monsoon"
                />
                <label htmlFor={`settings-lang-${l.code}`} lang={l.code} className="text-sm text-ink">
                  {l.native}{' '}
                  <span lang="en" className="font-mono text-xs text-ink-faint">
                    ({l.english})
                  </span>
                </label>
              </div>
            ))}
          </div>
        </fieldset>
      </Reveal>

      <Reveal delay={0.08}>
        <div>
          <p className="mb-3 text-lg text-ink">{t.defaultCity}</p>
          <CityPicker
            cities={cities}
            value={defaultCity}
            onChange={(key) => {
              setDefaultCity(key);
              flash();
            }}
            lang={lang}
            legend={t.defaultCity}
            legendHidden
            name="settings-city"
          />
        </div>
      </Reveal>

      <div role="status" className={`text-sm text-monsoon transition-opacity duration-500 ${savedVisible ? 'opacity-100' : 'opacity-0'}`}>
        {t.saved}
      </div>

      <Reveal delay={0.16}>
        <div className="border-t border-line pt-6">
          <h2 className="text-lg text-ink">{t.aboutData}</h2>
          <p className="mt-2 font-mono text-xs text-ink-faint">{apiBase}</p>
          <p className="mt-3 max-w-2xl text-sm text-ink-dim">
            Every number in an answer is checked against the weather data before it is shown; if
            the check fails you get a template answer or a refusal, never a guess.
          </p>
          <Link
            to="/warnings"
            className="mt-3 inline-block text-sm text-monsoon underline underline-offset-2 hover:text-monsoon-dim"
          >
            {t.navWarnings}
          </Link>
        </div>
      </Reveal>
    </div>
  );
}
