// The WeatherGPT mark in the active persona's badge (pics/ mockups): a
// solid accent disc with the persona's icon — or, for Aviation, the accent
// cloud carrying a plane — and the account avatars built the same way.
import type { AuthUser } from '../lib/auth';
import { initials } from '../lib/auth';
import { useUiPrefs } from '../state/UiPrefsContext';
import { Icon } from './ui';

export function BrandMark({ size = 30 }: { size?: number }) {
  const { theme } = useUiPrefs();
  if (theme.scene === 'airport') {
    return (
      <span className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
        <Icon name="cloud" fill size={Math.round(size * 1.08)} className="text-primary" />
        <span className="absolute" style={{ paddingTop: size * 0.12, transform: 'rotate(0.9rad)' }}>
          <Icon name="flight" fill size={Math.round(size * 0.46)} className="text-on-primary" />
        </span>
      </span>
    );
  }
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-accent-gradient text-on-primary shadow-card"
      style={{ width: size, height: size }}
    >
      <Icon name={theme.markIcon} fill size={Math.round(size * 0.58)} />
    </span>
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
