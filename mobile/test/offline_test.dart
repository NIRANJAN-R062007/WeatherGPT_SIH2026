// Offline (plan.md §2 principle 5): replies are saved (lib/response_cache.dart)
// and, when the backend can't be reached, the saved copies stand in —
// trimmed to what still holds, marked as saved, never a saved "no warnings"
// shown as an all-clear — until the backend answers again.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/facts_client.dart';
import 'package:weathergpt/hotlines_client.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/response_cache.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/state/weather_store.dart';
import 'package:weathergpt/warnings_client.dart';

const _ist = Duration(hours: 5, minutes: 30);
const _source = 'Google Weather API (live)';

String _date(DateTime d) => d.toIso8601String().substring(0, 10);

/// Today's IST calendar date, at UTC midnight.
DateTime _todayIst() {
  final ist = DateTime.now().toUtc().add(_ist);
  return DateTime.utc(ist.year, ist.month, ist.day);
}

/// Ten days from today (IST), so a copy saved now is fresh whenever this runs.
Map<String, dynamic> _daily() => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'status': 'ok',
  'days': [
    for (var i = 0; i < 10; i++)
      {
        'label': ['today', 'tomorrow'].elementAtOrNull(i) ?? 'later',
        'date': _date(_todayIst().add(Duration(days: i))),
        'condition': 'clear',
        'condition_label': 'clear',
        'high_c': 32,
        'low_c': 27,
        'rain_probability_pct': 15,
        'sunrise': '${_date(_todayIst().add(Duration(days: i)))}T00:28:00Z',
        'sunset': '${_date(_todayIst().add(Duration(days: i)))}T12:27:00Z',
      },
  ],
  'provenance': {'source': _source, 'is_live': true, 'issued': '${_date(_todayIst())}T01:30:00Z'},
};

/// The 24 hours from the current one.
Map<String, dynamic> _hourly() {
  final now = DateTime.now().toUtc();
  final start = DateTime.utc(now.year, now.month, now.day, now.hour);
  return {
    'city': 'chennai',
    'city_name': 'Chennai',
    'status': 'ok',
    'hours': [
      for (var i = 0; i < 24; i++)
        {
          'time_iso': start.add(Duration(hours: i)).toIso8601String(),
          'local_time': '${start.add(Duration(hours: i)).add(_ist).hour.toString().padLeft(2, '0')}:00',
          'date': _date(start.add(Duration(hours: i)).add(_ist)),
          'temp_c': 29,
          'rain_probability_pct': 10,
          'condition': 'clear',
          'condition_label': 'clear',
          'is_daytime': true,
        },
    ],
    'provenance': {'source': _source, 'is_live': true, 'issued': start.toIso8601String()},
  };
}

Map<String, dynamic> _facts(String intent, String day) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'condition_label': 'partly cloudy',
  'facts': {
    'condition': 'partly_cloudy',
    'temp_c': 31,
    'humidity_pct': 70,
    'rain_probability_pct': 25,
    'high_c': 32,
    'low_c': 27,
    'source': _source,
    'issued': DateTime.now().toUtc().toIso8601String(),
    'is_live': true,
  },
  if (intent == 'current_weather' && day == 'today')
    'rain_so_far': {'rain_so_far_mm': 0.56, 'rain_category': 'light', 'source': _source, 'is_live': true},
};

Map<String, dynamic> _warnings(String status) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'status': status,
  'warning': {
    'colour': status == 'active' ? 'orange' : 'green',
    'colour_label': status == 'active' ? 'Orange' : 'Green',
    'category_label': status == 'active' ? 'Heavy Rain' : '',
    'headline': status == 'active' ? 'Heavy rain likely in Chennai' : 'No warnings in force',
    'issued_by': 'IMD',
    'source': 'fixture',
  },
  'legend': [],
};

const _hotlines = {
  'city': 'chennai',
  'city_name': 'Chennai',
  'checked': '2026-10-03',
  'hotlines': [
    {'number': '112', 'dial': '112', 'name': 'Emergency', 'note': 'Any emergency, anywhere in India'},
    {
      'number': '1070',
      'dial': '1070',
      'name': 'State disaster helpline',
      'note': 'Floods, cyclones and other disasters',
    },
  ],
};

/// The backend while [online] says so; otherwise every request fails to
/// connect, as with no network.
class _Backend {
  bool online = true;
  String warningStatus = 'clear';

