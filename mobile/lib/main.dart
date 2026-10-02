// WeatherGPT mobile — same product as web/: the shell and page set mirror
// web/src/ (lib/components/app_shell.dart); the look follows the selected
// persona (lib/persona_theme.dart). Every page reads live orchestrator data:
// /facts, /ask, /asr, /tts and /warnings.
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'cities_client.dart';
import 'components/app_shell.dart';
import 'config.dart';
import 'pages/alerts_page.dart';
import 'pages/chat_page.dart';
import 'pages/forecast_page.dart';
import 'pages/home_page.dart';
import 'pages/onboarding_pages.dart';
import 'pages/settings_page.dart';
import 'persona_theme.dart';
import 'state/auth_store.dart';
import 'state/prefs_store.dart';
import 'state/ui_prefs.dart';
import 'state/weather_store.dart';
import 'theme.dart';

void main() {
  final configError = releaseConfigError();
  runApp(configError == null ? const WeatherGptApp() : ConfigErrorApp(configError));
}

/// Shown instead of the app when a release build was made with an insecure
/// API or Supabase URL ([releaseConfigError]), so it never sends a token
/// over plain http.
class ConfigErrorApp extends StatelessWidget {
  final String message;
  const ConfigErrorApp(this.message, {super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    home: Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(padding: const EdgeInsets.all(24), child: Text(message, textAlign: TextAlign.center)),
        ),
      ),
    ),
  );
}

class WeatherGptApp extends StatefulWidget {
  /// The account store; tests pass one with a preset session.
  final AuthStore? auth;

  /// Where the settings are remembered; tests pass one in memory.
  final PrefsStore? prefsStore;

  /// Where the city list comes from (GET /cities); tests pass a stub.
  final CitiesFetcher citiesFetcher;
  const WeatherGptApp({super.key, this.auth, this.prefsStore, this.citiesFetcher = fetchCities});

  @override
  State<WeatherGptApp> createState() => _WeatherGptAppState();
}

class _WeatherGptAppState extends State<WeatherGptApp> {
  final UiPrefs _prefs = UiPrefs();
  final WeatherStore _weather = WeatherStore();
  late final AuthStore _auth = widget.auth ?? AuthStore();
  late final PrefsStore _prefsStore = widget.prefsStore ?? FilePrefsStore();

  /// What was last written; null until the saved settings have been read, so
  /// nothing overwrites them before they are applied.
  Map<String, String>? _saved;

  @override
  void initState() {
    super.initState();
    if (_auth.status == AuthStatus.restoring) _auth.restore();
    // The hero and Forecast share one /facts load, redone on a city or
    // language change (condition labels come back localized).
    _weather.load(_prefs.city, _prefs.lang);
    _prefs.addListener(_onPrefsChanged);
    _restorePrefs();
    // The cities this server answers for; the bundled list until it answers,
    // or for good if it can't be reached.
    widget.citiesFetcher().then((cities) {
      if (cities != null && mounted) _prefs.cities = cities;
    });
  }

  /// The settings from an earlier launch, except any the user has already
  /// changed in the moments since this launch began.
  Future<void> _restorePrefs() async {
    final atLaunch = _prefs.toSaved();
    final saved = await _prefsStore.read();
    if (!mounted) return;
    final now = _prefs.toSaved();
    _saved = saved ?? const {};
    _prefs.applySaved(saved ?? const {}, keep: {for (final k in now.keys) if (now[k] != atLaunch[k]) k});
    _save();
  }

  void _onPrefsChanged() {
    _weather.ensureLoaded(_prefs.city, _prefs.lang);
    _save();
  }

  void _save() {
    final saved = _saved;
    if (saved == null) return; // not read yet
    final now = _prefs.toSaved();
    if (mapEquals(saved, now)) return;
    _saved = now;
    _prefsStore.write(now);
  }

  @override
  void dispose() {
    _prefs.removeListener(_onPrefsChanged);
    _prefs.dispose();
    _weather.dispose();
    if (widget.auth == null) _auth.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AuthScope(
      store: _auth,
      child: UiPrefsScope(
        prefs: _prefs,
        child: WeatherScope(
          store: _weather,
          // The selected persona is the app-wide theme: a persona change
          // rebuilds the theme and MaterialApp cross-fades every page to it.
          child: ListenableBuilder(
            listenable: _prefs,
            builder: (context, home) => MaterialApp(
              title: 'WeatherGPT',
              debugShowCheckedModeBanner: false,
              theme: buildAppTheme(personaThemeFor(_prefs.persona)),
              darkTheme: buildAppTheme(personaThemeFor(_prefs.persona, Brightness.dark)),
              themeMode: _prefs.themeMode,
              themeAnimationDuration: const Duration(milliseconds: 350),
              // Status-bar and navigation-bar icons follow light / dark.
              builder: (context, child) {
                final t = PersonaTheme.of(context);
                return AnnotatedRegion<SystemUiOverlayStyle>(
                  value: (t.isDark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
                    statusBarColor: Colors.transparent,
                    systemNavigationBarColor: t.navBar,
                    systemNavigationBarIconBrightness: t.isDark ? Brightness.light : Brightness.dark,
                  ),
                  child: child!,
                );
              },
              home: home,
            ),
            child: const _AuthGate(),
          ),
        ),
      ),
    );
  }
}

/// Signed out → onboarding: the language page, then welcome + log in; signed
/// in or guest → the app. Signing out (or leaving guest mode) from Profile
/// lands back on the language page.
class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    return switch (AuthStore.of(context).status) {
      AuthStatus.restoring => const _Splash(),
      AuthStatus.signedOut => const LanguagePage(),
      AuthStatus.signedIn || AuthStatus.guest => AppShell(
        pages: {
          AppPage.home: (_) => const HomePage(),
          AppPage.chat: (_) => const ChatPage(),
          AppPage.forecast: (_) => const ForecastPage(),
          AppPage.alerts: (_) => const AlertsPage(),
          AppPage.settings: (_) => const SettingsPage(),
        },
      ),
    };
  }
}

/// The moment between launch and the saved session being read.
class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Scaffold(
      backgroundColor: t.skyBottom,
      body: DecoratedBox(
        decoration: BoxDecoration(gradient: t.skyGradient),
        child: const Center(child: BrandMark(size: 72)),
      ),
    );
  }
}
