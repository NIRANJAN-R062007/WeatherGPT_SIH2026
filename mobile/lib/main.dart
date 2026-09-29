// WeatherGPT mobile — same product as web/: the shell and page set mirror
// web/src/ (lib/components/app_shell.dart); the look follows the selected
// persona (lib/persona_theme.dart). Every page reads live orchestrator data:
// /facts, /ask, /asr, /tts and /warnings.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'components/app_shell.dart';
import 'pages/alerts_page.dart';
import 'pages/chat_page.dart';
import 'pages/forecast_page.dart';
import 'pages/home_page.dart';
import 'pages/landing_page.dart';
import 'pages/settings_page.dart';
import 'persona_theme.dart';
import 'state/auth_store.dart';
import 'state/ui_prefs.dart';
import 'state/weather_store.dart';
import 'theme.dart';

void main() {
  runApp(const WeatherGptApp());
}

class WeatherGptApp extends StatefulWidget {
  /// The account store; tests pass one with a preset session.
  final AuthStore? auth;
  const WeatherGptApp({super.key, this.auth});

  @override
  State<WeatherGptApp> createState() => _WeatherGptAppState();
}

class _WeatherGptAppState extends State<WeatherGptApp> {
  final UiPrefs _prefs = UiPrefs();
  final WeatherStore _weather = WeatherStore();
  late final AuthStore _auth = widget.auth ?? AuthStore();

  @override
  void initState() {
    super.initState();
    if (_auth.status == AuthStatus.restoring) _auth.restore();
    // The hero and Forecast share one /facts load, redone on a city or
    // language change (condition labels come back localized).
    _weather.load(_prefs.city, _prefs.lang);
    _prefs.addListener(_syncWeather);
  }

  void _syncWeather() => _weather.ensureLoaded(_prefs.city, _prefs.lang);

  @override
  void dispose() {
    _prefs.removeListener(_syncWeather);
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

/// Signed out → the landing page (sign in / create account / guest); signed
/// in or guest → the app. Signing out (or leaving guest mode) from Profile
/// lands back on the landing page.
class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    return switch (AuthStore.of(context).status) {
      AuthStatus.restoring => const _Splash(),
      AuthStatus.signedOut => const LandingPage(),
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
