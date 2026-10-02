// The city list and "Use my location": GET /cities parsing (shapes from the
// real endpoint, Tamil names included), the bundled fallback, UiPrefs taking
// the server's list, nearestCity's distance, and the picker saying which
// city it picked and how far away it is.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/cities.dart';
import 'package:weathergpt/cities_client.dart';
import 'package:weathergpt/components/common.dart';
import 'package:weathergpt/location.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/pages/home_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

Map<String, dynamic> _entry(String key, double lat, double lon, String name, String region, {String? ta}) => {
  'key': key,
  'lat': lat,
  'lon': lon,
  'names': {'en': name, 'ta': ?ta},
  'region': {'en': region},
  'timezone': 'Asia/Kolkata',
};

/// What the deployed box answered on 2026-10-03 (a build older than main).
final _threeCities = [
  _entry('chennai', 13.0827, 80.2707, 'Chennai', 'Tamil Nadu', ta: 'சென்னை'),
  _entry('madurai', 9.9252, 78.1198, 'Madurai', 'Tamil Nadu', ta: 'மதுரை'),
  _entry('coimbatore', 11.0168, 76.9558, 'Coimbatore', 'Tamil Nadu', ta: 'கோயம்புத்தூர்'),
];

List<City> _parse(List<Map<String, dynamic>> entries) => [for (final e in entries) City.fromJson(e)!];

const _jaipur = (lat: 26.9124, lon: 75.7873);
const _adyar = (lat: 13.0012, lon: 80.2565); // a Chennai neighbourhood

final _noNetwork = MockClient((_) async => http.Response('{}', 500));

