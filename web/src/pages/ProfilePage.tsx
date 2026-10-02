// Profile — opened from the sidebar's "Profile" item or account card
// (mobile profile_page.dart): the signed-in account's details (name, email,
// phone, occupation from the Supabase account's user_metadata), the active
// persona, and Sign out. Signing out clears the saved session and returns
// to onboarding (the Languages page). A guest sees an invitation to sign in
// or create an account instead, and "Exit guest mode".
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { GuestAvatar, ProfileAvatar } from '../components/Brand';
import { FormMessage, GradientButton, OutlineButton } from '../components/forms';
import PageFrame from '../components/PageFrame';
import { ActionRow, AppCard, Icon, IconDisc, SectionTitle, Sheet } from '../components/ui';
import { displayName } from '../lib/auth';
import { useAuth } from '../state/AuthContext';
import { useUiPrefs } from '../state/UiPrefsContext';

/** "+919876543210" / "9876543210" → "+91 98765 43210" / "98765 43210". */
function formatPhone(raw: string) {
  const digits = raw.replace(/[^0-9]/g, '');
  if (digits.length === 10) return `${digits.slice(0, 5)} ${digits.slice(5)}`;
  if (digits.length === 12 && digits.startsWith('91')) return `+91 ${digits.slice(2, 7)} ${digits.slice(7)}`;
  return raw;
}

function memberSince(iso: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

function PersonaRow() {
  const { personaInfo: persona } = useUiPrefs();
  const navigate = useNavigate();
  return (
    <ActionRow
      leading={<IconDisc icon={persona.icon} solid />}
      title={persona.label}
      subtitle={persona.tagline}
      onClick={() => navigate('/persona')}
    />
  );
}

function Detail({ icon, label, value }: { icon: string; label: string; value: string }) {
  return <ActionRow icon={icon} title={label} subtitle={value} trailing={null} />;
}

function GuestProfile() {
  const { signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <>
      <AppCard wash pad="p-space-lg">
        <div className="flex items-center gap-space-md">
          <GuestAvatar size={68} />
          <div>
            <div className="font-headline-md text-headline-md font-bold text-ink">Guest</div>
            <div className="mt-0.5 font-body-sm text-body-sm text-ink-muted">
              You're using WeatherGPT without an account.
            </div>
          </div>
        </div>
      </AppCard>
      <div className="mt-space-lg mb-space-sm">
        <SectionTitle text="With an account" />
      </div>
      <div className="flex flex-col gap-space-sm">
        <ActionRow icon="badge" title="Your name, phone and occupation on your profile" trailing={null} />
        <ActionRow icon="devices" title="The same profile on any device you sign in on" trailing={null} />
      </div>
      <div className="mt-space-md mb-space-sm">
        <SectionTitle text="Persona" />
      </div>
      <PersonaRow />
      <div className="mt-space-xl flex flex-col gap-3">
        <GradientButton label="Create account" onClick={() => navigate('/signup')} />
        <OutlineButton label="Sign in" onClick={() => navigate('/signin')} />
        <OutlineButton
          label="Exit guest mode"
          icon="logout"
          destructive
          onClick={() => {
            void signOut();
            navigate('/', { replace: true });
          }}
        />
      </div>
    </>
  );
}

export default function ProfilePage() {
  const { user, isGuest, signOut } = useAuth();
  const navigate = useNavigate();
  const saved = (useLocation().state as { saved?: unknown } | null)?.saved === true;
  const [confirming, setConfirming] = useState(false);
  const orNone = (v: string) => v || 'Not added';

  return (
    <PageFrame showCityPill={false}>
      <h1 className="mb-space-md font-headline-lg text-headline-lg-mobile md:text-headline-lg font-bold text-ink">Profile</h1>
      {isGuest || !user ? (
        <GuestProfile />
      ) : (
        <>
          {saved && (
            <div className="mb-space-md">
              <FormMessage text="Profile saved." />
            </div>
          )}
          <AppCard wash pad="p-space-lg">
            <div className="flex items-center gap-space-md">
              <ProfileAvatar user={user} size={68} />
              <div className="min-w-0">
                <div className="font-headline-md text-headline-md font-bold text-ink">{displayName(user)}</div>
                <div className="mt-0.5 truncate font-body-sm text-body-sm text-ink-muted">{user.email}</div>
                {user.occupation && (
                  <span className="mt-space-sm inline-flex max-w-full items-center gap-1 px-2.5 py-1 rounded-full bg-card font-label-md text-label-md font-semibold text-primary">
                    <Icon name="work" size={14} />
                    <span className="truncate">{user.occupation}</span>
                  </span>
                )}
              </div>
            </div>
          </AppCard>
          <div className="mt-space-lg mb-space-sm">
            <SectionTitle text="Account details" />
          </div>
          <div className="flex flex-col gap-space-sm">
            <Detail icon="mail" label="Email" value={user.email} />
            <Detail icon="phone" label="Phone" value={orNone(formatPhone(user.phone))} />
            <Detail icon="work" label="Occupation" value={orNone(user.occupation)} />
            <Detail icon="event" label="Member since" value={memberSince(user.createdAt)} />
          </div>
          <div className="mt-space-md mb-space-sm">
            <SectionTitle text="Persona" />
          </div>
          <PersonaRow />
          <div className="mt-space-xl flex flex-col gap-3">
            <GradientButton label="Edit profile" icon="edit" onClick={() => navigate('/profile/edit')} />
            <OutlineButton label="Sign out" icon="logout" destructive onClick={() => setConfirming(true)} />
          </div>
          <Sheet open={confirming} onClose={() => setConfirming(false)} title="Sign out?">
            <p className="font-body-md text-body-md text-ink-muted">
              You'll need your email and password to sign in again.
            </p>
            <div className="mt-space-lg flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="px-4 py-2 rounded-full font-label-md text-label-md font-semibold text-primary hover:bg-tint"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirming(false);
                  void signOut();
                  navigate('/', { replace: true });
                }}
                className="px-4 py-2 rounded-full font-label-md text-label-md font-semibold text-error hover:bg-error-container"
              >
                Sign out
              </button>
            </div>
          </Sheet>
        </>
      )}
    </PageFrame>
  );
}
