import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: 'grid_view', end: true },
  { to: '/chat', label: 'Chat & Evidence', icon: 'chat_paste_go' },
  { to: '/forecast', label: 'Forecast', icon: 'partly_cloudy_day' },
  { to: '/alerts', label: 'Alerts & Warnings', icon: 'crisis_alert' },
  { to: '/history', label: 'History', icon: 'manage_search' },
  { to: '/settings', label: 'Settings', icon: 'tune' },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-surface-container-lowest z-50 flex flex-col justify-between shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <div className="flex flex-col">
        <div className="p-space-lg flex flex-col gap-space-xs">
          <div className="flex items-center gap-space-sm">
            <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center flex-none">
              <span className="material-symbols-outlined text-on-primary text-[20px]">cloud</span>
            </div>
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-on-surface tracking-tight leading-none">
                WeatherGPT
              </span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">Your AI weather assistant</span>
            </div>
          </div>
        </div>
        <nav className="flex flex-col gap-1 px-space-md mt-space-xs">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-space-sm px-space-md py-2.5 rounded-lg transition-colors font-label-md text-label-md ${
                  isActive
                    ? 'bg-primary text-on-primary'
                    : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                }`
              }
            >
              <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  );
}
