import { useRef, useState } from 'react';
import { ApiError, ask } from '../api/client';
import type { AskResponse, Lang } from '../api/types';
import { isAskSuccess } from '../api/types';
import { MetaLine } from '../components/MetaLine';
import { Notice } from '../components/Notice';
import { Placeholder } from '../components/Placeholder';
import { Reveal } from '../components/Reveal';
import { Skeleton } from '../components/Skeleton';
import { formatTime } from '../i18n/format';
import { useT } from '../i18n/strings';
import { useCities } from '../state/CitiesContext';
import { useSettings } from '../state/SettingsContext';

type State =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ok'; data: AskResponse }
  | { kind: 'error'; error: unknown };

export function AskPage() {
  const { lang, setLang, defaultCity } = useSettings();
  const { cities } = useCities();
  const t = useT(lang);
  const inputRef = useRef<HTMLInputElement>(null);

  const [text, setText] = useState('');
  const [city, setCity] = useState<string>(defaultCity);
  const [state, setState] = useState<State>({ kind: 'idle' });

  const submit = async (query: string) => {
    if (!query.trim()) return;
    setState({ kind: 'loading' });
    try {
      const data = await ask(query, lang, city || undefined);
      setState({ kind: 'ok', data });
    } catch (error) {
      setState({ kind: 'error', error });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void submit(text);
  };

  const fillExample = (query: string) => {
    setText(query);
    inputRef.current?.focus();
  };

  return (
    <div>
      <h1 className="text-2xl text-ink md:text-3xl">{t.askTitle}</h1>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="ask-input" className="sr-only">
            {t.askTitle}
          </label>
          <input
            id="ask-input"
            ref={inputRef}
            type="text"
            autoComplete="off"
            maxLength={300}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t.askPlaceholder}
            className="w-full rounded-sm border border-line bg-paper-hi px-4 py-3 text-lg text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon"
          />
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="ask-city" className="mb-1 block text-sm text-ink-dim">
              {t.cityFromQuestion}
            </label>
            <select
              id="ask-city"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="rounded-sm border border-line bg-paper-hi px-3 py-2 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon"
            >
              <option value="">{t.cityFromQuestion}</option>
              {cities.map((c) => (
                <option key={c.key} value={c.key} lang={lang}>
                  {c.names[lang] ?? c.names.en}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="ask-lang" className="mb-1 block text-sm text-ink-dim">
              {t.language}
            </label>
            <select
              id="ask-lang"
              value={lang}
              onChange={(e) => setLang(e.target.value as Lang)}
              className="rounded-sm border border-line bg-paper-hi px-3 py-2 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon"
            >
              <option value="en" lang="en">English</option>
              <option value="ta" lang="ta">தமிழ்</option>
              <option value="hi" lang="hi">हिन्दी</option>
              <option value="te" lang="te">తెలుగు</option>
              <option value="mr" lang="mr">मराठी</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={state.kind === 'loading' || !text.trim()}
            className="rounded-sm bg-monsoon px-6 py-2.5 text-sm font-medium uppercase tracking-[0.12em] text-paper-hi transition-colors hover:bg-monsoon-dim focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]"
          >
            {t.askSubmit}
          </button>
        </div>
      </form>

      {state.kind === 'idle' && (
        <Reveal className="mt-10 flex flex-wrap items-start gap-6" delay={0}>
          <div className="flex flex-1 flex-wrap gap-2">
            {t.exampleQueries.map((query, i) => (
              <button
                key={i}
                type="button"
                onClick={() => fillExample(query)}
                lang={lang}
                className="rounded-sm border border-line px-3 py-1.5 text-left text-sm text-ink-dim transition-colors hover:bg-paper-dim active:scale-[0.98]"
              >
                {query}
              </button>
            ))}
          </div>
          <Placeholder ratio="4/3" glyph="cloud" label={t.askTitle} className="hidden max-w-xs md:grid" />
        </Reveal>
      )}

      <div aria-live="polite" className="mt-8">
        {state.kind === 'loading' && <Skeleton kind="lines" count={3} />}

        {state.kind === 'error' && (
          <Notice
            variant="error"
            onRetry={() => void submit(text)}
            retryLabel={t.retry}
          >
            {state.error instanceof ApiError
              ? state.error.kind === 'timeout'
                ? t.errTimeout
                : state.error.kind === 'network'
                  ? t.errNetwork
                  : state.error.status === 429
                    ? t.errRate
                    : `${t.errHttp} (${state.error.status ?? '?'})`
              : t.errNetwork}
          </Notice>
        )}

        {state.kind === 'ok' && isAskSuccess(state.data) && (
          <div>
            <p className="break-words text-2xl text-ink md:text-3xl">{state.data.response}</p>
            <MetaLine
              className="mt-4"
              items={[state.data.intent, state.data.city, state.data.day, state.data.grounding.provider ?? undefined]}
            />
            {state.data.grounding.fallback_used && (
              <Notice variant="warn" className="mt-4">
                {t.templateAnswer}
              </Notice>
            )}
            {state.data.notice && (
              <Notice variant="info" className="mt-4">
                {state.data.notice}
              </Notice>
            )}
            {state.data.provenance && (
              <MetaLine
                className="mt-3"
                items={[
                  state.data.provenance.source,
                  state.data.provenance.issued
                    ? formatTime(
                        state.data.provenance.issued,
                        cities.find((c) => c.key === state.data.city)?.timezone ?? 'Asia/Kolkata',
                        lang,
                      )
                    : undefined,
                ]}
                badge={{
                  label: state.data.provenance.is_live ? t.liveData : t.fixtureData,
                  fixture: !state.data.provenance.is_live,
                }}
              />
            )}
          </div>
        )}

        {state.kind === 'ok' && !isAskSuccess(state.data) && (
          <div>
            <Notice variant="refusal">{state.data.message}</Notice>
            <p className="mt-2 font-mono text-xs text-ink-faint">{state.data.intent}</p>
            {state.data.notice && (
              <Notice variant="info" className="mt-4">
                {state.data.notice}
              </Notice>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
