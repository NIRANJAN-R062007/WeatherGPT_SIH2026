// The app shell (mobile app_shell.dart). Wide screens keep the permanent
// 256px sidebar; phones get the sky top bar with a menu that opens the
// sidebar as a drawer, and the five-tab bottom bar (Home, Chat, Forecast,
// Alerts, More = Settings). All chrome colours come from the active
// persona's theme.
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { NAV_ITEMS } from './nav';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { Icon } from './ui';

function BottomNav() {
  return (
    <nav className="lg:hidden fixed inset-x-0 bottom-0 z-40 bg-nav-bar rounded-t-[20px] shadow-[0_-3px_16px_rgb(var(--c-shadow)/0.08)] pb-safe">
      <div className="flex h-16">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            aria-label={item.label}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center gap-0.5 ${isActive ? 'text-primary' : 'text-nav-idle'}`
            }
          >
            {({ isActive }) => (
              <>
                <Icon name={item.icon} size={25} fill={isActive} />
                <span className={`text-[11px] leading-tight ${isActive ? 'font-bold' : 'font-medium'}`}>
                  {item.short}
                </span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default function Layout() {
  const [drawer, setDrawer] = useState(false);
  const { pathname } = useLocation();

  // A new page starts at the top (the drawer closes itself on navigate).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawer(false);
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [drawer]);

  return (
    <>
      <aside className="hidden lg:block fixed left-0 top-0 h-full w-64 bg-surface-container-lowest z-50 shadow-chrome overflow-y-auto">
        <Sidebar />
      </aside>

      {drawer && (
        <div className="lg:hidden fixed inset-0 z-[60]">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 max-w-[85vw] bg-sheet shadow-xl overflow-y-auto">
            <Sidebar onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64 min-h-screen flex flex-col bg-sky-gradient pb-16 lg:pb-0">
        <Topbar onMenu={() => setDrawer(true)} />
        <main className="flex-1 flex flex-col">
          <Outlet />
        </main>
      </div>

      <BottomNav />
    </>
  );
}
