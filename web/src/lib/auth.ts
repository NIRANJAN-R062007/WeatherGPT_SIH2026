// Email + password accounts on the team's Supabase project, via Supabase
// Auth's REST API (GoTrue) — the same project prototype/frontend/auth.js
// signs in to with Google, and the same client as mobile/lib/auth_client.dart.
// The profile fields the app shows (name, phone, occupation) live in the
// account's user_metadata, so they follow the user to any device. The
// project requires email confirmation, so a fresh sign-up returns no session
// until the link in the confirmation mail is opened.

// `or default`, not `??`: an env var set but empty must fall back too.
const env = (v: unknown, fallback: string) => (typeof v === 'string' && v.trim() !== '' ? v.trim() : fallback);

/** The anon key is public by design — Supabase's row-level security, not
 *  the key, guards the data. Override with VITE_SUPABASE_URL /
 *  VITE_SUPABASE_ANON_KEY for another project. */
export const SUPABASE_URL = env(
  import.meta.env.VITE_SUPABASE_URL,
  'https://bkohiigdngppywnzakvg.supabase.co',
).replace(/\/+$/, '');
export const SUPABASE_ANON_KEY = env(
  import.meta.env.VITE_SUPABASE_ANON_KEY,
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrb2hpaWdkbmdwcHl3bnpha3ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkyMTk5MjUsImV4cCI6MjEwNDc5NTkyNX0.55NOTKMwx0--h1KL32g-M2gSYEJnVfNMbPuBJehYoek',
);

/** Where the confirmation link in a sign-up mail lands: the hosted page that
 *  says the email is confirmed and to come back here and sign in
 *  (prototype/frontend/email-confirmed.html, on Amplify). Must be listed
 *  under Supabase → Authentication → URL Configuration → Redirect URLs. */
export const EMAIL_CONFIRMED_URL = `${env(
  import.meta.env.VITE_EMAIL_CONFIRMED_URL,
  'https://main.d2fpifryktvg3k.amplifyapp.com/email-confirmed.html',
)}?from=web`;
const confirmRedirect = `redirect_to=${encodeURIComponent(EMAIL_CONFIRMED_URL)}`;

const AUTH_TIMEOUT_MS = 15_000;

export class AuthError extends Error {
  /** GoTrue's `error_code` ("invalid_credentials", "email_not_confirmed", …)
   *  when it sent one. */
  readonly code: string | undefined;

  constructor(message: string, code?: string) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
  }

  get emailNotConfirmed() {
    return this.code === 'email_not_confirmed';
  }
}

/** The signed-in account, as Supabase returns it. */
export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  phone: string;
  occupation: string;
  /** ISO timestamp. */
  createdAt: string | null;
}

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  /** Epoch seconds when accessToken stops working. */
  expiresAt: number;
  user: AuthUser;
}

type Json = Record<string, unknown>;
const str = (v: unknown) => (typeof v === 'string' ? v.trim() : '');

export function userFromJson(j: Json): AuthUser {
  const meta = (j.user_metadata && typeof j.user_metadata === 'object' ? j.user_metadata : {}) as Json;
  return {
    id: str(j.id),
    email: str(j.email),
    fullName: str(meta.full_name) || str(meta.name),
    phone: str(meta.phone) || str(j.phone),
    occupation: str(meta.occupation),
    createdAt: str(j.created_at) || null,
  };
}

export function sessionFromJson(j: Json): AuthSession {
  const expiresAt =
    typeof j.expires_at === 'number'
      ? j.expires_at
      : Math.floor(Date.now() / 1000) + (typeof j.expires_in === 'number' ? j.expires_in : 3600);
  if (typeof j.access_token !== 'string' || typeof j.refresh_token !== 'string' || !j.user) {
    throw new AuthError("The sign-in service's reply didn't include a session.");
  }
  return {
    accessToken: j.access_token,
    refreshToken: j.refresh_token,
    expiresAt,
    user: userFromJson(j.user as Json),
  };
}

/** Expired, or will be within a minute. */
export const isStale = (s: AuthSession) => Date.now() / 1000 > s.expiresAt - 60;

/** Name if given, else the part of the email before the @. */
export const displayName = (u: AuthUser) => u.fullName || u.email.split('@')[0];

export function initials(u: AuthUser) {
  const parts = displayName(u).split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  const first = [...parts[0]][0];
  const last = parts.length > 1 ? [...parts[parts.length - 1]][0] : '';
  return (first + last).toUpperCase();
}

function friendlyError(status: number, data: Json): AuthError {
  const code = (str(data.error_code) || str(data.error)) || undefined;
  const raw = str(data.msg) || str(data.error_description) || str(data.message) || undefined;
  let message: string;
  switch (code) {
    case 'invalid_credentials':
    case 'invalid_grant':
      message = 'Wrong email or password.';
      break;
    case 'email_not_confirmed':
      message = 'Please confirm your email first — open the link we sent to your inbox.';
      break;
    case 'user_already_exists':
    case 'email_exists':
      message = 'An account with this email already exists. Sign in instead.';
      break;
    case 'weak_password':
      message = raw ?? 'Please choose a stronger password.';
      break;
    case 'over_email_send_rate_limit':
    case 'over_request_rate_limit':
      message = 'Too many attempts. Please wait a minute and try again.';
      break;
    case 'validation_failed':
    case 'email_address_invalid':
      message = raw ?? 'Please check the details you entered.';
      break;
    case 'otp_expired':
    case 'otp_disabled':
      message = 'That code is wrong or has expired. Request a new one.';
      break;
    case 'same_password':
      message = 'Choose a password different from your current one.';
      break;
    default:
      message =
        status === 429
          ? 'Too many attempts. Please wait a minute and try again.'
          : (raw ?? `Sign-in failed (HTTP ${status}). Please try again.`);
  }
  return new AuthError(message, code);
}

