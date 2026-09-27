// WeatherGPT mobile — same product, same look as web/: the shell, page set
// and visual tokens mirror web/src/ (see lib/theme.dart and
// lib/components/app_shell.dart). Every page reads live orchestrator data:
// /facts, /ask, /asr, /tts and /warnings.
import 'package:flutter/material.dart';

import 'components/app_shell.dart';
import 'pages/alerts_page.dart';
import 'pages/chat_page.dart';
import 'pages/forecast_page.dart';
import 'pages/home_page.dart';
import 'pages/settings_page.dart';
import 'state/ui_prefs.dart';
import 'state/weather_store.dart';
import 'theme.dart';

void main() {
  runApp(const WeatherGptApp());
}

class WeatherGptApp extends StatefulWidget {
  const WeatherGptApp({super.key});

  @override
  State<WeatherGptApp> createState() => _WeatherGptAppState();
}

class _WeatherGptAppState extends State<WeatherGptApp> {
  final UiPrefs _prefs = UiPrefs();
  final WeatherStore _weather = WeatherStore();

  @override
  void initState() {
    super.initState();
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
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return UiPrefsScope(
      prefs: _prefs,
      child: WeatherScope(
        store: _weather,
        child: MaterialApp(
          title: 'WeatherGPT',
          debugShowCheckedModeBanner: false,
          theme: buildAppTheme(),
          home: AppShell(pages: {
            AppPage.home: (_) => const HomePage(),
            AppPage.chat: (_) => const ChatPage(),
            AppPage.forecast: (_) => const ForecastPage(),
            AppPage.alerts: (_) => const AlertsPage(),
            AppPage.settings: (_) => const SettingsPage(),
          }),
        ),
      ),
    );
  }
}