  late final client = MockClient((req) async {
    if (!online) throw http.ClientException('Network is unreachable', req.url);
    final q = req.url.queryParameters;
    final Object? body = switch (req.url.path) {
      '/facts' => _facts(q['intent'] ?? 'current_weather', q['day'] ?? 'today'),
      '/forecast/daily' => _daily(),
      '/forecast/hourly' => _hourly(),
      '/warnings' => _warnings(warningStatus),
      '/hotlines' => _hotlines,
      _ => null,
    };
    if (body == null) return http.Response('{"detail":"Not Found"}', 404);
    return http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json; charset=utf-8'});
  });
}

Future<AuthStore> _guest() async {
  final store = AuthStore(
    storage: MemorySessionStorage({'guest': true}),
    client: AuthClient(client: MockClient((_) async => http.Response('{}', 500))),
  );
  await store.restore();
  return store;
}

void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

Future<void> _settle(WidgetTester tester) async {
  // Home's hero gradient drifts forever, so pumpAndSettle would time out.
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

Future<void> _boot(WidgetTester tester, ResponseCache cache) async {
  await tester.pumpWidget(
    WeatherGptApp(
      auth: await _guest(),
      prefsStore: MemoryPrefsStore(),
      citiesFetcher: () async => null,
      responseCache: cache,
    ),
  );
  await _settle(tester);
}

Future<void> _tab(WidgetTester tester, String label) async {
  await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.text(label)));
  await _settle(tester);
}

Future<void> _reveal(WidgetTester tester, Finder finder) async {
  await tester.dragUntilVisible(finder, find.byType(ListView).first, const Offset(0, -200));
  await tester.pump();
}

/// Boots once online (saving every reply), closes the app, and boots it
/// again with the network gone.
Future<void> _onlineThenOffline(WidgetTester tester, _Backend backend, MemoryResponseCache cache) async {
  await _boot(tester, cache);
  await _tab(tester, 'Alerts'); // the Alerts replies are saved on their first load
  await tester.pumpWidget(const SizedBox());
  backend.online = false;
  await _boot(tester, cache);
}

