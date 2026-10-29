// Cyclone map (CYC-5): the /cyclones client's parsing and the page's states —
// a live storm, an offline snapshot, GDACS unavailable (never "no cyclones"),
// a live empty answer versus a snapshot's, and a fetch error with retry.
// Shapes match GET /cyclones (services/orchestrator/gdacs.py public()); the
// storm is a trimmed copy of the dated fixture (data/fixtures/gdacs).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/cyclones_client.dart';
import 'package:weathergpt/pages/cyclone_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

import 'support/app_tour.dart' show loadAppFonts;

const _disclaimer =
    'GDACS cyclone alerts are produced automatically, are not reviewed by human experts and do not replace official warnings. Follow IMD and your state disaster authority.';
const _attribution = 'Cyclone data: Global Disaster Alert and Coordination System, GDACS. Not an IMD product.';

Map<String, dynamic> _event({String level = 'Red', String episode = 'Orange'}) => {
  'event_id': 1001345,
  'episode_id': 10,
  'name': 'ARNAB-26',
  'title': 'Tropical Cyclone ARNAB-26',
  'alert_level': level,
  'alert_score': 3.0,
  'episode_alert_level': episode,
  'is_current': true,
  'from_date': '2026-10-26T00:00:00+00:00',
  'to_date': '2026-10-28T06:00:00+00:00',
  'date_modified': '2026-10-29T08:02:06+00:00',
  'lon': 81.8,
  'lat': 16.4,
  'country_iso3': 'IND',
  'source_agency': 'JTWC',
  'severity': {'value': 222.2, 'unit': 'km/h', 'text': 'Tropical Storm (maximum wind speed of 222 km/h)'},
  'report_url': 'https://www.gdacs.org/report.aspx?eventid=1001345&episodeid=10&eventtype=TC',
  'track': {
    'segments': [
      {
        'category': 'HU',
        'is_forecast': false,
        'coordinates': [
          [83.8, 16.2],
          [82.7, 16.3],
        ],
      },
      {
        'category': 'TD',
        'is_forecast': true,
        'coordinates': [
          [81.7, 19.9],
          [81.6, 21.0],
        ],
      },
      {'category': 'TD', 'is_forecast': true, 'coordinates': <dynamic>[]}, // dropped
    ],
    'cones': [
      {
        'coordinates': [
          [
            [81.8, 16.15],
            [82.0, 17.0],
            [81.0, 17.0],
            [81.8, 16.15],
          ],
        ],
      },
    ],
    'areas': [
      {
        'class': 'Poly_Green',
        'label': '60 km/h',
        'coordinates': [
          [
            [88.4, 14.3],
            [88.9, 14.4],
            [88.6, 14.9],
            [88.4, 14.3],
          ],
        ],
      },
    ],
  },
  'source': 'GDACS',
};

Map<String, dynamic> _body({
  String status = 'ok',
  Object? events = 'one',
  bool live = true,
  bool complete = true,
}) => {
  'status': status,
  'events': events == 'one' ? [_event()] : events,
  'count': events is List ? events.length : (events == 'one' ? 1 : null),
  'is_live': live,
  'retrieved_at': live ? '2026-10-29T11:48:18+00:00' : '2026-10-29T11:48:18+00:00',
  'complete': complete,
  'source': 'GDACS',
  'source_url': 'https://www.gdacs.org/',
  'terms_url': 'https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf',
  'attribution': _attribution,
  'disclaimer': _disclaimer,
  'area': {'lon_min': 55.0, 'lon_max': 100.0, 'lat_min': 0.0, 'lat_max': 30.0, 'iso3': 'IND'},
  'window_days': 14,
};

CyclonesData _data(Map<String, dynamic> body) => CyclonesData.fromJson(body)!;

