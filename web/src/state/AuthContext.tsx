// The signed-in account, app-wide (mobile/lib/state/auth_store.dart). App.tsx
// shows the landing page while signed out and the app once signed in or
// browsing as a guest; the Profile page reads the user and signs out here.
//
// Guest mode is local only (the Supabase project has anonymous sign-ins
// off): the full app, no account, no profile. The choice is remembered like
// a session, and signing in from guest mode replaces it.
//
// The session is kept in localStorage, so a user stays signed in across
// visits; on load an expired access token is swapped for a fresh one with
// the refresh token, and a refresh the server rejects signs the user out.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  AuthError,
  isStale,
  refreshSession,
  resendConfirmation,
  sendPasswordReset,
  signIn as apiSignIn,
  signOutRemote,
  signUp as apiSignUp,
  updatePassword,
  updateProfile as apiUpdateProfile,
  verifyRecoveryCode,
  type AuthSession,
  type AuthUser,
  type SignUpResult,
} from '../lib/auth';

export type AuthStatus = 'restoring' | 'signedOut' | 'guest' | 'signedIn';

const STORE_KEY = 'weathergpt.auth';

type Stored = AuthSession | { guest: true };

function readStored(): Stored | null {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Stored) : null;
  } catch {
    return null; // unreadable or no storage — start signed out
  }
}

function writeStored(value: Stored) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(value));
  } catch {
    // Not persisted — the user just signs in again next visit.
  }
}

function clearStored() {
  try {
    localStorage.removeItem(STORE_KEY);
  } catch {
    // Nothing to clear.
  }
}

interface AuthCtx {
  status: AuthStatus;
  session: AuthSession | null;
  user: AuthUser | null;
  isGuest: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  /** Creates the account; the result says whether a confirmation mail must
   *  be opened first. */
  signUp: (details: {
    email: string;
    password: string;
    fullName: string;
    phone: string;
    occupation: string;
  }) => Promise<SignUpResult>;
  resendConfirmation: (email: string) => Promise<void>;
  /** Saves the edited profile to the account and to the saved session. */
  updateProfile: (details: { fullName: string; phone: string; occupation: string }) => Promise<void>;
  sendPasswordReset: (email: string) => Promise<void>;
  /** A working access token for the backend (refreshed first if it has
   *  expired), or null for a guest / signed-out visitor or a failed refresh. */
  getAccessToken: () => Promise<string | null>;
  /** Checks the emailed reset code, sets the new password, and signs in. */
  resetPassword: (details: { email: string; code: string; newPassword: string }) => Promise<void>;
  /** Use the app without an account. */
  continueAsGuest: () => void;
  /** Signs out, or leaves guest mode; either way back to the landing page. */
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('restoring');
  const [session, setSession] = useState<AuthSession | null>(null);

  const adopt = useCallback((s: AuthSession) => {
    setSession(s);
    setStatus('signedIn');
    writeStored(s);
  }, []);

  // Load a saved session, refreshing it if it has expired.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = readStored();
      if (stored && 'guest' in stored && stored.guest === true) {
        setStatus('guest');
        return;
      }
      let saved = stored && 'accessToken' in stored ? stored : null;
      if (saved && isStale(saved)) {
        try {
          saved = await refreshSession(saved.refreshToken);
          writeStored(saved);
        } catch (err) {
          // Offline: keep the user signed in with what we have; the next
          // visit retries. Rejected by the server: sign out.
          if (err instanceof AuthError && err.code !== undefined) {
            saved = null;
            clearStored();
          }
        }
      }
      if (cancelled) return;
      setSession(saved);
      setStatus(saved ? 'signedIn' : 'signedOut');
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({
      status,
      session,
      user: session?.user ?? null,
      isGuest: status === 'guest',
      signIn: async (email, password) => adopt(await apiSignIn(email.trim(), password)),
      signUp: async (d) => {
        const result = await apiSignUp({
          email: d.email.trim(),
          password: d.password,
          fullName: d.fullName.trim(),
          phone: d.phone.trim(),
          occupation: d.occupation.trim(),
        });
        if (result.session) adopt(result.session);
        return result;
      },
      resendConfirmation: (email) => resendConfirmation(email.trim()),
      updateProfile: async (d) => {
        if (!session) throw new AuthError('You are signed out. Sign in again to continue.');
        // Refresh an expired access token first.
        let current = session;
        if (isStale(current)) {
          current = await refreshSession(current.refreshToken);
          adopt(current);
        }
        const user = await apiUpdateProfile(current.accessToken, {
          fullName: d.fullName.trim(),
          phone: d.phone.trim(),
          occupation: d.occupation.trim(),
        });
        adopt({ ...current, user });
      },
      sendPasswordReset: (email) => sendPasswordReset(email.trim()),
      getAccessToken: async () => {
        if (!session) return null;
        if (!isStale(session)) return session.accessToken;
        try {
          const fresh = await refreshSession(session.refreshToken);
          adopt(fresh);
          return fresh.accessToken;
        } catch {
          return null;
        }
      },
      resetPassword: async (d) => {
        const recovered = await verifyRecoveryCode(d.email.trim(), d.code.trim());
        const user = await updatePassword(recovered.accessToken, d.newPassword);
        adopt({ ...recovered, user });
      },
      continueAsGuest: () => {
        setSession(null);
        setStatus('guest');
        writeStored({ guest: true });
      },
      signOut: async () => {
        const previous = session;
        setSession(null);
        setStatus('signedOut');
        clearStored();
        if (previous) {
          try {
            await signOutRemote(previous.accessToken);
          } catch {
            // Already expired or offline — the local session is gone either way.
          }
        }
      },
    }),
    [status, session, adopt],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
