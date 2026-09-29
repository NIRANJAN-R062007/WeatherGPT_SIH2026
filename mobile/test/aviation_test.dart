// Airport weather: the /aviation client's parsing and the page's states —
// live, offline snapshot, one report missing, none at all, error, and a city
// change. Report text is from real METAR/TAF for Chennai (VOMM), decoded by
// services/orchestrator (metar.py / taf.py); shapes match GET /aviation.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/aviation_client.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/pages/aviation_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

const _disclaimer =
    'For awareness only, not for flight planning. Use the official AAI / IMD aviation briefing before flying.';

Map<String, dynamic> _metar({bool live = true}) => {
  'raw': 'METAR VOMM 292130Z 22005KT 4000 BR SCT020 SCT100 30/28 Q1010 NOSIG',
  'decoded': {
    'observed': {'day': 29, 'time_utc': '21:30', 'time_ist': '03:00'},
  },
  'briefing': 'unused here',
  'lines': [
    'Chennai airport (VOMM), routine report observed at 03:00 IST (21:30 UTC on day 29 of the month).',
    'Wind from the southwest (220°) at 9 km/h (5 kt).',
    'Visibility 4 km.',
    'Weather: mist.',
  ],
  'is_live': live,
  'retrieved_at': live ? '2026-09-29T22:02:45+00:00' : '2026-09-29T21:47:58+00:00',
  'source': 'aviationweather.gov',
};

Map<String, dynamic> _taf({bool live = true}) => {
  'raw': 'TAF VOMM 291700Z 2918/3024 25010KT 4000 -DZ/BR SCT018 TEMPO 2921/3003 SCT018',
  'decoded': {
    'issued': {'day': 29, 'time_utc': '17:00', 'time_ist': '22:30'},
  },
  'briefing': 'unused here',
  'lines': [
    'Chennai airport (VOMM), terminal forecast (TAF) issued at 22:30 IST (17:00 UTC on day 29 of the month).',
    'Weather: light drizzle, mist.',
    'Temporarily between 02:30 IST (21:00 UTC, day 29) and 08:30 IST (03:00 UTC, day 30): Cloud: scattered at 1,800 ft.',
  ],
  'is_live': live,
  'retrieved_at': live ? '2026-09-29T22:02:45+00:00' : '2026-09-29T21:47:58+00:00',
  'source': 'aviationweather.gov',
};

Map<String, dynamic> _body({
  String station = 'VOMM',
  String? name = 'Chennai',
  String status = 'ok',
  Map<String, dynamic>? metar,
  Map<String, dynamic>? taf,
}) => {
  'station': station,
  'station_name': name,
  'city': name?.toLowerCase(),
  'status': status,
  'metar': metar,
  'taf': taf,
  'disclaimer': _disclaimer,
};

AviationData _data(Map<String, dynamic> body) => AviationData(
  station: body['station'] as String,
  stationName: body['station_name'] as String?,
  status: body['status'] as String,
  metar: AviationReport.fromJson(body['metar']),
  taf: AviationReport.fromJson(body['taf']),
  disclaimer: body['disclaimer'] as String,
);

/// The page on its own, themed and with the shared prefs.
Widget _harness(AviationFetcher fetcher, {UiPrefs? prefs}) {
  final p = prefs ?? UiPrefs();
  return UiPrefsScope(
    prefs: p,
    child: ListenableBuilder(
      listenable: p,
      builder: (context, _) => MaterialApp(
        theme: buildAppTheme(personaThemeFor(p.persona)),
        home: AviationPage(fetcher: fetcher),
      ),
    ),
  );
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 3000);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

