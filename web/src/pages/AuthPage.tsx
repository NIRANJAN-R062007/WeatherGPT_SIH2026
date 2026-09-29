// Sign in / create account, against the team's Supabase project
// (lib/auth.ts; mobile auth_page.dart). Creating an account collects the
// profile the Profile page shows: name, email, phone and occupation. The
// project requires email confirmation, so a new account ends on a "check
// your inbox" step with a resend button; signing in to an unconfirmed
// account offers the same resend. Success signs in and opens the app.
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { GradientButton, GuestButton, OutlineButton, SubPage, TextField } from '../components/forms';
import PageFrame from '../components/PageFrame';
import { Icon, IconDisc, PageHeader } from '../components/ui';
import { AuthError } from '../lib/auth';
import { useAuth } from '../state/AuthContext';

export type AuthMode = 'signIn' | 'signUp';

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const OCCUPATIONS = ['Farmer', 'Fisherman', 'Pilot', 'City official', 'Student', 'Teacher'];

/** Digits only, keeping a leading +; spaces, dashes and brackets dropped. */
function normalizePhone(raw: string) {
  const trimmed = raw.trim();
  const digits = trimmed.replace(/[^0-9]/g, '');
  return trimmed.startsWith('+') ? `+${digits}` : digits;
}

function validateEmail(v: string) {
  const s = v.trim();
  if (!s) return 'Enter your email.';
  if (!EMAIL.test(s)) return "That doesn't look like an email address.";
  return null;
}

function validatePhone(v: string) {
  const s = normalizePhone(v);
  if (!s) return 'Enter your phone number.';
  const digits = s.replace('+', '');
  if (digits.length < 10 || digits.length > 15) {
    return 'Enter a 10-digit mobile number (with country code if outside India).';
  }
  return null;
}

type Field = 'name' | 'email' | 'phone' | 'occupation' | 'password' | 'confirm';

/** An inline error (red) or notice (persona tint) under the form. */
function Message({ text, error = false }: { text: string; error?: boolean }) {
  return (
    <div
      role={error ? 'alert' : 'status'}
      className={`flex items-start gap-2 p-3 rounded-xl font-body-md text-body-md ${
        error ? 'bg-error-container text-on-error-container' : 'bg-tint text-ink'
      }`}
    >
      <Icon name={error ? 'error' : 'check_circle'} size={18} className={error ? '' : 'text-primary'} />
      <span>{text}</span>
    </div>
  );
}