Widget _harness(CyclonesFetcher fetcher, {UiPrefs? prefs}) {
  final p = prefs ?? UiPrefs();
  return UiPrefsScope(
    prefs: p,
    child: ListenableBuilder(
      listenable: p,
      builder: (context, _) => MaterialApp(
        theme: buildAppTheme(personaThemeFor(p.persona)),
        home: CyclonePage(fetcher: fetcher),
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
  group('CycloneEvent.fromJson', () {
    test('reads the storm: levels, position, severity text, agency and report link', () {
      final e = CycloneEvent.fromJson(_event())!;
      expect(e.name, 'ARNAB-26');
      expect(e.alertLevel, 'Red'); // GDACS's own level, not graded by the app
      expect(e.episodeAlertLevel, 'Orange');
      expect(e.isCurrent, isTrue);
      expect((e.lon, e.lat), (81.8, 16.4));
      expect(e.sourceAgency, 'JTWC');
      expect(e.severityText, startsWith('Tropical Storm'));
      expect(e.reportUrl, contains('gdacs.org'));
    });

    test('keeps the observed and forecast legs apart and drops a leg with no points', () {
      final e = CycloneEvent.fromJson(_event())!;
      expect(e.segments, hasLength(2));
      expect(e.segments.first.isForecast, isFalse);
      expect(e.segments.last.isForecast, isTrue);
      expect(e.segments.first.points.first, (lon: 83.8, lat: 16.2));
      expect(e.cone, hasLength(1));
      expect(e.windAreas.single.label, '60 km/h');
    });

    test('an entry without an id, a name or a level is dropped, not guessed', () {
      expect(CycloneEvent.fromJson(null), isNull);
      expect(CycloneEvent.fromJson({..._event(), 'event_id': null}), isNull);
      expect(CycloneEvent.fromJson({..._event(), 'name': ''}), isNull);
      expect(CycloneEvent.fromJson({..._event(), 'alert_level': null}), isNull);
    });

    test('bad numbers in a track are skipped rather than crashing', () {
      final e = CycloneEvent.fromJson({
        ..._event(),
        'lon': 'x',
        'track': {
          'segments': [
            {
              'is_forecast': false,
              'coordinates': [
                [1, 2],
                ['a', 'b'],
                [double.nan, 3],
                [3, 4],
              ],
            },
          ],
        },
      })!;
      expect(e.lon, isNull);
      expect(e.segments.single.points, hasLength(2));
    });
  });

  group('CyclonesData', () {
    test('a failed fetch is unavailable, with no event list at all', () {
      final d = _data(_body(status: 'unavailable', events: null, live: false, complete: false));
      expect(d.unavailable, isTrue);
      expect(d.events, isNull);
      expect(d.noCyclonesConfirmed, isFalse);
    });

    test('"no cyclones" is confirmed only by a live, complete, empty answer', () {
      expect(_data(_body(events: <dynamic>[])).noCyclonesConfirmed, isTrue);
      expect(_data(_body(events: <dynamic>[], live: false)).noCyclonesConfirmed, isFalse);
      expect(_data(_body(events: <dynamic>[], complete: false)).noCyclonesConfirmed, isFalse);
      expect(_data(_body()).noCyclonesConfirmed, isFalse);
    });

    test('a body that is not an object, or has no status, is null', () {
      expect(CyclonesData.fromJson('text'), isNull);
      expect(CyclonesData.fromJson({'events': []}), isNull);
    });

    test('falls back to the standard attribution and disclaimer when the server sends none', () {
      final d = CyclonesData.fromJson({'status': 'ok', 'events': <dynamic>[]})!;
      expect(d.attribution, contains('Not an IMD product'));
      expect(d.disclaimer, contains('do not replace official warnings'));
    });
  });

  group('fetchCyclones', () {
    Future<T> withReply<T>(http.Response Function(http.Request) reply, Future<T> Function() body) =>
        http.runWithClient(body, () => MockClient((req) async => reply(req)));

    test('asks GET /cyclones with no parameters and parses the reply', () async {
      Uri? asked;
      final d = await withReply((req) {
        asked = req.url;
        return http.Response(jsonEncode(_body()), 200, headers: {'content-type': 'application/json'});
      }, fetchCyclones);
      expect(asked!.path, '/cyclones');
      expect(asked!.hasQuery, isFalse);
      expect(d.events!.single.name, 'ARNAB-26');
    });

    test('a server from before the route (404) says so', () async {
      await expectLater(
        withReply((_) => http.Response('', 404), fetchCyclones),
        throwsA(isA<CyclonesError>().having((e) => e.message, 'message', contains("doesn't have the cyclone map"))),
      );
    });

    test('a 500 and unreadable JSON are errors, not empty data', () async {
      await expectLater(
        withReply((_) => http.Response('', 500), fetchCyclones),
        throwsA(isA<CyclonesError>().having((e) => e.kind, 'kind', CyclonesErrorKind.http)),
      );
      await expectLater(
        withReply((_) => http.Response('not json', 200), fetchCyclones),
        throwsA(isA<CyclonesError>().having((e) => e.kind, 'kind', CyclonesErrorKind.malformed)),
      );
    });
  });

  testWidgets('a live storm: GDACS on the map, LIVE, the storm card, attribution and disclaimer', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness(() async => _data(_body())));
    await _settle(tester);

    expect(find.text('Cyclone map'), findsWidgets);
    expect(find.text('GDACS'), findsWidgets); // on the map card and on the storm card
    expect(find.text('LIVE'), findsOneWidget);
    expect(find.text('NOT LIVE'), findsNothing);
    expect(find.text('Tropical Cyclone ARNAB-26'), findsOneWidget);
    expect(find.text('Red alert'), findsOneWidget);
    expect(find.textContaining('Tropical Storm (maximum wind speed of 222 km/h)', findRichText: true), findsOneWidget);
    expect(find.textContaining('Orange alert', findRichText: true), findsOneWidget); // the episode level differs, so it's shown
    expect(find.textContaining('JTWC', findRichText: true), findsOneWidget);
    expect(find.text(_disclaimer), findsOneWidget);
    expect(find.text(_attribution), findsOneWidget);
    expect(find.text('Open the GDACS report'), findsOneWidget);
    expect(find.byType(CustomPaint), findsWidgets);
    expect(
      find.bySemanticsLabel(RegExp('Map of tropical cyclones near India: ARNAB-26, Red alert')),
      findsOneWidget,
    );
  });

  testWidgets('an offline snapshot says NOT LIVE and gives its date in IST', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness(() async => _data(_body(live: false))));
    await _settle(tester);

    expect(find.text('NOT LIVE'), findsOneWidget);
    expect(find.text('LIVE'), findsNothing);
    // 11:48 UTC is 17:18 in India.
    expect(find.text('Snapshot taken 29 Oct, 17:18 IST — not live data.'), findsOneWidget);
  });

  testWidgets('GDACS unavailable is "no data", never "no cyclones"', (tester) async {
    _phone(tester);
    await tester.pumpWidget(
      _harness(() async => _data(_body(status: 'unavailable', events: null, live: false, complete: false))),
    );
    await _settle(tester);

    expect(find.text('No cyclone data'), findsOneWidget);
    expect(find.textContaining("can't be read as"), findsOneWidget);
    expect(find.textContaining('No cyclones near India'), findsNothing);
    expect(find.text(_disclaimer), findsOneWidget); // the disclaimer is on every state
    expect(find.text(_attribution), findsOneWidget);
  });

  testWidgets('a live, complete, empty answer says there are none', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness(() async => _data(_body(events: <dynamic>[]))));
    await _settle(tester);

    expect(find.text('No cyclones near India'), findsOneWidget);
    expect(find.text('GDACS lists no tropical cyclone near India in the last 14 days.'), findsOneWidget);
  });

  testWidgets("a snapshot's empty list does not say all clear", (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness(() async => _data(_body(events: <dynamic>[], live: false))));
    await _settle(tester);

    expect(find.text('No cyclones near India'), findsNothing);
    expect(find.text('No cyclones in this data'), findsOneWidget);
    expect(find.textContaining("don't read it as all clear"), findsOneWidget);
  });

  testWidgets('a fetch error shows the message and Try again fetches again', (tester) async {
    _phone(tester);
    var calls = 0;
    await tester.pumpWidget(
      _harness(() async {
        calls++;
        if (calls == 1) {
          throw CyclonesError(CyclonesErrorKind.timeout, 'The cyclone service took too long to answer.');
        }
        return _data(_body());
      }),
    );
    await _settle(tester);

    expect(find.text('Cyclone map unavailable'), findsOneWidget);
    expect(find.text('The cyclone service took too long to answer.'), findsOneWidget);
    expect(find.text('Tropical Cyclone ARNAB-26'), findsNothing);

    await tester.tap(find.text('Try again'));
    await _settle(tester);

    expect(calls, 2);
    expect(find.text('Tropical Cyclone ARNAB-26'), findsOneWidget);
  });

  testWidgets('the drawer has a Cyclone map tile that opens the page', (tester) async {
    _phone(tester);
    var opened = 0;
    final prefs = UiPrefs();
    await tester.pumpWidget(
      UiPrefsScope(
        prefs: prefs,
        child: MaterialApp(
          theme: buildAppTheme(personaThemeFor(prefs.persona)),
          home: Scaffold(
            body: Sidebar(current: AppPage.home, onSelect: (_) {}, onCyclones: () => opened++),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Cyclone map'));
    expect(opened, 1);
  });

  // README status item 24: every page fits on a 360 dp phone at Android's
  // largest text size. The storm card and the map card are the tallest parts;
  // the view is made tall enough that the whole page is laid out.
  group('large text', () {
    setUpAll(loadAppFonts);

    for (final lang in ['en', 'ta']) {
      for (final scale in [1.6, 2.0]) {
        testWidgets('$lang at $scale× text: nothing overflows', (tester) async {
          tester.view.physicalSize = const Size(945, 14000);
          tester.view.devicePixelRatio = 2.625;
          tester.platformDispatcher.textScaleFactorTestValue = scale;
          addTearDown(tester.view.reset);
          addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
          final prefs = UiPrefs()..lang = lang;
          await tester.pumpWidget(_harness(() async => _data(_body()), prefs: prefs));
          await _settle(tester);

          expect(find.byType(CustomPaint), findsWidgets);
          expect(tester.takeException(), isNull);
        });
      }
    }
  });
}
