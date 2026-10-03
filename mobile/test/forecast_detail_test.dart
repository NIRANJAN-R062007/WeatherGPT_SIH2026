// The forecast detail the backend's newer routes serve — /forecast/daily
// (day list, sun times), /forecast/hourly (hourly strip), /facts'
// rain_so_far and /hotlines — driven through the whole app against a fake
// backend, plus what an older backend (404 on those routes) falls back to.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/facts_client.dart';
import 'package:weathergpt/format.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/ui_strings.dart';

const _source = 'Google Weather API (live)';
const _weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];

/// Ten days from Saturday 3 Oct 2026, sunrise 05:58 and sunset 17:57 IST.
Map<String, dynamic> _daily() {
  final start = DateTime.utc(2026, 10, 3);
  return {
    'city': 'chennai',
    'city_name': 'Chennai',
    'status': 'ok',
    'days': [
      for (var i = 0; i < 10; i++)
        {
          'label': i == 0 ? 'today' : (i == 1 ? 'tomorrow' : _weekdays[start.add(Duration(days: i)).weekday - 1]),
          'date': start.add(Duration(days: i)).toIso8601String().substring(0, 10),
          'condition': i == 2 ? 'thunderstorm' : 'clear',
          'condition_label': i == 2 ? 'thunderstorm' : 'clear',
          'night_condition': 'partly_cloudy',
          'night_condition_label': 'partly cloudy',
          'high_c': 32 + i % 2,
          'low_c': 27,
          'rain_probability_pct': i == 2 ? 70 : 15,
          'night_rain_probability_pct': 20,
          'rain_mm': i == 2 ? 12.4 : 0.07,
          'wind_kmh': 14,
          'humidity_pct': 68,
          'uv_index': 9,
          'sunrise': '${start.add(Duration(days: i)).toIso8601String().substring(0, 10)}T00:28:00.648Z',
          'sunset': '${start.add(Duration(days: i)).toIso8601String().substring(0, 10)}T12:27:00.715Z',
        },
    ],
    'provenance': {'source': _source, 'is_live': true, 'issued': '2026-10-03T01:30:00Z'},
  };
}

/// 24 hours from 08:00 IST on 3 Oct, so the strip crosses midnight.
Map<String, dynamic> _hourly() {
  final start = DateTime.utc(2026, 10, 3, 2, 30);
  return {
    'city': 'chennai',
    'city_name': 'Chennai',
    'status': 'ok',
    'hours': [
      for (var i = 0; i < 24; i++)
        () {
          final ist = start.add(Duration(hours: i, minutes: 330));
          return {
            'time_iso': start.add(Duration(hours: i)).toIso8601String(),
            'local_time': '${ist.hour.toString().padLeft(2, '0')}:00',
            'date': ist.toIso8601String().substring(0, 10),
            'temp_c': 26 + (i < 8 ? i : 16 - i).clamp(0, 6),
            'rain_probability_pct': i == 3 ? 40 : 10,
            'condition': ist.hour >= 18 || ist.hour < 6 ? 'clear' : 'partly_cloudy',
            'condition_label': 'clear',
            'is_daytime': ist.hour >= 6 && ist.hour < 18,
          };
        }(),
    ],
    'provenance': {'source': _source, 'is_live': true, 'issued': '2026-10-03T02:30:00Z'},
  };
}

Map<String, dynamic> _facts(String intent, String day, {bool wind = true}) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'condition_label': 'partly cloudy',
  'facts': {
    'condition': 'partly_cloudy',
    'temp_c': 31,
    'feels_like_c': 36,
    'humidity_pct': 70,
    if (wind) 'wind_kmh': 12,
    'rain_probability_pct': 25,
    'high_c': 32,
    'low_c': 27,
    'source': _source,
    'issued': '2026-10-03T03:00:00Z',
    'is_live': true,
  },
  if (intent == 'current_weather' && day == 'today')
    'rain_so_far': {
      'rain_so_far_mm': 0.56,
      'rain_category': 'light',
      'since': '2026-10-03T00:00:00+05:30',
      'source': _source,
      'is_live': true,
    },
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
    {
      'number': '1077',
      'dial': '1077',
      'name': 'District disaster helpline',
      'note': "Your district's disaster control room",
    },
  ],
};

/// The backend: everything on main's routes, or (when [old]) the deployed
/// build from before /forecast/* and /hotlines, which 404s on them. [wind]
/// false leaves wind out of the hero (see the 360 dp test).
MockClient _backend({bool old = false, bool wind = true}) => MockClient((req) async {
  final q = req.url.queryParameters;
  final Object? body = switch (req.url.path) {
    '/facts' => _facts(q['intent'] ?? 'current_weather', q['day'] ?? 'today', wind: wind),
    '/forecast/daily' when !old => _daily(),
    '/forecast/hourly' when !old => _hourly(),
    '/hotlines' when !old => _hotlines,
    '/warnings' => {'city': 'chennai', 'city_name': 'Chennai', 'status': 'unavailable', 'warning': null},
    _ => null,
  };
  if (body == null) return http.Response('{"detail":"Not Found"}', 404);
  return http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json; charset=utf-8'});
});

