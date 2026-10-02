// Onboarding — what a signed-out visitor sees (pics/ Languages and Welcome
// mockups, in their light and dark designs; mobile onboarding_pages.dart):
//   1. LanguagePage (/): pick English / हिन्दी / தமிழ் / తెలుగు / मराठी, then
//      Continue. The pick becomes the app language (UiPrefs lang).
//   2. WelcomeLoginPage (/welcome): the WeatherGPT logo and "Welcome to
//      WeatherGPT!" over the painted panorama, and the log-in sheet under it
//      — email and password, Google, Sign Up and Sign in as Guest — all in
//      the language picked on page 1.
// App.tsx shows these whenever the account is signed out, so signing out
// lands back here. Sign Up and Forgot password open the existing AuthPage /
// ResetPasswordPage.
import { useMemo, useState, type CSSProperties, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FormMessage } from '../components/forms';
import {
  ONB_DARK,
  ONB_LIGHT,
  onboardingClouds,
  onboardingFooter,
  onboardingScene,
  type OnbPalette,
} from '../components/scenery/onboardingScene';
import { PaintCanvas } from '../components/scenery/Scenery';
import { Icon, Spinner } from '../components/ui';
import { AuthError } from '../lib/auth';
import { onboardingStrings, welcomeLine, type OnboardingStrings } from '../lib/onboardingStrings';
import { normalizePhone } from '../lib/validate';
import { useAuth } from '../state/AuthContext';
import { LANG_NAMES, useUiPrefs, type LangCode } from '../state/UiPrefsContext';

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function usePalette(): OnbPalette {
  return useUiPrefs().isDark ? ONB_DARK : ONB_LIGHT;
}

const gradient = (p: OnbPalette) => `linear-gradient(to bottom, ${p.bgTop}, ${p.bgBottom})`;

/** Back arrow (when there is somewhere to go back to) and the light / dark
 *  toggle — the only way to switch modes before signing in. */
function TopBar({ s, onBack }: { s: OnboardingStrings; onBack?: () => void }) {
  const p = usePalette();
  const { setAppearance } = useUiPrefs();
  const label = p.isDark ? s.lightMode : s.darkMode;
  return (
    <div className="h-12 flex items-center justify-between" style={{ color: p.ink }}>
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label={s.back}
          title={s.back}
          className="p-2.5 -ml-1 rounded-full hover:bg-black/5"
        >
          <Icon name="arrow_back_ios_new" size={22} />
        </button>
      ) : (
        <span />
      )}
      <button
        type="button"
        onClick={() => setAppearance(p.isDark ? 'light' : 'dark')}
        aria-label={label}
        title={label}
        className="p-2.5 -mr-1 rounded-full hover:bg-black/5"
      >
        <Icon name={p.isDark ? 'light_mode' : 'dark_mode'} size={24} />
      </button>
    </div>
  );
}

/** The full-width blue button. */
function BlueButton({
  label,
  icon,
  onClick,
  loading = false,
  type = 'button',
}: {
  label: string;
  icon?: string;
  onClick?: () => void;
  loading?: boolean;
  type?: 'button' | 'submit';
}) {
  const p = usePalette();
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={loading}
      aria-busy={loading || undefined}
      className="w-full h-[54px] flex items-center justify-center gap-2.5 rounded-2xl text-white font-label-md text-[17px] font-semibold transition hover:brightness-105 active:scale-[0.99] disabled:cursor-wait"
      style={{
        background: `linear-gradient(to bottom, ${p.buttonTop}, ${p.buttonBottom})`,
        boxShadow: `0 5px 14px ${p.buttonBottom}4D`,
      }}
    >
      {loading ? (
        <Spinner className="w-[22px] h-[22px] border-white/35 border-t-white" />
      ) : (
        <>
          <span className="truncate">{label}</span>
          {icon && <Icon name={icon} size={22} />}
        </>
      )}
    </button>
  );
}

/** The logo mark: the saved pics/ logos (weathergpt-logo-light.svg for
 *  light, weathergpt-logo-original.svg for dark) without their
 *  "WeatherGPT" text. */
function Logo({ size }: { size: number }) {
  const p = usePalette();
  return (
    <img
      src={`${import.meta.env.BASE_URL}brand/weathergpt-onboarding-${p.isDark ? 'dark' : 'light'}.svg`}
      alt=""
      width={size}
      height={size}
      className="shrink-0 select-none"
      draggable={false}
    />
  );
}

