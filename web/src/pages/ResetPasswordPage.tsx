// Forgot password, from the sign-in form (mobile reset_password_page.dart).
// Two steps, no redirect link: Supabase mails a code, the user types it here
// with a new password, and a correct code signs them in. The code only
// appears in the mail once the project's "Reset password" template includes
// {{ .Token }} (dashboard).
import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FormMessage, GradientButton, OutlineButton, SubPage, TextField } from '../components/forms';
import PageFrame from '../components/PageFrame';
import { Icon, PageHeader } from '../components/ui';
import { AuthError } from '../lib/auth';
import { validateEmail, validateNewPassword } from '../lib/validate';
import { useAuth } from '../state/AuthContext';
import { useT } from '../lib/i18n';

const CODE = /^\d{6,10}$/;

function validateCode(v: string) {
  const s = v.trim();
  if (!s) return 'Enter the code from the email.';
  if (!CODE.test(s)) return 'The code is the digits from the email.';
  return null;
}

export default function ResetPasswordPage() {
  const t = useT();
  const auth = useAuth();
  const navigate = useNavigate();
  const carried = (useLocation().state as { email?: unknown } | null)?.email;
  const [email, setEmail] = useState(typeof carried === 'string' ? carried : '');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const errors = {
    email: validateEmail(email),
    code: validateCode(code),
    password: validateNewPassword(password),
    confirm: confirm !== password ? "Passwords don't match." : null,
  };
  const shown = (f: keyof typeof errors) => (submitted && errors[f]) || null;

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof AuthError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const sendCode = (again = false) =>
    run(async () => {
      await auth.sendPasswordReset(email);
      setCodeSent(true);
      setSubmitted(false);
      setNotice(
        t(again ? 'A new code is on its way to {email}.' : 'We sent a reset code to {email}.', { email: email.trim() }),
      );
    });

  const submitEmail = (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (errors.email) return;
    void sendCode();
  };

  const submitReset = (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (errors.code || errors.password || errors.confirm) return;
    void run(async () => {
      await auth.resetPassword({ email, code, newPassword: password });
      navigate('/', { replace: true });
    });
  };

  const passwordToggle = (
    <button
      type="button"
      onClick={() => setShowPassword((s) => !s)}
      aria-label={t(showPassword ? 'Hide password' : 'Show password')}
      title={t(showPassword ? 'Hide password' : 'Show password')}
      className="p-2 rounded-full text-ink-muted hover:bg-tint"
    >
      <Icon name={showPassword ? 'visibility_off' : 'visibility'} size={20} />
    </button>
  );

  const messages = (
    <>
      {error && <FormMessage text={error} error />}
      {notice && <FormMessage text={notice} />}
    </>
  );

  return (
    <SubPage>
      <PageFrame showCityPill={false} footer="soft">
        <div className="mx-auto max-w-md">
          <PageHeader
            title="Reset your password"
            subtitle={
              codeSent
                ? 'Enter the code from the email and choose a new password.'
                : "Enter your account's email and we'll send you a reset code."
            }
          />
          {codeSent ? (
            <form noValidate onSubmit={submitReset} className="mt-space-lg flex flex-col gap-3.5">
              <TextField
                label="Reset code"
                icon="pin"
                name="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                hint="123456"
                value={code}
                disabled={busy}
                error={shown('code')}
                onChange={(e) => setCode(e.target.value)}
              />
              <TextField
                label="New password"
                icon="lock"
                name="new-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                suffix={passwordToggle}
                value={password}
                disabled={busy}
                error={shown('password')}
                onChange={(e) => setPassword(e.target.value)}
              />
              <TextField
                label="Confirm new password"
                icon="lock"
                name="confirm-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirm}
                disabled={busy}
                error={shown('confirm')}
                onChange={(e) => setConfirm(e.target.value)}
              />
              {messages}
              <div className="mt-2 flex flex-col gap-3">
                <GradientButton type="submit" label="Set new password" loading={busy} />
                <OutlineButton
                  label="Send a new code"
                  icon="forward_to_inbox"
                  disabled={busy}
                  onClick={() => void sendCode(true)}
                />
              </div>
            </form>
          ) : (
            <form noValidate onSubmit={submitEmail} className="mt-space-lg flex flex-col gap-3.5">
              <TextField
                label="Email"
                icon="mail"
                name="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                value={email}
                disabled={busy}
                error={shown('email')}
                onChange={(e) => setEmail(e.target.value)}
              />
              {messages}
              <div className="mt-2">
                <GradientButton type="submit" label="Send reset code" loading={busy} />
              </div>
            </form>
          )}
        </div>
      </PageFrame>
    </SubPage>
  );
}