Future<AuthStore> _guest() async {
  final store = AuthStore(
    storage: MemorySessionStorage({'guest': true}),
    client: AuthClient(client: MockClient((_) async => http.Response('{}', 500))),
  );
  await store.restore();
  return store;
}

void _phone(WidgetTester tester, {double width = 1080}) {
  tester.view.physicalSize = Size(width, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

Future<void> _settle(WidgetTester tester) async {
  // Home's hero gradient drifts forever, so pumpAndSettle would time out.
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

/// The app, signed in as a guest, against [backend]; [lang] preselected.
Future<void> _boot(WidgetTester tester, MockClient backend, {String lang = 'en'}) async {
  await tester.pumpWidget(
    WeatherGptApp(auth: await _guest(), prefsStore: MemoryPrefsStore({'lang': lang}), citiesFetcher: () async => null),
  );
  await _settle(tester);
}

Future<void> _tab(WidgetTester tester, String label) async {
  await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.text(label)));
  await _settle(tester);
}

/// Scrolls the page until [finder] is built and on screen.
Future<void> _reveal(WidgetTester tester, Finder finder) async {
  await tester.dragUntilVisible(finder, find.byType(ListView).first, const Offset(0, -200));
  await tester.pump();
}

void main() {
  group('clients', () {
    test('the daily and hourly series parse, provenance included', () async {
      final (daily, hourly) = await http.runWithClient(
        () async => (await fetchDailyForecast(city: 'chennai'), await fetchHourlyForecast(city: 'chennai')),
        _backend,
      );
      expect(daily.entries, hasLength(10));
      expect(daily.entries.first.label, 'today');
      expect(daily.entries[2].date, DateTime(2026, 10, 5));
      expect(daily.entries.first.number('rain_mm'), 0.07);
      expect((daily.source, daily.isLive), (_source, true));
      expect(hourly.entries, hasLength(24));
      expect(hourly.entries.first.localTime, '08:00');
      expect((hourly.entries[16].localTime, hourly.entries[16].isNight), ('00:00', true));
    });

    test("an older backend's 404 is a FactsError with the status", () async {
      await http.runWithClient(() async {
        await expectLater(
          fetchDailyForecast(city: 'chennai'),
          throwsA(isA<FactsError>().having((e) => e.status, 'status', 404)),
        );
      }, () => _backend(old: true));
    });

    test("current conditions carry rain_so_far; a forecast period doesn't", () async {
      final (now, later) = await http.runWithClient(
        () async => (await fetchFacts(city: 'chennai'), await fetchFacts(city: 'chennai', day: 'tomorrow')),
        _backend,
      );
      expect(now.rainSoFar?.number('rain_so_far_mm'), 0.56);
      expect(later.rainSoFar, isNull);
    });
  });

  test('format helpers', () {
    expect(istClock('2026-10-03T00:28:00.648Z'), '05:58');
    expect(istMinuteOfDay('2026-10-03T12:27:00Z'), 17 * 60 + 57);
    expect(forecastDayName('monday', DateTime(2026, 10, 5), 'en'), 'Mon');
    expect(forecastDayName('tomorrow', DateTime(2026, 10, 4), 'ta'), kUiStrings['ta']!['Tomorrow']);
    expect(forecastDayName('later', DateTime(2026, 10, 8), 'hi'), kUiStrings['hi']!['Thu']);
    expect(hoursMinutes(const Duration(hours: 11, minutes: 59), 'en'), '11 h 59 min');
    expect(millimetres(0.56), '0.6 mm');
    expect(millimetres(64.5), '65 mm');
    expect(rainCategoryLabel('very_heavy'), 'Very heavy rain');
    expect(rainCategoryLabel('drizzle'), isNull);
  });

  testWidgets('Home: rain so far, daylight and a five-day strip', (tester) async {
    _phone(tester);
    await http.runWithClient(() async {
      await _boot(tester, _backend());
      await _reveal(tester, find.text('Rain so far'));
      expect(find.text('0.6 mm'), findsOneWidget);
      expect(find.text('Light rain'), findsOneWidget);
      expect(find.text('Since midnight'), findsOneWidget);
      expect(find.text('Daylight'), findsOneWidget);
      expect(find.text('11 h 59 min'), findsOneWidget);
      expect(find.text('05:58'), findsOneWidget);
      expect(find.text('17:57'), findsOneWidget);

      await _reveal(tester, find.text('Mon'));
      for (final day in ['Today', 'Tomorrow', 'Mon', 'Tue', 'Wed']) {
        expect(find.text(day), findsWidgets, reason: day);
      }
      expect(find.text('Thu'), findsNothing); // five days, not ten
      expect(tester.takeException(), isNull);
    }, _backend);
  });

  testWidgets('Forecast: ten days, a day opens to its figures; Hourly starts Now', (tester) async {
    _phone(tester);
    await http.runWithClient(() async {
      await _boot(tester, _backend());
      await _tab(tester, 'Forecast');

      expect(find.text('Need more days?'), findsNothing);
      expect(find.text('5 Oct'), findsOneWidget);
      await _reveal(tester, find.text('12 Oct'));
      await _reveal(tester, find.text('5 Oct'));
      await tester.tap(find.text('5 Oct'));
      await tester.pump();
      for (final label in ['Rainfall', 'UV index', 'Sunrise', 'Sunset', 'Rain at night']) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
      expect(find.text('12 mm'), findsOneWidget);
      expect(find.text('70%'), findsWidgets);
      expect(find.text('Night: partly cloudy'), findsOneWidget);

      await _reveal(tester, find.text('Hourly'));
      await tester.tap(find.text('Hourly'));
      await _settle(tester);
      expect(find.text('Now'), findsOneWidget);
      expect(find.text('08:00'), findsOneWidget);
      expect(find.textContaining('As served by $_source'), findsOneWidget);
      expect(tester.takeException(), isNull);
    }, _backend);
  });

  testWidgets('an older backend: the /facts rows, the Chat banner, and no hourly strip', (tester) async {
    _phone(tester);
    await http.runWithClient(() async {
      await _boot(tester, _backend(old: true));
      await _reveal(tester, find.text('Tonight'));
      expect(find.text('Rain so far'), findsOneWidget); // /facts still carries it
      expect(find.text('Daylight'), findsNothing); // no /forecast/daily, no sun times

      await _tab(tester, 'Forecast');
      expect(find.text('Tonight'), findsOneWidget);
      expect(find.text('Need more days?'), findsOneWidget);
      await tester.tap(find.text('Hourly'));
      await _settle(tester);
      expect(find.text("This weather service doesn't serve an hourly forecast yet."), findsOneWidget);
    }, () => _backend(old: true));
  });

  testWidgets('Alerts: the city\'s emergency numbers, 112 first, with the check date', (tester) async {
    _phone(tester);
    await http.runWithClient(() async {
      await _boot(tester, _backend());
      await _tab(tester, 'Alerts');
      await _reveal(tester, find.text('Checked against official government pages on 3 Oct 2026.'));
      expect(find.text('Emergency numbers'), findsOneWidget);
      final numbers = find.descendant(
        of: find.byType(ListView).first,
        matching: find.textContaining(RegExp(r'^1\d\d\d?$')),
      );
      expect(tester.widgetList<Text>(numbers).map((t) => t.data), ['112', '1070', '1077']);
      expect(find.bySemanticsLabel('Call State disaster helpline, 1070'), findsOneWidget);
    }, _backend);
  });

  testWidgets('Alerts without /hotlines: 112 alone, and why', (tester) async {
    _phone(tester);
    await http.runWithClient(() async {
      await _boot(tester, _backend(old: true));
      await _tab(tester, 'Alerts');
      await _reveal(tester, find.text("Couldn't load the local numbers. 112 works anywhere in India."));
      expect(find.text('112'), findsOneWidget);
      expect(find.text('1070'), findsNothing);
    }, () => _backend(old: true));
  });

  // The test font draws every glyph a full em wide, about twice a real
  // font's width, so this is stricter than a real 360 dp phone. The hero's
  // existing wind stat ("12 km/h") overflows under it, though not on a
  // device, so its wind is left out here.
  testWidgets('nothing new overflows a 360 dp screen in any language', (tester) async {
    _phone(tester, width: 945); // 360 dp
    for (final lang in ['en', 'hi', 'ta', 'te', 'mr']) {
      await http.runWithClient(() async {
        await _boot(tester, _backend(wind: false), lang: lang);
        await _reveal(tester, find.byIcon(Icons.wb_twilight));
        expect(tester.takeException(), isNull, reason: '$lang Home');

        await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.byIcon(Icons.light_mode_outlined)));
        await _settle(tester);
        await tester.tap(find.byIcon(Icons.expand_more).first);
        await tester.pump();
        expect(tester.takeException(), isNull, reason: '$lang Forecast day');

        await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.byIcon(Icons.notifications_none)));
        await _settle(tester);
        await _reveal(tester, find.byIcon(Icons.call).last);
        expect(tester.takeException(), isNull, reason: '$lang Alerts');
      }, () => _backend(wind: false));
      await tester.pumpWidget(const SizedBox());
    }
  });

  test('every hotline name and note in data/hotlines.json is translated', () {
    final data = jsonDecode(File('../data/hotlines.json').readAsStringSync()) as Map<String, dynamic>;
    final entries = [
      ...data['national'] as List,
      for (final list in (data['regions'] as Map).values) ...list as List,
      for (final list in (data['cities'] as Map).values) ...list as List,
    ];
    for (final e in entries.cast<Map<String, dynamic>>()) {
      for (final key in [e['name'] as String, e['note'] as String]) {
        for (final lang in ['hi', 'ta', 'te', 'mr']) {
          expect(kUiStrings[lang]?[key], isNotNull, reason: '$lang: $key');
        }
      }
    }
  });
}
