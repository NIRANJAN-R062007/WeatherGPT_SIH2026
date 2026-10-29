// Climate trends (CLM-5): the /climate client's parsing and the page's states —
// the source line and credit, the metric and period switches, the three trend
// wordings (clear, can't tell, too few years), years with missing days left out
// as gaps, a dated snapshot, no data at all (never "no change"), an error with
// retry, and a city change. Shapes match GET /climate
// (services/orchestrator/climate.py public()).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/climate_client.dart';
import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/pages/climate_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

import 'support/app_tour.dart' show loadAppFonts;

const _label = 'Open-Meteo / ERA5 reanalysis, not IMD station data';
const _changes =
    "Monthly, seasonal and annual figures and trends are computed by WeatherGPT from Open-Meteo's daily ERA5 values.";
const _calendar =
    "Months and seasons are fixed calendar windows. They are not IMD's declared monsoon onset or withdrawal.";

Map<String, dynamic> _trend({
  String status = 'ok',
  int n = 30,
  double mean = 1034.83,
  double slope = 84.021,
  double se = 54.606,
  bool significant = false,
}) => {
  'status': status,
  'n': n,
  'first_year': 1996,
  'last_year': 2025,
  'mean': status == 'ok' ? mean : null,
  'slope_per_decade': status == 'ok' ? slope : null,
  'stderr_per_decade': status == 'ok' ? se : null,
  't': status == 'ok' ? 1.54 : null,
  'significant_95': significant,
};

/// 1996–2026: 2026 is incomplete (null), as ERA5 lags and the year isn't over.
Map<String, dynamic> _body({
  String status = 'ok',
  String city = 'chennai',
  bool live = true,
  Map<String, dynamic>? yearRain,
  Map<String, dynamic>? yearTemp,
  Map<String, dynamic>? monsoonRain,
  Set<int> missingYears = const {2026},
}) {
  final annual = <Map<String, dynamic>>[];
  final seasonal = <Map<String, dynamic>>[];
  for (var y = 1996; y <= 2026; y++) {
    final miss = missingYears.contains(y);
    annual.add({
      'year': y,
      'days': 365,
      'rain_days': miss ? 295 : 365,
      'temp_days': miss ? 295 : 365,
      'rain_mm': miss ? null : 900.0 + (y - 1996) * 5 + (y % 3) * 40,
      'temp_mean_c': miss ? null : 28.0 + (y - 1996) * 0.02,
    });
    seasonal.add({
      'year': y,
      'season': 'monsoon',
      'months': [6, 7, 8, 9],
      'days': 122,
      'rain_days': 122,
      'temp_days': 122,
      'rain_mm': miss ? null : 300.0 + (y - 1996) * 2,
      'temp_mean_c': miss ? null : 31.0,
    });
    seasonal.add({
      'year': y,
      'season': 'winter',
      'months': [1, 2],
      'days': 59,
      'rain_days': 59,
      'temp_days': 59,
      'rain_mm': 25.0,
      'temp_mean_c': 25.5,
    });
  }
  return {
    'status': status,
    'city': city,
    'is_live': live,
    'retrieved_at': '2026-10-29T12:51:12+00:00',
    'requested': {'start_date': '1996-01-01', 'end_date': '2026-10-22'},
    'grid': {'latitude': 13.0, 'longitude': 80.25, 'elevation': 12.0},
    'monthly': status == 'ok' ? <dynamic>[] : null,
    'seasonal': status == 'ok' ? seasonal : null,
    'annual': status == 'ok' ? annual : null,
    'trends': status == 'ok'
        ? {
            'month': <String, dynamic>{},
            'season': {
              'monsoon': {
                'rain_mm':
                    monsoonRain ??
                    _trend(mean: 330, slope: 20, se: 4, significant: true),
                'temp_mean_c': _trend(status: 'insufficient_data', n: 4),
              },
              'winter': {
                'rain_mm': _trend(mean: 25, slope: 0, se: 1),
                'temp_mean_c': _trend(mean: 25.5, slope: 0.1, se: 0.05),
              },
            },
            'year': {
              'rain_mm': yearRain ?? _trend(),
              'temp_mean_c':
                  yearTemp ??
                  _trend(
                    mean: 28.2,
                    slope: 0.243,
                    se: 0.041,
                    significant: true,
                  ),
            },
          }
        : null,
    'data_quality': null,
    'source': 'Open-Meteo',
    'model': 'era5',
    'label': _label,
    'credit': {
      'text': 'Weather data by Open-Meteo.com',
      'url': 'https://open-meteo.com/',
    },
    'changes_note': _changes,
    'calendar_note': _calendar,
    'licence_url': 'https://open-meteo.com/en/licence',
    'terms_url': 'https://open-meteo.com/en/terms',
    'seasons': {
      'winter': [1, 2],
      'monsoon': [6, 7, 8, 9],
    },
    'units': {'precipitation_sum': 'mm', 'temperature_2m_mean': '°C'},
    'min_trend_years': 10,
  };
}

