// Orchestrator base URL. Override at build/run time with:
//   flutter run --dart-define=API_BASE_URL=https://3-108-52-61.sslip.io
// Defaults to the same localhost:8001 convention as web/.env.example and
// prototype/frontend/WeatherGPT.dc.html.
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8001',
);

/// The team's Supabase project (the same one prototype/frontend/auth.js
/// signs in with). The anon key is public by design — Supabase's row-level
/// security, not the key, guards the data. Override with
/// --dart-define=SUPABASE_URL=… / SUPABASE_ANON_KEY=… for another project.
const String kSupabaseUrl = String.fromEnvironment(
  'SUPABASE_URL',
  defaultValue: 'https://bkohiigdngppywnzakvg.supabase.co',
);
const String kSupabaseAnonKey = String.fromEnvironment(
  'SUPABASE_ANON_KEY',
  defaultValue:
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrb2hpaWdkbmdwcHl3bnpha3ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkyMTk5MjUsImV4cCI6MjEwNDc5NTkyNX0.55NOTKMwx0--h1KL32g-M2gSYEJnVfNMbPuBJehYoek',
);

/// Where the confirmation link in a sign-up mail lands: the hosted page that
/// says the email is confirmed and to go back to the app and sign in
/// (prototype/frontend/email-confirmed.html, on Amplify). Must be listed
/// under Supabase → Authentication → URL Configuration → Redirect URLs.
const String kEmailConfirmedUrl = String.fromEnvironment(
  'EMAIL_CONFIRMED_URL',
  defaultValue: 'https://main.d2fpifryktvg3k.amplifyapp.com/email-confirmed.html',
);

/// i18n.SUPPORTED_LANGUAGES, services/orchestrator/i18n.py:35 — fixed enum,
/// not derived at runtime.
const List<String> kSupportedLanguages = ['en', 'hi', 'ta', 'te', 'mr'];

const Map<String, String> kLanguageLabels = {
  'en': 'English',
  'hi': 'हिन्दी',
  'ta': 'தமிழ்',
  'te': 'తెలుగు',
  'mr': 'मराठी',
};

/// Shown in Settings > About; keep in step with pubspec.yaml's `version`.
const String kAppVersion = '1.0.0';