/** "WeatherGPT!" set as text, the "!" black on light and white on dark. */
function Wordmark({ size, suffix = '!' }: { size: number; suffix?: string }) {
  const p = usePalette();
  return (
    <span
      className="font-headline-xl font-extrabold whitespace-nowrap tracking-[-0.5px] leading-[1.15]"
      style={{ fontSize: size, color: p.ink }}
    >
      WeatherGPT
      {suffix && <span style={{ color: suffix === '!' ? (p.isDark ? '#FFFFFF' : '#000000') : p.ink }}>{suffix}</span>}
    </span>
  );
}

// ---------------------------------------------------------------------------
// 1. Languages

export function LanguagePage() {
  const p = usePalette();
  const prefs = useUiPrefs();
  const navigate = useNavigate();
  /** English unless a language was picked earlier in this visit. */
  const [lang, setLang] = useState<LangCode>(prefs.lang);
  const s = onboardingStrings(lang);
  const clouds = useMemo(() => onboardingClouds(p), [p]);
  const footer = useMemo(() => onboardingFooter(p), [p]);

  return (
    <div className="relative min-h-screen overflow-hidden" style={{ background: gradient(p) }}>
      <div className="absolute inset-x-0 top-0 h-[300px] pointer-events-none">
        <PaintCanvas paint={clouds} />
      </div>
      <div className="absolute inset-x-0 bottom-0 h-[130px] pointer-events-none">
        <PaintCanvas paint={footer} />
      </div>
      <main className="relative mx-auto max-w-[460px] px-6 pb-[140px]">
        <TopBar s={s} />
        <div className="flex flex-col items-center">
          <Logo size={84} />
          <div className="mt-1.5">
            <Wordmark size={30} />
          </div>
        </div>
        <h1
          className="mt-6 font-headline-xl text-[34px] leading-[1.15] font-extrabold"
          style={{ color: p.ink }}
          lang={lang}
        >
          {s.languagesTitle}
        </h1>
        <p
          className="mt-2 font-body-lg text-[17px] leading-[1.35]"
          style={{ color: p.isDark ? p.accent : p.muted }}
          lang={lang}
        >
          {s.languagesLead}
        </p>
        <div role="radiogroup" aria-label={s.languagesTitle} className="mt-[22px] flex flex-col gap-3">
          {(Object.keys(LANG_NAMES) as LangCode[]).map((code) => (
            <LanguageOption key={code} code={code} selected={code === lang} onSelect={() => setLang(code)} />
          ))}
        </div>
        <div className="mt-[30px]">
          <BlueButton
            label={s.continueLabel}
            icon="arrow_forward"
            onClick={() => {
              prefs.setLang(lang);
              navigate('/welcome');
            }}
          />
        </div>
      </main>
    </div>
  );
}

