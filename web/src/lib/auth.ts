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
    default:
      message =
        status === 429
          ? 'Too many attempts. Please wait a minute and try again.'
          : (raw ?? `Sign-in failed (HTTP ${status}). Please try again.`);
  }
  return new AuthError(message, code);
}

async function post(path: string, body: Json | null, accessToken?: string): Promise<Json> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AUTH_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
      method: 'POST',
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
  const data = await post('signup', {
    email: details.email,
    password: details.password,
    data: { full_name: details.fullName, phone: details.phone, occupation: details.occupation },
  });
  return { email: details.email, session: typeof data.access_token === 'string' ? sessionFromJson(data) : null };
}

/** Sends the confirmation mail again. */
export async function resendConfirmation(email: string): Promise<void> {
  await post('resend', { type: 'signup', email });
}

export async function refreshSession(refreshToken: string): Promise<AuthSession> {
  return sessionFromJson(await post('token?grant_type=refresh_token', { refresh_token: refreshToken }));
}

/** Revokes the session server-side. Best effort — the caller forgets the
 *  session locally either way. */
export async function signOutRemote(accessToken: string): Promise<void> {
  await post('logout', null, accessToken);
}
