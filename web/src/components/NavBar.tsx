import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import type { Lang, WarningColour } from '../api/types';
import { useT } from '../i18n/strings';
import { LangSwitcher } from './LangSwitcher';

const DOT_COLOURS: Record<WarningColour, string> = {
  green: 'bg-imd-green',
  yellow: 'bg-imd-yellow',
  orange: 'bg-imd-orange',
  red: 'bg-imd-red',
};

interface Props {
  lang: Lang;
  onLangChange: (lang: Lang) => void;
  warningColour: WarningColour | null;
}

export function NavBar({ lang, onLangChange, warningColour }: Props) {
  const t = useT(lang);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const links = [
    { to: '/', label: t.navAsk },
    { to: '/dashboard', label: t.navDashboard },
    { to: '/warnings', label: t.navWarnings, dot: true },
    { to: '/settings', label: t.navSettings },
  ];

  return (
    <header
      // Always translucent: over flat paper that's indistinguishable from
      // solid, and over the Ask page's sky it lets the gradient through.
      className={`sticky top-1 z-40 backdrop-blur-md transition-colors duration-300 ${
        scrolled ? 'border-b border-line bg-paper/85' : 'bg-paper/60'
      }`}
      style={{ height: '56px' }}
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <span className="font-mono text-sm font-medium tracking-[0.2em] text-ink">WeatherGPT</span>
        <nav aria-label="Main" className="hidden gap-6 md:flex">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `group relative py-1 text-sm text-ink-dim transition-colors hover:text-ink ${
                  isActive ? 'text-ink' : ''
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className="whitespace-normal">{link.label}</span>
                  {link.dot && warningColour && (
                    <span
                      aria-hidden
                      className={`ml-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle ${DOT_COLOURS[warningColour]}`}
                    />
                  )}
                  <span
                    aria-hidden
                    className={`absolute -bottom-0.5 left-0 h-px w-full origin-left scale-x-0 bg-ink transition-transform duration-300 ${
                      isActive ? 'scale-x-100' : 'group-hover:scale-x-100'
                    }`}
                  />
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <LangSwitcher value={lang} onChange={onLangChange} />
      </div>
    </header>
  );
}