function LanguageOption({ code, selected, onSelect }: { code: LangCode; selected: boolean; onSelect: () => void }) {
  const p = usePalette();
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      lang={code}
      className="h-[60px] px-5 flex items-center justify-between rounded-2xl text-left transition-colors"
      style={{
        background: selected ? p.selectedFill : `${p.field}${p.isDark ? '99' : 'D9'}`,
        border: `${selected ? 1.6 : 1}px solid ${selected ? p.selectedBorder : p.fieldBorder}`,
        color: p.ink,
      }}
    >
      <span className="font-body-lg text-[19px] font-medium">{LANG_NAMES[code]}</span>
      <span
        className="w-[26px] h-[26px] rounded-full flex items-center justify-center transition-colors"
        style={selected ? { background: p.accent, color: '#fff' } : { border: `1.6px solid ${p.radio}` }}
      >
        {selected && <Icon name="check" size={18} />}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// 2. Welcome + Log In

export function WelcomeLoginPage() {
  const p = usePalette();
  const { lang } = useUiPrefs();
  const s = onboardingStrings(lang);
  const auth = useAuth();
  const navigate = useNavigate();
  const scene = useMemo(() => onboardingScene(p), [p]);

  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState<{ id?: boolean; password?: boolean }>({});
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(auth.googleError);
  const [offerResend, setOfferResend] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  /** Email, or a phone number — which the project can't sign in with yet
   *  (accounts are email + password; the phone is profile data), so a phone
   *  gets a clear message instead of a failed request. */
  const idError = (() => {
    const v = id.trim();
    if (!v) return s.enterEmailOrPhone;
    if (EMAIL.test(v)) return null;
    const digits = normalizePhone(v).replace('+', '');
    if (!v.includes('@') && digits.length >= 10 && digits.length <= 15) return s.phoneUnavailable;
    return s.badEmail;
  })();
  const passwordError = password ? null : s.enterPassword;
  const shownId = submitted || touched.id ? idError : null;
  const shownPassword = submitted || touched.password ? passwordError : null;

  const logIn = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (idError || passwordError) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setOfferResend(false);
    try {
      await auth.signIn(id, password);
      navigate('/', { replace: true });
    } catch (err) {
      const e2 = err instanceof AuthError ? err : new AuthError('Something went wrong. Please try again.');
      setError(e2.message);
      setOfferResend(e2.emailNotConfirmed);
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setBusy(true);
    setError(null);
    try {
      await auth.resendConfirmation(id.trim());
      setNotice(s.confirmationResent);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    setGoogleBusy(true);
    setError(null);
    try {
      await auth.signInWithGoogle(); // leaves the page on success
    } catch (err) {
      setError(err instanceof AuthError ? err.message : 'Google sign-in failed. Please try again.');
      setGoogleBusy(false);
    }
  };

  const disabled = busy || googleBusy;
  const link = 'font-label-md font-bold rounded-lg hover:underline disabled:opacity-60';

  return (
    <div className="min-h-screen" style={{ background: gradient(p) }} lang={lang}>
      <div className="mx-auto max-w-[480px] min-h-screen flex flex-col" style={{ background: p.sheet }}>
        {/* The hero is kept compact so the log-in sheet sits high. */}
        <div className="relative h-[330px] shrink-0" style={{ background: gradient(p) }}>
          <div className="absolute inset-x-0 top-0 h-[334px]">
            <PaintCanvas paint={scene} />
          </div>
          <div className="relative px-4">
            <TopBar s={s} onBack={() => navigate('/')} />
            <div className="flex flex-col items-center">
              <Logo size={76} />
              <WelcomeTitle s={s} />
            </div>
          </div>
        </div>
        <main
          className="relative -mt-7 flex-1 rounded-t-[30px] px-[22px] pt-[26px] pb-6"
          style={{
            background: p.sheet,
            borderTop: `1.2px solid ${p.sheetBorder}`,
            boxShadow: `0 -4px 18px rgba(0, 0, 0, ${p.isDark ? 0.3 : 0.06})`,
          }}
        >
          <form noValidate onSubmit={logIn} className="flex flex-col">
            <Field
              icon="mail"
              placeholder={s.emailOrPhone}
              type="email"
              inputMode="email"
              autoComplete="email"
              value={id}
              disabled={disabled}
              error={shownId}
              onChange={setId}
              onBlur={() => setTouched((t) => ({ ...t, id: true }))}
            />
            <div className="h-3.5" />
            <Field
              icon="lock"
              placeholder={s.password}
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              disabled={disabled}
              error={shownPassword}
              onChange={setPassword}
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? s.hidePassword : s.showPassword}
                  title={showPassword ? s.hidePassword : s.showPassword}
                  className="p-2 rounded-full hover:bg-black/5"
                  style={{ color: p.ink }}
                >
                  <Icon name={showPassword ? 'visibility_off' : 'visibility'} size={22} />
                </button>
              }
            />
            <div className="flex justify-end mt-1.5 mb-2.5">
              <Link
                to="/reset-password"
                state={{ email: id.trim() }}
                className={`${link} px-2 py-1.5 text-[14px]`}
                style={{ color: p.accent }}
              >
                {s.forgotPassword}
              </Link>
            </div>
            {error && (
              <div className="mb-3 flex flex-col gap-1">
                <FormMessage text={error} error />
                {offerResend && (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={resend}
                    className={`${link} self-start inline-flex items-center gap-1.5 px-2 py-1.5 text-[14px]`}
                    style={{ color: p.accent }}
                  >
                    <Icon name="forward_to_inbox" size={18} />
                    {s.resendConfirmation}
                  </button>
                )}
              </div>
            )}
            {notice && (
              <div className="mb-3">
                <FormMessage text={notice} />
              </div>
            )}
            <BlueButton type="submit" label={s.logIn} loading={busy} />
          </form>

          <div className="my-[18px] flex items-center gap-3.5">
            <span className="flex-1 h-px" style={{ background: p.divider }} />
            <span className="font-body-md text-body-md" style={{ color: p.muted }}>
              {s.or}
            </span>
            <span className="flex-1 h-px" style={{ background: p.divider }} />
          </div>

          <div className="flex flex-col gap-3">
            <OutlinedButton disabled={disabled} onClick={google} leading={<GoogleG />}>
              {googleBusy ? s.waitingForGoogle : s.continueWithGoogle}
            </OutlinedButton>
            <button
              type="button"
              disabled={disabled}
              onClick={() => {
                auth.continueAsGuest();
                navigate('/', { replace: true });
              }}
              className="w-full h-[52px] flex items-center justify-center gap-2.5 rounded-2xl font-label-md text-[16px] font-bold transition hover:brightness-[0.98] disabled:opacity-60"
              style={{ background: p.guestFill, color: p.accent }}
            >
              <Icon name="person" size={22} />
              <span className="truncate">{s.guest}</span>
            </button>
          </div>

          <p className="mt-3.5 flex flex-wrap items-center justify-center gap-x-1 font-body-md text-body-md">
            <span style={{ color: p.muted }}>{s.noAccount}</span>
            <Link to="/signup" className={`${link} px-2 py-1.5 text-[15px]`} style={{ color: p.accent }}>
              {s.signUp}
            </Link>
          </p>
        </main>
      </div>
    </div>
  );
}