const post = (path: string, body: Json | null, accessToken?: string) => send('POST', path, body, accessToken);

async function send(method: 'POST' | 'PUT', path: string, body: Json | null, accessToken?: string): Promise<Json> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AUTH_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
      method,
      signal: controller.signal,
      headers: {
        apikey: SUPABASE_ANON_KEY,
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken ?? SUPABASE_ANON_KEY}`,
      },
      body: body === null ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new AuthError('The sign-in service took too long to answer. Check your connection and try again.');
    }
    throw new AuthError("Couldn't reach the sign-in service. Check your internet connection.");
  } finally {
    clearTimeout(timer);
  }
  let data: Json = {};
  try {
    const text = await res.text();
    if (text) {
      const parsed: unknown = JSON.parse(text);
      if (parsed && typeof parsed === 'object') data = parsed as Json;
    }
  } catch {
    // Not JSON — the status alone decides.
  }
  if (res.ok) return data;
  throw friendlyError(res.status, data);
}

export async function signIn(email: string, password: string): Promise<AuthSession> {
  return sessionFromJson(await post('token?grant_type=password', { email, password }));
}

/** What a sign-up produced: a session straight away (projects without email
 *  confirmation) or a confirmation mail to open first (this project). */
export interface SignUpResult {
  email: string;
  session: AuthSession | null;
}

export async function signUp(details: {
  email: string;
  password: string;
  fullName: string;
  phone: string;
  occupation: string;
}): Promise<SignUpResult> {
  const data = await post(`signup?${confirmRedirect}`, {
    email: details.email,
    password: details.password,
    data: { full_name: details.fullName, phone: details.phone, occupation: details.occupation },
  });
  return { email: details.email, session: typeof data.access_token === 'string' ? sessionFromJson(data) : null };
}

/** Sends the confirmation mail again. */
export async function resendConfirmation(email: string): Promise<void> {
  await post(`resend?${confirmRedirect}`, { type: 'signup', email });
}

export async function refreshSession(refreshToken: string): Promise<AuthSession> {
  return sessionFromJson(await post('token?grant_type=refresh_token', { refresh_token: refreshToken }));
}

/** Saves name, phone and occupation to the account's user_metadata and
 *  returns the updated user. */
export async function updateProfile(
  accessToken: string,
  details: { fullName: string; phone: string; occupation: string },
): Promise<AuthUser> {
  const data = await send(
    'PUT',
    'user',
    { data: { full_name: details.fullName, phone: details.phone, occupation: details.occupation } },
    accessToken,
  );
  return userFromJson(data);
}

/** Mails a password-reset code. The mail template has to include
 *  `{{ .Token }}` for the code to appear (Supabase dashboard setting). */
export async function sendPasswordReset(email: string): Promise<void> {
  await post('recover', { email });
}

/** Trades the emailed reset code for a session that may set a new password. */
export async function verifyRecoveryCode(email: string, code: string): Promise<AuthSession> {
  return sessionFromJson(await post('verify', { type: 'recovery', email, token: code }));
}

export async function updatePassword(accessToken: string, password: string): Promise<AuthUser> {
  return userFromJson(await send('PUT', 'user', { password }, accessToken));
}

// Google sign-in: Supabase's OAuth with PKCE, the same flow as mobile
// google_auth.dart. The browser leaves for /auth/v1/authorize, Supabase
// hands over to Google, and Google's answer comes back to `redirectTo` with
// a `code` (or an error), which is traded for a session with the verifier
// kept in sessionStorage. `redirectTo` must be listed under Supabase →
// Authentication → URL Configuration → Redirect URLs, or Supabase falls back
// to the Site URL and the app never hears back.

const PKCE_KEY = 'weathergpt.pkce';

const base64Url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');

/** Sends the browser to Google; resolves only if it couldn't leave. */
export async function startGoogleSignIn(redirectTo: string): Promise<void> {
  if (!crypto.subtle) throw new AuthError('Google sign-in needs a secure (https) page.');
  const verifier = base64Url(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = base64Url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  try {
    sessionStorage.setItem(PKCE_KEY, verifier);
  } catch {
    throw new AuthError("Google sign-in needs this site's storage. Allow it and try again.");
  }
  const query = new URLSearchParams({
    provider: 'google',
    redirect_to: redirectTo,
    code_challenge: challenge,
    code_challenge_method: 's256',
  });
  window.location.assign(`${SUPABASE_URL}/auth/v1/authorize?${query}`);
}

/** The session from a Google redirect on the current URL, or null when the
 *  URL isn't one. Throws AuthError with Google's / Supabase's reason when
 *  the redirect carries an error instead of a code. */
export async function finishGoogleSignIn(url: URL): Promise<AuthSession | null> {
  const hash = new URLSearchParams(url.hash.replace(/^#/, ''));
  const error = url.searchParams.get('error_description') ?? hash.get('error_description');
  const code = url.searchParams.get('code');
  let verifier: string | null = null;
  try {
    verifier = sessionStorage.getItem(PKCE_KEY);
    if (code || error) sessionStorage.removeItem(PKCE_KEY);
  } catch {
    // No storage — no verifier.
  }
  if (error) throw new AuthError(error.replace(/\+/g, ' '), 'google_error');
  if (!code || !verifier) return null;
  return sessionFromJson(await post('token?grant_type=pkce', { auth_code: code, code_verifier: verifier }));
}

/** Revokes the session server-side. Best effort — the caller forgets the
 *  session locally either way. */
export async function signOutRemote(accessToken: string): Promise<void> {
  await post('logout', null, accessToken);
}
