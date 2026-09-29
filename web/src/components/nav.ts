// The five pages the sidebar and the bottom bar both list (mobile
// app_shell.dart's kNavItems).
export interface NavItem {
  to: string;
  label: string;
  icon: string;
  /** The bottom bar's label. */
  short: string;
  end?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Home', icon: 'home', short: 'Home', end: true },
  { to: '/chat', label: 'Chat & Evidence', icon: 'chat_bubble', short: 'Chat' },
  { to: '/forecast', label: 'Forecast', icon: 'light_mode', short: 'Forecast' },
  { to: '/alerts', label: 'Alerts & Warnings', icon: 'notifications', short: 'Alerts' },
  { to: '/settings', label: 'Settings', icon: 'more_horiz', short: 'More' },
];
