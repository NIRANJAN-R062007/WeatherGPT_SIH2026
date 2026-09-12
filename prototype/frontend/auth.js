// Supabase Google OAuth (plan.md §14 Deepthi track).
//
// Chelsea: wire the login button to WeatherGPTAuth.signInWithGoogle(), read
// the signed-in user via WeatherGPTAuth.getSession(), and subscribe with
// WeatherGPTAuth.onChange(cb) to update the UI when it changes. To call a
// protected backend endpoint (e.g. Abel's /history), send the session's
// access_token as `Authorization: Bearer <token>`.
//
// Requires the Supabase JS CDN script tag before this file:
//   <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js"></script>

const SUPABASE_URL = "https://bkohiigdngppywnzakvg.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrb2hpaWdkbmdwcHl3bnpha3ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkyMTk5MjUsImV4cCI6MjEwNDc5NTkyNX0.55NOTKMwx0--h1KL32g-M2gSYEJnVfNMbPuBJehYoek";

const _client = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function signInWithGoogle() {
  const { error } = await _client.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: window.location.origin + window.location.pathname },
  });
  if (error) console.error("Sign-in failed:", error);
}

async function signOut() {
  const { error } = await _client.auth.signOut();
  if (error) console.error("Sign-out failed:", error);
}

async function getSession() {
  const { data, error } = await _client.auth.getSession();
  if (error) {
    console.error("getSession failed:", error);
    return null;
  }
  return data.session; // null when signed out
}

function onChange(callback) {
  const { data } = _client.auth.onAuthStateChange((_event, session) => callback(session));
  return data.subscription; // caller can .unsubscribe() if needed
}

window.WeatherGPTAuth = { signInWithGoogle, signOut, getSession, onChange };
