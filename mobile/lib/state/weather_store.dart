// Live /facts for the selected city, shared by the Home hero and the
// Forecast page so switching between them doesn't refetch. Reloads whenever
// the city or language changes (condition labels come back localized).
// The day list and hourly series (/forecast/daily, /forecast/hourly) load
// beside it, each with its own error: a backend without those routes (404)
// still serves Home and the /facts rows.
//
// Offline (plan.md §2 principle 5): with a [ResponseCache], a backend that
// can't be reached gives the last saved replies instead, trimmed to what
// still holds now ([freshFacts], [freshDaily], [freshHourly]) and marked by
// [savedAt]. While saved data is showing, the store retries every
// [kOfflineRetry] until the backend answers again.
import 'dart:async';

import 'package:flutter/widgets.dart';

import '../config.dart';
import '../facts_client.dart';
import '../response_cache.dart';

/// How often to try the backend again while showing saved data.
const Duration kOfflineRetry = Duration(minutes: 1);

const Duration _ist = Duration(hours: 5, minutes: 30);

/// The IST calendar date of [t].
DateTime _istDate(DateTime t) {
  final ist = t.toUtc().add(_ist);
  return DateTime(ist.year, ist.month, ist.day);
}

/// A saved /facts reply as far as it still holds at [now]. Current
/// conditions stand however old (the page says when they were saved), but
/// their rain since midnight belongs to the day it was saved; a forecast
/// period (today / tonight / tomorrow) saved on an earlier day is gone.
FactsResult? freshFacts(FactsResult r, DateTime now, {required bool current}) {
  final saved = r.savedAt;
  if (saved == null || _istDate(saved) == _istDate(now)) return r;
  return current ? r.withoutRain() : null;
}

/// A saved day list from today on (past days dropped), with today and
/// tomorrow labelled by date rather than by the order they were saved in.
/// Null when no day is left.
DailyForecast? freshDaily(DailyForecast d, DateTime now) {
  if (d.savedAt == null) return d;
  final today = _istDate(now);
  final kept = [
    for (final day in d.entries)
      if (day.date != null && !day.date!.isBefore(today))
        ForecastDay({
          ...day.raw,
          'label': switch (day.date!.difference(today).inDays) {
            0 => 'today',
            1 => 'tomorrow',
            _ => 'later', // shown as its weekday
          },
        }),
  ];
  if (kept.isEmpty) return null;
  return DailyForecast(kept, source: d.source, isLive: d.isLive, issued: d.issued, savedAt: d.savedAt);
}

/// A saved hourly series without the hours that have ended. Null when none
/// is left.
HourlyForecast? freshHourly(HourlyForecast h, DateTime now) {
  if (h.savedAt == null) return h;
  final kept = h.where((hour) {
    final start = DateTime.tryParse(hour.text('time_iso') ?? '');
    return start != null && start.add(const Duration(hours: 1)).isAfter(now);
  });
  return kept.isEmpty ? null : kept;
}

class WeatherStore extends ChangeNotifier {
  /// Where replies are saved for offline use; null saves nothing.
  final ResponseCache? cache;
  WeatherStore({this.cache});

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
  Timer? _retry;

  bool get hasData => current != null;

  /// The day list has days to show (else the /facts rows stand in).
  bool get hasDaily => daily?.isEmpty == false;
  bool get hasHourly => hourly?.isEmpty == false;

  /// Still waiting on /forecast/daily.
  bool get dailyPending => daily == null && dailyError == null;
  bool get hourlyPending => hourly == null && hourlyError == null;

  /// When the oldest saved reply on show was saved; null when everything
  /// shown is fresh.
  DateTime? get savedAt {
    final times = [
      for (final t in [
        current?.savedAt,
        today?.savedAt,
        tonight?.savedAt,
        tomorrow?.savedAt,
        daily?.savedAt,
        hourly?.savedAt,
      ])
        ?t,
    ];
    return times.isEmpty ? null : times.reduce((a, b) => a.isBefore(b) ? a : b);
  }

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
      _loadSeries(id, () => fetchDailyForecast(city: city, lang: lang, cache: cache), freshDaily, (d, e) {
        daily = d;
        dailyError = e;
      }),
      _loadSeries(id, () => fetchHourlyForecast(city: city, lang: lang, cache: cache), freshHourly, (h, e) {
        hourly = h;
        hourlyError = e;
      }),
    ]);
    if (_disposed || id != _requestId) return;
    _scheduleRetry();
  }

  /// The four /facts replies, each on its own: only the hero's failing is an
  /// error for the page; a forecast period that fails is just left empty.
  Future<void> _loadFacts(int id, String city, String lang) async {
    FactsError? failure;
    Future<FactsResult?> fetch({String intent = 'current_weather', String day = 'today'}) async {
      final isCurrent = intent == 'current_weather' && day == 'today';
      try {
        final r = await fetchFacts(city: city, lang: lang, intent: intent, day: day, cache: cache);
        return freshFacts(r, DateTime.now(), current: isCurrent);
      } catch (e) {
        if (isCurrent) failure = _asFactsError(e);
        return null;
      }
    }

    final results = await Future.wait([
      fetch(),
      fetch(intent: 'will_it_rain'),
      fetch(day: 'tonight'),
      fetch(day: 'tomorrow'),
    ]);
    if (_disposed || id != _requestId) return;
    error = failure;
    if (failure != null) {
      current = today = tonight = tomorrow = null;
    } else {
      current = results[0];
      today = results[1];
      tonight = results[2];
      tomorrow = results[3];
    }
    loading = false;
    notifyListeners();
  }

  /// One forecast series: [store] gets the result, or null and the error. A
  /// saved copy with nothing left that still holds counts as unreachable.
  Future<void> _loadSeries<T>(
    int id,
    Future<T> Function() fetch,
    T? Function(T result, DateTime now) fresh,
    void Function(T?, FactsError?) store,
  ) async {
    try {
      final result = fresh(await fetch(), DateTime.now());
      if (_disposed || id != _requestId) return;
      store(result, result == null ? _unreachable() : null);
    } catch (e) {
      if (_disposed || id != _requestId) return;
      store(null, _asFactsError(e));
    }
    notifyListeners();
  }

  /// Keep trying while saved data is showing; stop once it's all fresh.
  void _scheduleRetry() {
    if (savedAt == null) {
      _retry?.cancel();
      _retry = null;
    } else {
      _retry ??= Timer.periodic(kOfflineRetry, (_) {
        if (!loading) refresh();
      });
    }
  }

  static FactsError _asFactsError(Object e) => e is FactsError
      ? e
      : FactsError(FactsErrorKind.network, 'Something went wrong talking to the weather service.');

  static FactsError _unreachable() => FactsError(
    FactsErrorKind.network,
    "Couldn't reach the weather service at {url}. Is the orchestrator running?",
    args: {'url': kApiBaseUrl},
  );

  @override
  void dispose() {
    _disposed = true;
    _retry?.cancel();
    super.dispose();
  }

  static WeatherStore of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<WeatherScope>()!.notifier!;
}

class WeatherScope extends InheritedNotifier<WeatherStore> {
  const WeatherScope({super.key, required WeatherStore store, required super.child})
      : super(notifier: store);
}
