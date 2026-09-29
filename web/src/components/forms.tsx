// Form pieces for the landing, sign-in and profile pages, in the active
// persona's colours (mobile/lib/components/forms.dart): the sky-backed
// sub-page scaffold, the rounded text field, the two button styles (accent
// gradient, outlined) and the "Continue as guest" link.
import type { InputHTMLAttributes, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../state/AuthContext';
import { BrandTitle } from './Brand';
import { Icon, Spinner } from './ui';

/** Sky gradient, a back arrow + WeatherGPT bar, then `children` — the pages
 *  outside the app shell (sign in / create account). */
export function SubPage({ children, backTo }: { children: ReactNode; backTo?: string }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex flex-col bg-sky-gradient">
      <header className="h-14 flex items-center gap-1 px-1 sm:px-space-md">
        <button
          type="button"
          aria-label="Back"
          onClick={() => (backTo ? navigate(backTo) : navigate(-1))}
          className="p-2.5 rounded-full text-ink hover:bg-ink/5"
        >
          <Icon name="arrow_back" size={24} />
        </button>
        <BrandTitle />
      </header>
      {children}
    </div>
  );
}

/** A labelled, rounded input on a card with a persona-tinted border. */
export function TextField({
  label,
  icon,
  error,
  suffix,
  hint,
  ...input
}: {
  label: string;
  icon: string;
  error?: string | null;
  suffix?: ReactNode;
  hint?: string;
} & InputHTMLAttributes<HTMLInputElement>) {
  const id = input.id ?? `f-${input.name ?? label.replace(/\s+/g, '-').toLowerCase()}`;
  return (
    <div>
      <label htmlFor={id} className="block mb-1 font-label-md text-label-md font-semibold text-ink-muted">
        {label}
      </label>
      <div
        className={`flex items-center gap-2 pl-3.5 pr-1.5 rounded-card bg-card border transition-colors ${
          error ? 'border-error' : 'border-card-border focus-within:border-primary focus-within:ring-1 focus-within:ring-primary'
        } ${input.disabled ? 'opacity-70' : ''}`}
      >
        <Icon name={icon} size={20} className="text-primary" />
        <input
          id={id}
          placeholder={hint}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-err` : undefined}
          className="flex-1 min-w-0 bg-transparent border-0 outline-none py-3.5 font-body-md text-body-md text-ink placeholder:text-outline"
          {...input}
        />
        {suffix}
      </div>
      {error && (
        <p id={`${id}-err`} className="mt-1 font-body-sm text-body-sm text-error">
          {error}
        </p>
      )}
    </div>
  );
}

/** Full-width accent-gradient button; shows a spinner while `loading`. */
export function GradientButton({
  label,
  icon,
  onClick,
  loading = false,
  disabled = false,
  type = 'button',
}: {
  label: string;
  icon?: string;
  onClick?: () => void;
  loading?: boolean;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className="w-full h-[52px] flex items-center justify-center gap-2 rounded-card bg-accent-gradient text-on-primary font-label-md text-[15px] font-bold shadow-[0_5px_14px_rgb(var(--c-primary)/0.28)] transition hover:brightness-105 active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed"
    >
      {loading ? (
        <Spinner className="w-[22px] h-[22px] border-on-primary/35 border-t-on-primary" />
      ) : (
        <>
          <span className="truncate">{label}</span>
          {icon && <Icon name={icon} size={18} />}
        </>
      )}
    </button>
  );
}

/** Full-width card-coloured button with an accent outline (secondary
 *  action), or a red one for destructive actions like signing out. */
export function OutlineButton({
  label,
  icon,
  onClick,
  destructive = false,
  disabled = false,
}: {
  label: string;
  icon?: string;
  onClick?: () => void;
  destructive?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`w-full h-[52px] flex items-center justify-center gap-2 rounded-card bg-card border-[1.4px] font-label-md text-[15px] font-bold transition hover:bg-tint disabled:opacity-60 disabled:cursor-not-allowed ${
        destructive ? 'text-error border-error/55' : 'text-primary border-primary/55'
      }`}
    >
      {icon && <Icon name={icon} size={19} />}
      <span className="truncate">{label}</span>
    </button>
  );
}

/** An inline error (red) or notice (persona tint) under a form. */
export function FormMessage({ text, error = false }: { text: string; error?: boolean }) {
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

/** "Continue as guest": the whole app without an account. */
export function GuestButton({ disabled = false }: { disabled?: boolean }) {
  const { continueAsGuest } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex justify-center">
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          continueAsGuest();
          navigate('/', { replace: true });
        }}
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full font-label-md text-[14px] font-semibold text-ink-muted hover:bg-tint disabled:opacity-60"
      >
        <Icon name="person" size={18} />
        Continue as guest
      </button>
    </div>
  );
}
