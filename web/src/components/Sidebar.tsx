// Logo block + nav; the active item is a solid primary pill. Below the
// pages: Profile, and the account's card at the foot (both open the Profile
// page, which has Sign out) — mobile app_shell.dart's Sidebar.
import { NavLink } from 'react-router-dom';
import { displayName } from '../lib/auth';
import { useAuth } from '../state/AuthContext';
import { BrandMark, GuestAvatar, ProfileAvatar } from './Brand';
import { NAV_ITEMS } from './nav';
import { Icon } from './ui';
import { useT } from '../lib/i18n';

const tile = (active: boolean) =>
  `flex items-center gap-space-sm px-space-md py-2.5 rounded-lg transition-colors font-label-md text-label-md ${
    active ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
  }`;

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const t = useT();
  const { user, isGuest } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <div className="p-space-lg flex items-center gap-space-sm">
        <BrandMark size={32} />
        <div className="flex flex-col">
          <span className="font-headline-sm text-headline-sm text-on-surface tracking-tight leading-none">
            WeatherGPT
          </span>
          <span className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">{t('Your AI weather assistant')}</span>
        </div>
      </div>
      <nav className="flex flex-col gap-1 px-space-md">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} onClick={onNavigate} className={({ isActive }) => tile(isActive)}>
            {({ isActive }) => (
              <>
                <Icon name={item.icon} size={20} fill={isActive} />
                <span>{t(item.label)}</span>
              </>
            )}
          </NavLink>
        ))}
        <NavLink to="/history" onClick={onNavigate} className={({ isActive }) => tile(isActive)}>
          <Icon name="manage_search" size={20} />
          <span>{t('History')}</span>
        </NavLink>
        <NavLink to="/aviation" onClick={onNavigate} className={({ isActive }) => tile(isActive)}>
          <Icon name="flight" size={20} />
          <span>{t('Airport weather')}</span>
        </NavLink>
        <NavLink to="/best-window" onClick={onNavigate} className={({ isActive }) => tile(isActive)}>
          <Icon name="schedule" size={20} />
          <span>{t('Best Time & What-if')}</span>
        </NavLink>
        <div className="my-space-sm h-px bg-outline-variant/60" />
        <NavLink to="/profile" onClick={onNavigate} className={({ isActive }) => tile(isActive)}>
          <Icon name="account_circle" size={20} />
          <span>{t('Profile')}</span>
        </NavLink>
      </nav>
      <div className="flex-1" />
      {(user || isGuest) && (
        <NavLink
          to="/profile"
          onClick={onNavigate}
          className="m-space-md flex items-center gap-2.5 p-3 rounded-card bg-tint hover:bg-tint-strong transition-colors"
        >
          {user ? <ProfileAvatar user={user} size={40} /> : <GuestAvatar size={40} />}
          <span className="flex-1 min-w-0">
            <span className="block truncate font-label-md text-label-md font-bold text-ink">
              {user ? displayName(user) : t('Guest')}
            </span>
            <span className="block truncate font-body-sm text-body-sm text-ink-muted">
              {user ? user.email : t('Not signed in')}
            </span>
          </span>
          <Icon name="chevron_right" size={20} className="text-ink-muted" />
        </NavLink>
      )}
    </div>
  );
}