ClimateData _data(Map<String, dynamic> body) => ClimateData.fromJson(body)!;

Widget _harness(ClimateFetcher fetcher, {UiPrefs? prefs}) {
  final p = prefs ?? UiPrefs();
  return UiPrefsScope(
    prefs: p,
    child: ListenableBuilder(
      listenable: p,
      builder: (context, _) => MaterialApp(
        theme: buildAppTheme(personaThemeFor(p.persona)),
        home: ClimatePage(fetcher: fetcher),
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
  tester.view.physicalSize = const Size(1080, 4200);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

void main() {
  group('ClimateData', () {
    test(
      'reads the yearly series; a year with missing days is null, not zero',
      () {
        final d = _data(_body());
        final rain = d.series(ClimatePeriod.year, ClimateMetric.rain);
        expect(rain.first.year, 1996);
        expect(rain.last.year, 2026);
        expect(rain.last.value, isNull);
        expect(rain.where((p) => p.value == null), hasLength(1));
        expect(rain.first.value, 940.0);
      },
    );

    test('reads one season, oldest first, whatever order the rows come in', () {
      final body = _body();
      (body['seasonal'] as List).shuffle();
      final monsoon = _data(
        body,
      ).series(ClimatePeriod.monsoon, ClimateMetric.rain);
      expect(monsoon, hasLength(31));
      expect(
        [for (final p in monsoon) p.year],
        [for (var y = 1996; y <= 2026; y++) y],
      );
      expect(monsoon.first.value, 300.0);
    });

    test('reads the trends for the year and for a season', () {
      final d = _data(_body());
      final year = d.trend(ClimatePeriod.year, ClimateMetric.temperature)!;
      expect(year.hasSlope, isTrue);
      expect(year.slopePerDecade, 0.243);
      expect(year.significant95, isTrue);
      expect(
        d.trend(ClimatePeriod.monsoon, ClimateMetric.rain)!.slopePerDecade,
        20,
      );
      expect(
        d.trend(ClimatePeriod.monsoon, ClimateMetric.temperature)!.hasSlope,
        isFalse,
      );
      expect(d.trend(ClimatePeriod.postMonsoon, ClimateMetric.rain), isNull);
    });

    test('an unavailable answer has no data and says so', () {
      final d = _data(_body(status: 'unavailable'));
      expect(d.unavailable, isTrue);
      expect(d.series(ClimatePeriod.year, ClimateMetric.rain), isEmpty);
      expect(d.label, _label);
    });

    test('a body that is not an object or lacks a status or city is null', () {
      expect(ClimateData.fromJson('x'), isNull);
      expect(ClimateData.fromJson({'city': 'chennai'}), isNull);
      expect(ClimateData.fromJson({'status': 'ok'}), isNull);
    });

    test(
      'falls back to the standard source line when the server sends none',
      () {
        final d = ClimateData.fromJson({'status': 'ok', 'city': 'delhi'})!;
        expect(d.label, _label);
        expect(d.creditUrl, 'https://open-meteo.com/');
        expect(d.changesNote, contains('computed by WeatherGPT'));
      },
    );
  });

  group('formatClimate', () {
    test(
      'rain: thousands grouped, one decimal below 100, a signed slope with a decimal',
      () {
        expect(formatClimate(1034.83, ClimateMetric.rain), '1,035 mm');
        expect(formatClimate(68.34, ClimateMetric.rain), '68.3 mm');
        expect(
          formatClimate(84.021, ClimateMetric.rain, slope: true),
          '+84.0 mm',
        );
        expect(
          formatClimate(-1.925, ClimateMetric.rain, slope: true),
          '−1.9 mm',
        );
      },
    );

    test('temperature: one decimal, two for a slope', () {
      expect(formatClimate(28.2, ClimateMetric.temperature), '28.2 °C');
      expect(
        formatClimate(0.243, ClimateMetric.temperature, slope: true),
        '+0.24 °C',
      );
    });
  });

  group('fetchClimate', () {
    Future<T> withReply<T>(
      http.Response Function(http.Request) reply,
      Future<T> Function() body,
    ) => http.runWithClient(body, () => MockClient((req) async => reply(req)));

    test('asks GET /climate?city= and parses the reply', () async {
      Uri? asked;
      final d = await withReply((req) {
        asked = req.url;
        return http.Response(
          jsonEncode(_body()),
          200,
          headers: {'content-type': 'application/json'},
        );
      }, () => fetchClimate('chennai'));
      expect(asked!.path, '/climate');
      expect(asked!.queryParameters, {'city': 'chennai'});
      expect(d.city, 'chennai');
    });

    test(
      '404 says the server has no history for the city; 500 and bad JSON are errors',
      () async {
        await expectLater(
          withReply(
            (_) => http.Response('', 404),
            () => fetchClimate('chennai'),
          ),
          throwsA(
            isA<ClimateError>().having(
              (e) => e.message,
              'message',
              contains("doesn't have climate history"),
            ),
          ),
        );
        await expectLater(
          withReply(
            (_) => http.Response('', 500),
            () => fetchClimate('chennai'),
          ),
          throwsA(
            isA<ClimateError>().having(
              (e) => e.kind,
              'kind',
              ClimateErrorKind.http,
            ),
          ),
        );
        await expectLater(
          withReply(
            (_) => http.Response('nope', 200),
            () => fetchClimate('chennai'),
          ),
          throwsA(
            isA<ClimateError>().having(
              (e) => e.kind,
              'kind',
              ClimateErrorKind.malformed,
            ),
          ),
        );
      },
    );
  });

  testWidgets(
    'the source line, credit and notes are on the page; the whole-year rainfall chart shows',
    (tester) async {
      _phone(tester);
      final cities = <String>[];
      await tester.pumpWidget(
        _harness((city) async {
          cities.add(city);
          return _data(_body());
        }),
      );
      await _settle(tester);

      expect(cities, ['chennai']);
      expect(find.text('Climate trends'), findsWidgets);
      expect(find.text('Rainfall — Whole year'), findsOneWidget);
      expect(find.text(_label), findsOneWidget);
      expect(find.text('Weather data by Open-Meteo.com'), findsOneWidget);
      expect(find.textContaining('computed by WeatherGPT'), findsOneWidget);
      expect(
        find.textContaining("not IMD's declared monsoon onset"),
        findsOneWidget,
      );
      expect(find.text('Licence'), findsOneWidget);
      expect(find.byType(CustomPaint), findsWidgets);
      expect(
        find.bySemanticsLabel(
          RegExp('Chart: Rainfall — Whole year, 1996 to 2026'),
        ),
        findsOneWidget,
      );
      expect(find.text('Snapshot taken', findRichText: true), findsNothing);
    // 2026 is the one incomplete year.
    expect(find.text('One year with missing days is left out, not drawn as zero.'), findsOneWidget);
    },
  );

  testWidgets(
    'a trend that is not clear says it can\'t be told apart, and that this is not "no change"',
    (tester) async {
      _phone(tester);
      await tester.pumpWidget(_harness((_) async => _data(_body())));
      await _settle(tester);

      // Whole-year rain: +84.0 mm per decade, not significant.
      expect(
        find.textContaining(
          '+84.0 mm per decade (± 54.6 mm) over 30 complete years, 1996–2025',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining("can't be told apart from year-to-year variation"),
        findsOneWidget,
      );
      expect(
        find.textContaining('does not mean nothing has changed'),
        findsOneWidget,
      );
      expect(
        find.textContaining('clear of year-to-year variation'),
        findsNothing,
      );
    },
  );

  testWidgets(
    'Temperature switches the chart and shows a clear trend in plain words',
    (tester) async {
      _phone(tester);
      await tester.pumpWidget(_harness((_) async => _data(_body())));
      await _settle(tester);

      await tester.tap(find.text('Temperature'));
      await _settle(tester);

      expect(find.text('Temperature — Whole year'), findsOneWidget);
      expect(
        find.textContaining(
          '+0.24 °C per decade (± 0.04 °C) over 30 complete years',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining('clear of year-to-year variation at the 95% level'),
        findsOneWidget,
      );
      expect(find.textContaining("can't be told apart"), findsNothing);
      expect(find.text('Average for the year'), findsOneWidget);
    },
  );

  testWidgets(
    'a season is picked on its own, with its own trend; too few years is "no trend", not a line',
    (tester) async {
      _phone(tester);
      await tester.pumpWidget(_harness((_) async => _data(_body())));
      await _settle(tester);

      await tester.tap(find.text('Monsoon (Jun–Sep)'));
      await _settle(tester);
      expect(find.text('Rainfall — Monsoon (Jun–Sep)'), findsOneWidget);
      expect(
        find.textContaining('+20.0 mm per decade (± 4.0 mm)'),
        findsOneWidget,
      );

      await tester.tap(find.text('Temperature'));
      await _settle(tester);
      expect(find.text('No trend'), findsOneWidget);
      expect(
        find.textContaining('at least 10 are needed, and there are 4'),
        findsOneWidget,
      );
      expect(find.text('Trend line'), findsNothing);
    },
  );

  testWidgets(
    'a year with missing days is left out and said so, never drawn as zero',
    (tester) async {
      _phone(tester);
      await tester.pumpWidget(
        _harness((_) async => _data(_body(missingYears: {2000, 2026}))),
      );
      await _settle(tester);

      expect(
        find.text('2 years with missing days are left out, not drawn as zero.'),
        findsOneWidget,
      );
      await tester.tap(find.text('Show every year'));
      await _settle(tester);
      expect(find.text('Missing days — left out'), findsNWidgets(2));
      expect(find.text('940 mm'), findsWidgets); // a year with every day is shown in full
    },
  );

  testWidgets('an offline snapshot gives its date in IST', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_harness((_) async => _data(_body(live: false))));
    await _settle(tester);

    // 12:51 UTC is 18:21 in India.
    expect(
      find.text('Snapshot taken 29 Oct, 18:21 IST — not live data.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'no data at all is "not available", never no change, and still carries the source',
    (tester) async {
      _phone(tester);
      await tester.pumpWidget(
        _harness((_) async => _data(_body(status: 'unavailable'))),
      );
      await _settle(tester);

      expect(find.text('No climate history'), findsOneWidget);
      expect(find.textContaining("can't be read as no change"), findsOneWidget);
      expect(find.text('No trend'), findsNothing);
      expect(find.text(_label), findsOneWidget);
      expect(find.textContaining('computed by WeatherGPT'), findsOneWidget);
    },
  );

  testWidgets('a fetch error shows the message and Try again fetches again', (
    tester,
  ) async {
    _phone(tester);
    var calls = 0;
    await tester.pumpWidget(
      _harness((_) async {
        calls++;
        if (calls == 1) {
          throw ClimateError(
            ClimateErrorKind.timeout,
            'The climate service took too long to answer.',
          );
        }
        return _data(_body());
      }),
    );
    await _settle(tester);

    expect(find.text('Climate trends unavailable'), findsOneWidget);
    expect(
      find.text('The climate service took too long to answer.'),
      findsOneWidget,
    );

    await tester.tap(find.text('Try again'));
    await _settle(tester);

    expect(calls, 2);
    expect(find.text('Rainfall — Whole year'), findsOneWidget);
  });

  testWidgets('changing the city fetches that city', (tester) async {
    _phone(tester);
    final asked = <String>[];
    final prefs = UiPrefs();
    await tester.pumpWidget(
      _harness((city) async {
        asked.add(city);
        return _data(_body(city: city));
      }, prefs: prefs),
    );
    await _settle(tester);
    prefs.city = 'mumbai';
    await _settle(tester);

    expect(asked, ['chennai', 'mumbai']);
  });

  testWidgets('the drawer has a Climate trends tile that opens the page', (
    tester,
  ) async {
    _phone(tester);
    var opened = 0;
    final prefs = UiPrefs();
    await tester.pumpWidget(
      UiPrefsScope(
        prefs: prefs,
        child: MaterialApp(
          theme: buildAppTheme(personaThemeFor(prefs.persona)),
          home: Scaffold(
            body: Sidebar(
              current: AppPage.home,
              onSelect: (_) {},
              onClimate: () => opened++,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Climate trends'));
    expect(opened, 1);
  });

  // README status item 24: every page fits a 360 dp phone at Android's largest
  // text size; the view is tall enough that the whole page is laid out.
  group('large text', () {
    setUpAll(loadAppFonts);

    for (final lang in ['en', 'ta']) {
      for (final scale in [1.6, 2.0]) {
        testWidgets('$lang at $scale× text: nothing overflows', (tester) async {
          tester.view.physicalSize = const Size(945, 16000);
          tester.view.devicePixelRatio = 2.625;
          tester.platformDispatcher.textScaleFactorTestValue = scale;
          addTearDown(tester.view.reset);
          addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
          final prefs = UiPrefs()..lang = lang;
          await tester.pumpWidget(
            _harness((_) async => _data(_body()), prefs: prefs),
          );
          await _settle(tester);

          expect(find.byType(CustomPaint), findsWidgets);
          expect(tester.takeException(), isNull);
        });
      }
    }
  });
}
