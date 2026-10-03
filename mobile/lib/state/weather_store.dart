// Live /facts for the selected city, shared by the Home hero and the
// Forecast page so switching between them doesn't refetch. Reloads whenever
// the city or language changes (condition labels come back localized).
// The day list and hourly series (/forecast/daily, /forecast/hourly) load
// beside it, each with its own error: a backend without those routes (404)
// still serves Home and the /facts rows.
import 'package:flutter/widgets.dart';

import '../facts_client.dart';

class WeatherStore extends ChangeNotifier {
  String? _city;
  String? _lang;
  bool loading = false;
  FactsError? error;

  /// current_weather/today — the hero card.
  FactsResult? current;

  /// Forecast entries: will_it_rain/today, current_weather/tonight, /tomorrow.
  FactsResult? today;
  FactsResult? tonight;
  FactsResult? tomorrow;

  /// GET /forecast/daily and /forecast/hourly, null until they answer.
  DailyForecast? daily;
  HourlyForecast? hourly;
  FactsError? dailyError;
  FactsError? hourlyError;

  // Bumped on every load(); a reply whose id no longer matches is stale
  // (e.g. a fast city switch), same as web/src/lib/useAsk.ts.
  int _requestId = 0;
  bool _disposed = false;

  bool get hasData => current != null;

  /// The day list has days to show (else the /facts rows stand in).
  bool get hasDaily => daily?.isEmpty == false;
  bool get hasHourly => hourly?.isEmpty == false;

  /// Still waiting on /forecast/daily.
  bool get dailyPending => daily == null && dailyError == null;
  bool get hourlyPending => hourly == null && hourlyError == null;

  void ensureLoaded(String city, String lang) {
    if (city == _city && lang == _lang) return;
    load(city, lang);
  }

  Future<void> refresh() async {
    final city = _city;
    final lang = _lang;
    if (city != null && lang != null) await load(city, lang);
  }

  Future<void> load(String city, String lang) async {
    final id = ++_requestId;
    final cityChanged = city != _city;
    _city = city;
    _lang = lang;
    loading = true;
    error = dailyError = hourlyError = null;
    // Never show the previous city's numbers under the new city's name.
    if (cityChanged) {
      current = today = tonight = tomorrow = null;
      daily = hourly = null;
    }
    notifyListeners();

    await Future.wait([
      _loadFacts(id, city, lang),
      _loadSeries(id, () => fetchDailyForecast(city: city, lang: lang), (d, e) {
        daily = d;
        dailyError = e;
      }),
      _loadSeries(id, () => fetchHourlyForecast(city: city, lang: lang), (h, e) {
        hourly = h;
        hourlyError = e;
      }),
    ]);
  }

  Future<void> _loadFacts(int id, String city, String lang) async {
    try {
      final results = await Future.wait([
        fetchFacts(city: city, lang: lang),
        fetchFacts(city: city, lang: lang, intent: 'will_it_rain', day: 'today'),
        fetchFacts(city: city, lang: lang, day: 'tonight'),
        fetchFacts(city: city, lang: lang, day: 'tomorrow'),
      ]);
      if (_disposed || id != _requestId) return;
      current = results[0];
      today = results[1];
      tonight = results[2];
      tomorrow = results[3];
    } catch (e) {
      if (_disposed || id != _requestId) return;
      error = _asFactsError(e);
      current = today = tonight = tomorrow = null;
    }
    loading = false;
    notifyListeners();
  }

  /// One forecast series: [store] gets the result, or null and the error.
  Future<void> _loadSeries<T>(int id, Future<T> Function() fetch, void Function(T?, FactsError?) store) async {
    try {
      final result = await fetch();
      if (_disposed || id != _requestId) return;
      store(result, null);
    } catch (e) {
      if (_disposed || id != _requestId) return;
      store(null, _asFactsError(e));
    }
    notifyListeners();
  }

  static FactsError _asFactsError(Object e) => e is FactsError
      ? e
      : FactsError(FactsErrorKind.network, 'Something went wrong talking to the weather service.');

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  static WeatherStore of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<WeatherScope>()!.notifier!;
}

class WeatherScope extends InheritedNotifier<WeatherStore> {
  const WeatherScope({super.key, required WeatherStore store, required super.child})
      : super(notifier: store);
}
