import type { ReactElement } from 'react';
import { NavLink } from 'react-router-dom';
import type { Lang, WarningColour } from '../api/types';
import { useT } from '../i18n/strings';

const DOT_COLOURS: Record<WarningColour, string> = {
  green: 'bg-imd-green',
  yellow: 'bg-imd-yellow',
  orange: 'bg-imd-orange',
  red: 'bg-imd-red',
};

interface Props {
  lang: Lang;
  warningColour: WarningColour | null;
}

const ICONS: Record<string, ReactElement> = {
  ask: (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 5h16v11H8l-4 4V5Z" strokeLinejoin="round" />
    </svg>
  ),
  dashboard: (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="4" y="4" width="7" height="7" />
      <rect x="13" y="4" width="7" height="16" />
      <rect x="4" y="13" width="7" height="7" />
    </svg>
  ),
  warnings: (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M12 3 2 20h20L12 3Z" strokeLinejoin="round" />
      <path d="M12 10v4M12 17h.01" strokeLinecap="round" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3" />
      <path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2-1.2L14 3h-4l-.6 2.7a7 7 0 0 0-2 1.2l-2.3-1-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2 1.2L10 21h4l.6-2.7a7 7 0 0 0 2-1.2l2.3 1 2-3.4-2-1.5c.07-.4.1-.8.1-1.2Z" strokeLinejoin="round" />
    </svg>
  ),
};

export function MobileTabs({ lang, warningColour }: Props) {
  const t = useT(lang);
  const tabs = [
    { to: '/', label: t.navAsk, icon: 'ask' },
    { to: '/dashboard', label: t.navDashboard, icon: 'dashboard' },
    { to: '/warnings', label: t.navWarnings, icon: 'warnings', dot: true },
    { to: '/settings', label: t.navSettings, icon: 'settings' },
  ];

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-paper-hi pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            `relative flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 py-1.5 text-[11px] leading-tight text-ink-dim ${
              isActive ? 'text-monsoon' : ''
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span className="relative">
                {ICONS[tab.icon]}
                {tab.dot && warningColour && (
                  <span
                    aria-hidden
                    className={`absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full ${DOT_COLOURS[warningColour]}`}
                  />
                )}
              </span>
              <span className={`whitespace-normal text-center ${isActive ? 'font-medium' : ''}`}>
                {tab.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