/** "Welcome to" / "WeatherGPT!" — or the brand first, for languages where
 *  the welcome follows the name (OnboardingStrings.welcome*). */
function WelcomeTitle({ s }: { s: OnboardingStrings }) {
  const p = usePalette();
  const small = 'font-headline-lg text-[24px] leading-[1.25] font-medium';
  return (
    <h1 aria-label={welcomeLine(s)} className="mt-1 px-6 text-center max-w-full" style={{ color: p.ink }}>
      {s.welcomeBefore && (
        <span aria-hidden="true" className={`block ${small}`}>
          {s.welcomeBefore}
        </span>
      )}
      <span aria-hidden="true" className="block">
        <Wordmark size={38} suffix={s.welcomeBrandSuffix} />
      </span>
      {s.welcomeAfter && (
        <span aria-hidden="true" className={`block ${small}`}>
          {s.welcomeAfter}
        </span>
      )}
    </h1>
  );
}

/** A rounded input with a leading icon and the placeholder inside, as in
 *  the mockup (no floating label). */
function Field({
  icon,
  placeholder,
  error,
  suffix,
  onChange,
  ...input
}: {
  icon: string;
  placeholder: string;
  error: string | null;
  suffix?: ReactNode;
  onChange: (v: string) => void;
  type: string;
  value: string;
  disabled: boolean;
  onBlur: () => void;
  autoComplete: string;
  inputMode?: 'email';
}) {
  const p = usePalette();
  const errId = `onb-${icon}-err`;
  const errorColor = p.isDark ? '#FFB4AB' : '#BA1A1A';
  return (
    <div>
      <div
        className="flex items-center gap-2.5 pl-4 pr-1.5 rounded-2xl border transition-colors focus-within:ring-1"
        style={
          {
            background: p.field,
            borderColor: error ? errorColor : p.fieldBorder,
            '--tw-ring-color': p.accent,
          } as CSSProperties
        }
      >
        <Icon name={icon} size={24} style={{ color: p.ink, opacity: 0.85 }} />
        <input
          {...input}
          placeholder={placeholder}
          aria-label={placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errId : undefined}
          onChange={(e) => onChange(e.target.value)}
          className="onb-input flex-1 min-w-0 bg-transparent border-0 outline-none py-4 font-body-lg text-[16px]"
          style={{ color: p.ink, '--onb-placeholder': p.muted } as CSSProperties}
        />
        {suffix}
      </div>
      {error && (
        <p id={errId} className="mt-1 px-1 font-body-sm text-body-sm" style={{ color: errorColor }}>
          {error}
        </p>
      )}
    </div>
  );
}

/** The outlined "Continue with Google" button. */
function OutlinedButton({
  children,
  leading,
  onClick,
  disabled,
}: {
  children: ReactNode;
  leading: ReactNode;
  onClick: () => void;
  disabled: boolean;
}) {
  const p = usePalette();
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full h-[54px] flex items-center justify-center gap-3 rounded-2xl font-label-md text-[16px] font-semibold transition hover:brightness-105 disabled:opacity-60"
      style={{
        background: p.isDark ? 'transparent' : p.field,
        border: `1.3px solid ${p.isDark ? `${p.accent}CC` : p.fieldBorder}`,
        color: p.ink,
      }}
    >
      {leading}
      <span className="truncate">{children}</span>
    </button>
  );
}

/** Google's four-colour "G". */
function GoogleG() {
  return (
    <svg width="22" height="22" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}
