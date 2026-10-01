// The WeatherGPT logo mark (public/brand/: the light-theme and dark-theme
// cuts of the logo, without the wordmark — the name is set as text next to
// it), and the account avatars.
import type { AuthUser } from '../lib/auth';
import { initials } from '../lib/auth';
import { useUiPrefs } from '../state/UiPrefsContext';
import { Icon } from './ui';

export function BrandMark({ size = 30 }: { size?: number }) {
  const { theme } = useUiPrefs();
  return (
    <img
      src={`${import.meta.env.BASE_URL}brand/weathergpt-mark-${theme.brightness}.svg`}
      alt=""
      width={size}
      height={size}
      className="shrink-0 select-none"
      draggable={false}
    />
  );
}

/** WeatherGPT mark + name, as in the top bar. */
export function BrandTitle({ size = 30 }: { size?: number }) {
  return (
    <span className="flex items-center gap-space-sm">
      <BrandMark size={size} />
      <span className="font-headline-sm text-headline-sm font-bold text-ink">WeatherGPT</span>
    </span>
  );
}

const ring = (size: number) => ({ width: size, height: size, borderWidth: size > 50 ? 3 : 2 });

/** The accent-gradient disc with the user's initials. */
export function ProfileAvatar({ user, size = 44 }: { user: AuthUser; size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-accent-gradient border-card text-on-primary shadow-card font-headline-sm font-bold"
      style={{ ...ring(size), fontSize: size * 0.36 }}
    >
      {initials(user)}
    </span>
  );
}

/** The guest's avatar: the accent disc with a person outline. */
export function GuestAvatar({ size = 44 }: { size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-accent-gradient border-card text-on-primary shadow-card"
      style={ring(size)}
    >
      <Icon name="person" size={Math.round(size * 0.55)} />
    </span>
  );
}