void main() {
  group('fetchOrSaved', () {
    Future<Map<String, dynamic>> fails() async => throw const SocketException('offline');

    test('a fresh reply is saved; an outage gets the saved copy and its time', () async {
      final cache = MemoryResponseCache();
      final (fresh, freshAt) = await fetchOrSaved(cache, 'k', () async => {'a': 1}, useSaved: (_) => true);
      expect(fresh, {'a': 1});
      expect(freshAt, isNull);
      final (saved, savedAt) = await fetchOrSaved(cache, 'k', fails, useSaved: (_) => true);
      expect(saved, {'a': 1});
      expect(savedAt, cache.entries['k']!.savedAt);
    });

    test('an answer that is not an outage, no copy, or a week-old copy: the error', () async {
      final cache = MemoryResponseCache(now: () => DateTime.now().subtract(const Duration(days: 8)));
      await cache.write('old', {'a': 1});
      expect(() => fetchOrSaved(cache, 'old', fails, useSaved: (_) => true), throwsA(isA<SocketException>()));
      cache.now = DateTime.now;
      await cache.write('k', {'a': 1});
      expect(() => fetchOrSaved(cache, 'k', fails, useSaved: (_) => false), throwsA(isA<SocketException>()));
      expect(() => fetchOrSaved(cache, 'none', fails, useSaved: (_) => true), throwsA(isA<SocketException>()));
      expect(() => fetchOrSaved(null, 'k', fails, useSaved: (_) => true), throwsA(isA<SocketException>()));
    });

    test('the key ignores parameter order', () {
      expect(replyKey('/facts', {'city': 'x', 'day': 'today'}), replyKey('/facts', {'day': 'today', 'city': 'x'}));
    });
  });

  group('FileResponseCache', () {
    late Directory dir;
    setUp(() async => dir = await Directory.systemTemp.createTemp('weathergpt_cache'));
    tearDown(() => dir.delete(recursive: true));

    test('round-trips a reply, with no temp file left behind', () async {
      final cache = FileResponseCache(base: () async => dir);
      await cache.write('/facts?city=chennai', {
        'facts': {'temp_c': 31},
      });
      final saved = await FileResponseCache(base: () async => dir).read('/facts?city=chennai');
      expect(saved?.body, {
        'facts': {'temp_c': 31},
      });
      expect(DateTime.now().difference(saved!.savedAt).inMinutes, 0);
      final files = Directory('${dir.path}/response_cache').listSync().map((f) => f.path);
      expect(files, everyElement(endsWith('.json')));
    });

    test('a missing, damaged or unavailable store reads as nothing saved', () async {
      final cache = FileResponseCache(base: () async => dir);
      expect(await cache.read('nothing'), isNull);
      await cache.write('k', {'a': 1});
      for (final f in Directory('${dir.path}/response_cache').listSync()) {
        File(f.path).writeAsStringSync('{not json');
      }
      expect(await cache.read('k'), isNull);
      final broken = FileResponseCache(base: () async => throw const FileSystemException('no storage'));
      await broken.write('k', {'a': 1}); // swallowed
      expect(await broken.read('k'), isNull);
    });
  });

  test('only an outage lets a saved copy stand in', () {
    expect(isWeatherOutage(FactsError(FactsErrorKind.network, 'x')), isTrue);
    expect(isWeatherOutage(FactsError(FactsErrorKind.timeout, 'x')), isTrue);
    expect(isWeatherOutage(FactsError(FactsErrorKind.http, 'x', status: 502)), isTrue);
    expect(isWeatherOutage(FactsError(FactsErrorKind.http, 'x', status: 404)), isFalse);
    expect(isWeatherOutage(FactsError(FactsErrorKind.malformed, 'x')), isFalse);
  });

  test('the clients save, then serve the saved copy marked with its time', () async {
    final backend = _Backend();
    final cache = MemoryResponseCache();
    await http.runWithClient(() async {
      await fetchFacts(city: 'chennai', cache: cache);
      await fetchWarningsOrSaved(city: 'chennai', cache: cache);
      await fetchHotlines(city: 'chennai', cache: cache);
      backend.online = false;
      final facts = await fetchFacts(city: 'chennai', cache: cache);
      expect((facts.number('temp_c'), facts.savedAt != null), (31, true));
      final (warnings, warningsSavedAt) = await fetchWarningsOrSaved(city: 'chennai', cache: cache);
      expect((warnings['status'], warningsSavedAt != null), ('clear', true));
      final hotlines = await fetchHotlines(city: 'chennai', cache: cache);
      expect(hotlines.lines.map((l) => l.dial), ['112', '1070']);
      expect(hotlines.savedAt, isNotNull);
      // Nothing saved for another city: the outage itself.
      await expectLater(
        fetchFacts(city: 'madurai', cache: cache),
        throwsA(isA<FactsError>().having((e) => e.kind, 'kind', FactsErrorKind.network)),
      );
    }, () => backend.client);
  });

  group('a saved copy keeps only what still holds', () {
    final now = DateTime.utc(2026, 10, 5, 6); // 11:30 IST, 5 Oct
    final yesterday = DateTime.utc(2026, 10, 4, 6);

    test('facts: current conditions stay, without an earlier day\'s rain; old periods go', () {
      final current = FactsResult.fromJson(_facts('current_weather', 'today'), savedAt: yesterday);
      final kept = freshFacts(current, now, current: true)!;
      expect((kept.number('temp_c'), kept.rainSoFar), (31, null));
      expect(
        freshFacts(FactsResult.fromJson(_facts('will_it_rain', 'today'), savedAt: yesterday), now, current: false),
        isNull,
      );
      final sameDay = FactsResult.fromJson(
        _facts('current_weather', 'today'),
        savedAt: now.subtract(const Duration(hours: 2)),
      );
      expect(freshFacts(sameDay, now, current: true)!.rainSoFar, isNotNull);
    });

    test('days: past days dropped, today and tomorrow labelled by date', () {
      final days = DailyForecast([
        for (var i = 3; i <= 9; i++) ForecastDay({'label': 'x', 'date': '2026-10-0$i'}),
      ], savedAt: yesterday);
      final kept = freshDaily(days, now)!;
      expect(kept.entries.map((d) => (d.text('date'), d.label)).take(3), [
        ('2026-10-05', 'today'),
        ('2026-10-06', 'tomorrow'),
        ('2026-10-07', 'later'),
      ]);
      expect(
        freshDaily(
          DailyForecast([
            ForecastDay({'date': '2026-10-01'}),
          ], savedAt: yesterday),
          now,
        ),
        isNull,
      );
      expect(
        freshDaily(
          DailyForecast([
            ForecastDay({'date': '2026-10-01'}),
          ]),
          now,
        )!.entries,
        hasLength(1),
      ); // fresh: as served
    });

    test('hours: the ones that have ended are dropped', () {
      final hours = HourlyForecast([
        for (var h = 3; h <= 8; h++) ForecastHour({'time_iso': '2026-10-05T0$h:00:00Z'}),
      ], savedAt: yesterday);
      expect(freshHourly(hours, now)!.entries.map((h) => h.text('time_iso')).first, '2026-10-05T06:00:00Z');
      expect(
        freshHourly(
          HourlyForecast([
            ForecastHour({'time_iso': '2026-10-05T01:00:00Z'}),
          ], savedAt: yesterday),
          now,
        ),
        isNull,
      );
    });
  });

  testWidgets('offline, Home and Forecast show the saved figures, marked as saved', (tester) async {
    _phone(tester);
    final backend = _Backend();
    final cache = MemoryResponseCache();
    await http.runWithClient(() async {
      await _boot(tester, cache);
      expect(find.text('Showing saved data'), findsNothing);
      expect(find.text('LIVE'), findsOneWidget);

      await tester.pumpWidget(const SizedBox());
      backend.online = false;
      await _boot(tester, cache);
      expect(find.text('Showing saved data'), findsOneWidget);
      expect(find.textContaining('These figures were saved at'), findsOneWidget);
      expect(find.text('LIVE'), findsNothing);
      expect(find.text('SAVED'), findsWidgets);
      expect(find.text('Live conditions unavailable'), findsNothing);
      expect(find.textContaining('31°'), findsWidgets);

      await _tab(tester, 'Forecast');
      expect(find.text('Showing saved data'), findsOneWidget);
      expect(find.text('Today'), findsOneWidget);
      await tester.tap(find.text('Hourly'));
      await _settle(tester);
      expect(find.text('Now'), findsOneWidget);
      await _reveal(tester, find.textContaining('Saved on this phone at'));
      expect(tester.takeException(), isNull);
    }, () => backend.client);
  });

  testWidgets('when the backend answers again, the saved banner goes', (tester) async {
    _phone(tester);
    final backend = _Backend();
    final cache = MemoryResponseCache();
    await http.runWithClient(() async {
      await _boot(tester, cache);
      await tester.pumpWidget(const SizedBox());
      backend.online = false;
      await _boot(tester, cache);
      expect(find.text('Showing saved data'), findsOneWidget);

      backend.online = true;
      await tester.pump(kOfflineRetry + const Duration(seconds: 1));
      await _settle(tester);
      expect(find.text('Showing saved data'), findsNothing);
      expect(find.text('LIVE'), findsOneWidget);
    }, () => backend.client);
  });

  testWidgets('offline with nothing saved: the error, as before', (tester) async {
    _phone(tester);
    final backend = _Backend()..online = false;
    await http.runWithClient(() async {
      await _boot(tester, MemoryResponseCache());
      expect(find.text('Live conditions unavailable'), findsOneWidget);
      expect(find.text('Showing saved data'), findsNothing);
    }, () => backend.client);
  });

  testWidgets('offline Alerts: a saved "nothing in force" is no verdict, not an all-clear', (tester) async {
    _phone(tester);
    final backend = _Backend();
    final cache = MemoryResponseCache();
    await http.runWithClient(() async {
      await _onlineThenOffline(tester, backend, cache);
      await _tab(tester, 'Alerts');
      expect(find.textContaining("Couldn't reach the warnings service. This was saved at"), findsOneWidget);
      expect(find.text('No warning verdict'), findsOneWidget);
      expect(find.text('No warnings in force'), findsNothing);
      expect(find.textContaining('No active alerts'), findsNothing);
      await _reveal(tester, find.text('1070')); // the saved emergency numbers
      expect(find.text("Couldn't load the local numbers. 112 works anywhere in India."), findsNothing);
    }, () => backend.client);
  });

  testWidgets('offline Alerts: a saved active warning still shows, marked as saved', (tester) async {
    _phone(tester);
    final backend = _Backend()..warningStatus = 'active';
    final cache = MemoryResponseCache();
    await http.runWithClient(() async {
      await _onlineThenOffline(tester, backend, cache);
      await _tab(tester, 'Alerts');
      expect(find.textContaining("Couldn't reach the warnings service. This was saved at"), findsOneWidget);
      expect(find.text('Heavy Rain Alert'), findsOneWidget);
    }, () => backend.client);
  });
}