Future<AuthStore> _guest() async {
  final store = AuthStore(
    storage: MemorySessionStorage({'guest': true}),
    client: AuthClient(client: _noNetwork),
  );
  await store.restore();
  return store;
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

/// A screen with one button that opens the picker, with [locate] as the GPS.
Widget _pickerHarness(UiPrefs prefs, Locator locate) => UiPrefsScope(
  prefs: prefs,
  child: MaterialApp(
    theme: buildAppTheme(personaThemeFor(prefs.persona)),
    home: Scaffold(
      body: Builder(
        builder: (context) => Center(
          child: TextButton(
            onPressed: () => showCityPicker(context, locate: locate),
            child: const Text('pick'),
          ),
        ),
      ),
    ),
  ),
);

void main() {
  group('City.fromJson', () {
    test('reads a /cities entry: key, coordinates, English name and region', () {
      final c = City.fromJson(_threeCities.first)!;
      expect(c.key, 'chennai');
      expect(c.lat, 13.0827);
      expect(c.lon, 80.2707);
      expect(c.name, 'Chennai');
      expect(c.region, 'Tamil Nadu');
    });

    test('a missing region is empty; a missing key, coordinate or name is no city', () {
      expect(City.fromJson({..._threeCities.first, 'region': null})!.region, '');
      expect(City.fromJson({..._threeCities.first, 'key': ''}), isNull);
      expect(City.fromJson({..._threeCities.first, 'lat': '13.08'}), isNull);
      expect(
        City.fromJson({
          ..._threeCities.first,
          'names': {'ta': 'சென்னை'},
        }),
        isNull,
      );
      expect(City.fromJson('chennai'), isNull);
    });

    test('integer coordinates are fine', () {
      expect(City.fromJson({..._threeCities.first, 'lat': 13, 'lon': 80})!.lat, 13.0);
    });
  });

  group('fetchCities', () {
    Future<List<City>?> fetchWith(http.Response res) =>
        http.runWithClient(fetchCities, () => MockClient((_) async => res));

    test('the server list, decoded as UTF-8 whatever the content type says', () async {
      final cities = await fetchWith(http.Response.bytes(utf8.encode(jsonEncode({'cities': _threeCities})), 200));
      expect(cities!.map((c) => c.key), ['chennai', 'madurai', 'coimbatore']);
    });

    test('unusable entries are dropped', () async {
      final cities = await fetchWith(
        http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'cities': [
                _threeCities.first,
                {'key': 'nowhere'},
                42,
              ],
            }),
          ),
          200,
        ),
      );
      expect(cities!.map((c) => c.key), ['chennai']);
    });

    test('null (keep the bundled list) on an error, bad JSON, wrong shape or no cities', () async {
      expect(await fetchWith(http.Response('{}', 500)), isNull);
      expect(await fetchWith(http.Response('<html>', 200)), isNull);
      expect(await fetchWith(http.Response('{"cities": "chennai"}', 200)), isNull);
      expect(await fetchWith(http.Response('{"cities": []}', 200)), isNull);
    });
  });

  group('nearestCity', () {
    test('a Chennai neighbourhood is Chennai, a few km away', () {
      final (:city, :km) = nearestCity(_adyar.lat, _adyar.lon);
      expect(city.key, 'chennai');
      expect(km, inInclusiveRange(5, 15));
    });

    test('Jaipur is nearest to Delhi, far beyond the "near" distance', () {
      final (:city, :km) = nearestCity(_jaipur.lat, _jaipur.lon);
      expect(city.key, 'delhi');
      expect(km, inInclusiveRange(220, 260));
      expect(km, greaterThan(kNearCityKm));
    });

    test('only the given cities are considered', () {
      expect(nearestCity(_jaipur.lat, _jaipur.lon, _parse(_threeCities)).city.key, 'chennai'); // not Delhi
    });
  });

  group('UiPrefs.cities', () {
    test("the server's list replaces the bundled one; a city it doesn't serve moves to its first", () {
      final prefs = UiPrefs()..city = 'mumbai';
      var notified = 0;
      prefs.addListener(() => notified++);
      prefs.cities = _parse(_threeCities);
      expect(prefs.cities.map((c) => c.key), ['chennai', 'madurai', 'coimbatore']);
      expect(prefs.city, 'chennai');
      expect(notified, 1);
    });

    test('a served selection stays put, and the same list again changes nothing', () {
      final prefs = UiPrefs()..city = 'madurai';
      prefs.cities = _parse(_threeCities);
      var notified = 0;
      prefs.addListener(() => notified++);
      prefs.cities = _parse(_threeCities);
      expect(prefs.city, 'madurai');
      expect(notified, 0);
    });

    test('a saved city the bundled list lacked is selected once the server has it', () {
      final prefs = UiPrefs()..applySaved({'city': 'pune'});
      prefs.cities = [..._parse(_threeCities), City.fromJson(_entry('pune', 18.5204, 73.8567, 'Pune', 'Maharashtra'))!];
      expect(prefs.city, 'pune');
      expect(prefs.cityInfo.name, 'Pune');
    });

    test('an empty list is ignored', () {
      final prefs = UiPrefs()..cities = [];
      expect(prefs.cities, kCities);
    });
  });

  group('the app', () {
    testWidgets("offers only the server's cities, and leaves one it doesn't serve", (tester) async {
      _phone(tester);
      final store = MemoryPrefsStore({'city': 'mumbai'});
      await tester.pumpWidget(
        WeatherGptApp(auth: await _guest(), prefsStore: store, citiesFetcher: () async => _parse(_threeCities)),
      );
      await _settle(tester);

      expect(UiPrefs.read(tester.element(find.byType(HomePage))).city, 'chennai');
      expect(store.saved!['city'], 'chennai');
      await tester.tap(find.text('Chennai, Tamil Nadu'));
      await _settle(tester);
      expect(find.text('Choose a city'), findsOneWidget);
      expect(find.text('Coimbatore, Tamil Nadu'), findsOneWidget);
      expect(find.text('Mumbai, Maharashtra'), findsNothing);
      expect(find.text('Delhi, Delhi'), findsNothing);
    });

    testWidgets('keeps the bundled cities when the server list is unavailable', (tester) async {
      _phone(tester);
      await tester.pumpWidget(
        WeatherGptApp(auth: await _guest(), prefsStore: MemoryPrefsStore(), citiesFetcher: () async => null),
      );
      await _settle(tester);
      expect(UiPrefs.read(tester.element(find.byType(HomePage))).cities, kCities);
    });
  });

  group('Use my location', () {
    Future<UiPrefs> locateWith(WidgetTester tester, Locator locate) async {
      _phone(tester);
      final prefs = UiPrefs();
      await tester.pumpWidget(_pickerHarness(prefs, locate));
      await tester.tap(find.text('pick'));
      await _settle(tester);
      await tester.tap(find.text('Use my location'));
      await _settle(tester);
      return prefs;
    }

    testWidgets('near a covered city: picks it and says how far it is', (tester) async {
      final prefs = await locateWith(tester, () async => _adyar);
      expect(prefs.city, 'chennai');
      expect(find.text('Choose a city'), findsNothing); // the sheet closed
      expect(find.textContaining(RegExp(r'^Using Chennai, about \d+ km from you\.$')), findsOneWidget);
    });

    testWidgets('far from every covered city: picks the nearest and says answers are for it', (tester) async {
      final prefs = await locateWith(tester, () async => _jaipur);
      expect(prefs.city, 'delhi');
      expect(
        find.textContaining(
          RegExp(
            r'^Delhi is the nearest city WeatherGPT covers, about 2\d\d km from you\. '
            r'Answers are for Delhi, not your exact location\.$',
          ),
        ),
        findsOneWidget,
      );
    });

    testWidgets('location refused: the reason shows in the sheet and the city is unchanged', (tester) async {
      final prefs = await locateWith(
        tester,
        () async => throw LocationDenied('Location permission denied. Pick a city manually instead.'),
      );
      expect(prefs.city, 'chennai');
      expect(find.text('Choose a city'), findsOneWidget);
      expect(find.text('Location permission denied. Pick a city manually instead.'), findsOneWidget);
    });

    testWidgets('the note is in the app language, city name included', (tester) async {
      final prefs = UiPrefs()..lang = 'hi';
      await tester.pumpWidget(_pickerHarness(prefs, () async => _jaipur));
      final context = tester.element(find.text('pick'));
      final far = nearestCityNote(context, cityByKey('delhi'), 240);
      expect(far, startsWith('WeatherGPT'));
      expect(far, contains('दिल्ली'));
      expect(far, contains('240'));
      expect(nearestCityNote(context, cityByKey('delhi'), 0.3), contains('1')); // never "0 km"
    });
  });
}
