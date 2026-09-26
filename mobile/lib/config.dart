// Orchestrator base URL. Override at build/run time with:
//   flutter run --dart-define=API_BASE_URL=https://3-108-52-61.sslip.io
// Defaults to the same localhost:8001 convention as web/.env.example and
// prototype/frontend/WeatherGPT.dc.html.
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8001',
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
