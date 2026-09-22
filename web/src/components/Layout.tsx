import type { ReactNode } from 'react';
import { fetchWarning } from '../api/client';
import { useQuery } from '../hooks/useQuery';
import { useSettings } from '../state/SettingsContext';
import { Footer } from './Footer';
import { MobileTabs } from './MobileTabs';
import { NavBar } from './NavBar';
import { ScrollToHash } from './ScrollToHash';
import { SignalRail } from './SignalRail';

export function Layout({ children }: { children: ReactNode }) {
  const { lang, setLang, defaultCity } = useSettings();

  const { status, data } = useQuery(
    (signal) => fetchWarning(defaultCity, lang, signal),
    [defaultCity, lang],
  );
  const colour = status === 'ok' ? (data?.warning?.colour ?? null) : null;

  // No background on the wrapper: body already paints paper, and the Ask
  // page's SkyBackdrop sits behind the content at z-index -10, which any
  // opaque wrapper would hide.
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-sm focus:bg-monsoon focus:px-4 focus:py-2 focus:text-paper-hi"
      >
        Skip to content
      </a>
      <SignalRail colour={colour} />
      <NavBar lang={lang} onLangChange={setLang} warningColour={colour} />
      <ScrollToHash />
      <main id="main" className="mx-auto max-w-6xl px-4 pb-20 pt-8 sm:px-6 md:pb-8">
        {children}
      </main>
      <Footer />
      <MobileTabs lang={lang} warningColour={colour} />
    </div>
  );
}