void main() {
  group('AviationReport.fromJson', () {
    test('reads a METAR: lines, live flag, and the observed stamp', () {
      final r = AviationReport.fromJson(_metar())!;
      expect(r.lines, hasLength(4));
      expect(r.isLive, isTrue);
      expect(r.stamp, 'Observed 03:00 IST · 21:30 UTC');
      expect(r.raw, startsWith('METAR VOMM'));
      expect(r.source, 'aviationweather.gov');
    });

    test('a TAF gets an "Issued" stamp', () {
      expect(AviationReport.fromJson(_taf())!.stamp, 'Issued 22:30 IST · 17:00 UTC');
    });

    test('a snapshot is not live', () {
      expect(AviationReport.fromJson(_metar(live: false))!.isLive, isFalse);
    });

    test('null, malformed and incomplete reports are null, never guessed', () {
      expect(AviationReport.fromJson(null), isNull);
      expect(AviationReport.fromJson('text'), isNull);
      expect(AviationReport.fromJson({'raw': 'METAR ...'}), isNull); // no lines
      expect(
        AviationReport.fromJson({
          'lines': ['x'],
        }),
        isNull,
      ); // no raw
    });

    test('a report without decoded times has no stamp but still reads', () {
      final r = AviationReport.fromJson({..._metar(), 'decoded': <String, dynamic>{}})!;
      expect(r.stamp, isNull);
      expect(r.lines, isNotEmpty);
    });
  });

  group('AviationData', () {
    test('names the station, with or without a display name', () {
      expect(_data(_body()).where, 'Chennai airport (VOMM)');
      expect(_data(_body(station: 'VECC', name: null)).where, 'Station VECC');
    });

    test('unavailable is reported as such', () {
      expect(_data(_body(status: 'unavailable')).unavailable, isTrue);
      expect(_data(_body(metar: _metar())).unavailable, isFalse);
    });
  });

  testWidgets('live reports: METAR and TAF lines, LIVE badges, stamps and the disclaimer', (tester) async {
    _phone(tester);
    final cities = <String>[];
    await tester.pumpWidget(
      _harness((city) async {
        cities.add(city);
        return _data(_body(metar: _metar(), taf: _taf()));
      }),
    );
    await _settle(tester);

    expect(cities, ['chennai']);
    expect(find.text('Airport weather'), findsWidgets);
    expect(find.textContaining('Chennai airport (VOMM), routine report'), findsOneWidget);
    expect(find.text('Wind from the southwest (220°) at 9 km/h (5 kt).'), findsOneWidget);
    expect(find.textContaining('terminal forecast (TAF) issued at 22:30 IST'), findsOneWidget);
    expect(find.textContaining('Temporarily between'), findsOneWidget);
    expect(find.text('LIVE'), findsNWidgets(2));
    expect(find.text('NOT LIVE'), findsNothing);
    expect(find.textContaining('Snapshot taken'), findsNothing);
    expect(find.textContaining('Observed 03:00 IST · 21:30 UTC'), findsOneWidget);
    expect(find.textContaining('Issued 22:30 IST · 17:00 UTC'), findsOneWidget);
    expect(find.text(_disclaimer), findsOneWidget);
  });

  testWidgets('an offline snapshot says NOT LIVE and gives its date in IST', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness((_) async => _data(_body(metar: _metar(live: false), taf: _taf(live: false)))));
    await _settle(tester);

    expect(find.text('NOT LIVE'), findsNWidgets(2));
    expect(find.text('LIVE'), findsNothing);
    // 21:47 UTC on the 29th is 03:17 on the 30th in India.
    expect(find.text('Snapshot taken 30 Sep, 03:17 IST — not a live report.'), findsNWidgets(2));
  });

  testWidgets('one missing report says so beside the other', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness((_) async => _data(_body(metar: null, taf: _taf()))));
    await _settle(tester);

    expect(find.text('No METAR is available for this airport right now.'), findsOneWidget);
    expect(find.textContaining('terminal forecast (TAF)'), findsOneWidget);
    expect(find.text('LIVE'), findsOneWidget); // only the TAF has a badge
  });

  testWidgets('no reports at all: "not available", explicitly not fair weather', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness((_) async => _data(_body(status: 'unavailable'))));
    await _settle(tester);

    expect(find.text('No airport reports'), findsOneWidget);
    expect(find.textContaining("can't be read as fair weather"), findsOneWidget);
    expect(find.text('METAR'), findsNothing);
    expect(find.text('LIVE'), findsNothing);
  });

  testWidgets('an error shows its message and retries', (tester) async {
    _phone(tester);
    var calls = 0;
    await tester.pumpWidget(
      _harness((_) async {
        calls++;
        if (calls == 1) {
          throw AviationError(AviationErrorKind.network, "Couldn't reach the airport weather service.");
        }
        return _data(_body(metar: _metar(), taf: _taf()));
      }),
    );
    await _settle(tester);
    expect(find.text('Airport weather unavailable'), findsOneWidget);
    expect(find.text("Couldn't reach the airport weather service."), findsOneWidget);

    await tester.tap(find.text('Try again'));
    await _settle(tester);
    expect(calls, 2);
    expect(find.text('Airport weather unavailable'), findsNothing);
    expect(find.textContaining('routine report'), findsOneWidget);
  });

  testWidgets('a city change loads that airport; a stale reply is dropped', (tester) async {
    _phone(tester);
    final prefs = UiPrefs();
    final asked = <String>[];
    await tester.pumpWidget(
      _harness((city) async {
        asked.add(city);
        return city == 'mumbai'
            ? _data(
                _body(
                  station: 'VABB',
                  name: 'Mumbai',
                  metar: {
                    ..._metar(),
                    'lines': ['Mumbai airport (VABB), routine report.'],
                  },
                ),
              )
            : _data(_body(metar: _metar()));
      }, prefs: prefs),
    );
    await _settle(tester);
    expect(find.textContaining('Chennai airport (VOMM), routine report'), findsOneWidget);

    prefs.city = 'mumbai';
    await _settle(tester);
    expect(asked, ['chennai', 'mumbai']);
    expect(find.text('Mumbai airport (VABB), routine report.'), findsOneWidget);
    expect(find.textContaining('Chennai airport (VOMM), routine report'), findsNothing);
  });

  testWidgets('the code as issued is behind a tap', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness((_) async => _data(_body(metar: _metar(), taf: _taf()))));
    await _settle(tester);

    expect(find.textContaining('METAR VOMM 292130Z'), findsNothing);
    await tester.tap(find.text('Show the code as issued').first);
    await _settle(tester);
    expect(find.textContaining('METAR VOMM 292130Z 22005KT'), findsOneWidget);
  });

  testWidgets('the drawer opens Airport weather (no server: the error state)', (tester) async {
    _phone(tester);
    final auth = AuthStore(storage: MemorySessionStorage({'guest': true}));
    await auth.restore();
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);

    await tester.tap(find.byTooltip('Menu'));
    await _settle(tester);
    await tester.tap(find.descendant(of: find.byType(Drawer), matching: find.text('Airport weather')));
    await _settle(tester);

    // flutter_test answers every real HTTP request with a 400.
    expect(find.text('Airport weather unavailable'), findsOneWidget);
    expect(find.textContaining('HTTP 400'), findsOneWidget);
    expect(find.byTooltip('Back'), findsOneWidget);
  });

  test('the aviation persona asks for the airport reports', () {
    final p = personaById('aviation');
    expect(p.suggestions.first.template, 'METAR for {city} airport');
    expect(p.quickActions.last.template, 'METAR and TAF for {city} airport');
  });

  test('client bodies decode from real JSON text', () {
    final decoded = jsonDecode(jsonEncode(_body(metar: _metar(), taf: _taf()))) as Map<String, dynamic>;
    expect(AviationReport.fromJson(decoded['metar']), isNotNull);
    expect(AviationReport.fromJson(decoded['taf']), isNotNull);
  });
}