export default function AuthPage({ initialMode }: { initialMode: AuthMode }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [values, setValues] = useState<Record<Field, string>>({
    name: '',
    email: '',
    phone: '',
    occupation: '',
    password: '',
    confirm: '',
  });
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offerResend, setOfferResend] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  /** Set once an account is created and waits for its confirmation link. */
  const [awaiting, setAwaiting] = useState<string | null>(null);
  const signUp = mode === 'signUp';

  const errors: Record<Field, string | null> = {
    name: signUp && !values.name.trim() ? 'Enter your name.' : null,
    email: validateEmail(values.email),
    phone: signUp ? validatePhone(values.phone) : null,
    occupation: !signUp
      ? null
      : !values.occupation.trim()
        ? 'Enter your occupation.'
        : values.occupation.trim().length > 60
          ? 'Keep it under 60 characters.'
          : null,
    password: !values.password
      ? 'Enter your password.'
      : signUp && values.password.length < 8
        ? 'Use at least 8 characters.'
        : null,
    confirm: signUp && values.confirm !== values.password ? "Passwords don't match." : null,
  };
  const shown = (f: Field) => ((submitted || touched[f]) && errors[f]) || null;

  const bind = (f: Field) => ({
    name: f,
    value: values[f],
    disabled: busy,
    onChange: (e: { target: { value: string } }) => setValues((v) => ({ ...v, [f]: e.target.value })),
    onBlur: () => setTouched((t) => ({ ...t, [f]: true })),
  });

  const switchMode = (m: AuthMode) => {
    setMode(m);
    setError(null);
    setNotice(null);
    setOfferResend(false);
    setAwaiting(null);
    setSubmitted(false);
    setTouched({});
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    const fields: Field[] = signUp ? ['name', 'email', 'phone', 'occupation', 'password', 'confirm'] : ['email', 'password'];
    if (fields.some((f) => errors[f])) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setOfferResend(false);
    try {
      if (!signUp) {
        await auth.signIn(values.email, values.password);
        navigate('/', { replace: true });
        return;
      }
      const result = await auth.signUp({
        email: values.email,
        password: values.password,
        fullName: values.name,
        phone: normalizePhone(values.phone),
        occupation: values.occupation,
      });
      if (result.session) {
        navigate('/', { replace: true });
        return;
      }
      setAwaiting(result.email);
    } catch (err) {
      const e2 = err instanceof AuthError ? err : new AuthError('Something went wrong. Please try again.');
      setError(e2.message);
      setOfferResend(e2.emailNotConfirmed);
    } finally {
      setBusy(false);
    }
  };

  const resend = async (email: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await auth.resendConfirmation(email);
      setNotice(`Confirmation email sent again to ${email}.`);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const passwordToggle = (
    <button
      type="button"
      onClick={() => setShowPassword((s) => !s)}
      aria-label={showPassword ? 'Hide password' : 'Show password'}
      title={showPassword ? 'Hide password' : 'Show password'}
      className="p-2 rounded-full text-ink-muted hover:bg-tint"
    >
      <Icon name={showPassword ? 'visibility_off' : 'visibility'} size={20} />
    </button>
  );

  const body = awaiting ? (
    <div className="flex flex-col items-center text-center">
      <div className="mt-space-md">
        <IconDisc icon="mark_email_unread" solid size={72} />
      </div>
      <h1 className="mt-space-lg font-headline-lg text-headline-lg-mobile font-bold text-ink">Confirm your email</h1>
      <p className="mt-space-sm font-body-md text-body-md text-ink-muted">
        We sent a confirmation link to <strong className="text-ink">{awaiting}</strong>. Open it, then come back and
        sign in.
      </p>
      <div className="w-full mt-space-md flex flex-col gap-space-md text-left">
        {error && <Message text={error} error />}
        {notice && <Message text={notice} />}
      </div>
      <div className="w-full mt-space-xl flex flex-col gap-3">
        <GradientButton
          label="I've confirmed — sign in"
          disabled={busy}
          onClick={() => {
            setValues((v) => ({ ...v, password: '', confirm: '' }));
            switchMode('signIn');
          }}
        />
        <OutlineButton label="Resend email" icon="forward_to_inbox" disabled={busy} onClick={() => resend(awaiting)} />
      </div>
    </div>
  ) : (
    <>
      <PageHeader
        title={signUp ? 'Create your account' : 'Welcome back'}
        subtitle={signUp ? 'Tell us a little about you — it appears on your profile.' : 'Sign in to continue to WeatherGPT.'}
      />
      <form noValidate onSubmit={submit} className="mt-space-lg flex flex-col gap-3.5">
        {signUp && (
          <TextField label="Full name" icon="person" autoComplete="name" error={shown('name')} {...bind('name')} />
        )}
        <TextField
          label="Email"
          icon="mail"
          type="email"
          autoComplete="email"
          inputMode="email"
          error={shown('email')}
          {...bind('email')}
        />
        {signUp && (
          <>
            <TextField
              label="Phone number"
              icon="phone"
              type="tel"
              autoComplete="tel"
              hint="98765 43210"
              error={shown('phone')}
              {...bind('phone')}
            />
            <div>
              <TextField
                label="Occupation"
                icon="work"
                hint="e.g. Farmer, Pilot, Student"
                error={shown('occupation')}
                {...bind('occupation')}
              />
              <div className="mt-2 flex flex-wrap gap-1.5">
                {OCCUPATIONS.map((o) => {
                  const selected = values.occupation.trim().toLowerCase() === o.toLowerCase();
                  return (
                    <button
                      key={o}
                      type="button"
                      disabled={busy}
                      aria-pressed={selected}
                      onClick={() => setValues((v) => ({ ...v, occupation: o }))}
                      className={`px-3 py-1.5 rounded-full font-label-md text-label-md font-semibold transition-colors ${
                        selected ? 'bg-primary text-on-primary' : 'bg-tint text-primary hover:bg-tint-strong'
                      }`}
                    >
                      {o}
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        )}
        <TextField
          label="Password"
          icon="lock"
          type={showPassword ? 'text' : 'password'}
          autoComplete={signUp ? 'new-password' : 'current-password'}
          suffix={passwordToggle}
          error={shown('password')}
          {...bind('password')}
        />
        {signUp && (
          <TextField
            label="Confirm password"
            icon="lock"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            error={shown('confirm')}
            {...bind('confirm')}
          />
        )}

        {error && (
          <div className="mt-1 flex flex-col gap-space-sm">
            <Message text={error} error />
            {offerResend && (
              <OutlineButton
                label="Resend confirmation email"
                icon="forward_to_inbox"
                disabled={busy}
                onClick={() => resend(values.email.trim())}
              />
            )}
          </div>
        )}
        {notice && <Message text={notice} />}

        <div className="mt-2">
          <GradientButton type="submit" label={signUp ? 'Create account' : 'Sign in'} loading={busy} />
        </div>
      </form>
      <p className="mt-space-md text-center font-body-md text-body-md text-ink-muted">
        {signUp ? 'Already have an account? ' : 'New to WeatherGPT? '}
        <button
          type="button"
          disabled={busy}
          onClick={() => switchMode(signUp ? 'signIn' : 'signUp')}
          className="px-1 py-1.5 rounded-lg font-label-md text-[14px] font-bold text-primary hover:bg-tint"
        >
          {signUp ? 'Sign in' : 'Create an account'}
        </button>
      </p>
      <div className="mt-space-xs">
        <GuestButton disabled={busy} />
      </div>
    </>
  );

  return (
    <SubPage>
      <PageFrame showCityPill={false} footer="soft">
        <div className="mx-auto max-w-md">{body}</div>
      </PageFrame>
    </SubPage>
  );
}
