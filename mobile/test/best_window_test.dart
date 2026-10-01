// Best Time & What-if page (plan.md §8 Phase 9, WIE-14): the best-window
// card's states and the what-if comparison, against stubbed fetchers.
// Shapes mirror services/orchestrator/main.py's /intelligence/* responses.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/intelligence_client.dart';
import 'package:weathergpt/pages/best_window_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

Map<String, dynamic> _windowOk({String day = 'today'}) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'day': day,
  'activity': 'outdoor',
  'status': 'ok',
  'window': {
    'start_local': '09:00',
    'end_local': '11:00',
    'avg_temp_c': 27.3,
    'max_rain_probability_pct': 15,
    'max_wind_kmh': 12,
    'hours': [],
  },
  'provenance': {'source': 'Google Weather API (live)', 'is_live': true},
};

Map<String, dynamic> _windowNoSuitable({String day = 'today'}) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'day': day,
  'activity': 'outdoor',
  'status': 'no_suitable_window',
  'window': null,
  'provenance': {'source': 'fixture', 'is_live': false},
};

Map<String, dynamic> _windowUnavailable({String day = 'tomorrow'}) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'day': day,
  'activity': 'outdoor',
  'status': 'unavailable',
  'window': null,
  'provenance': null,
};

Map<String, dynamic> _scenarioOk() => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'day': 'today',
  'activity': 'outdoor',
  'status': 'ok',
  'hours': [
    {
      'time': '09:00',
      'available': true,
      'temp_c': 24,
      'rain_probability_pct': 10,
      'wind_kmh': 8,
      'condition': 'clear',
      'suitable': true,
    },
    {'time': '17:00', 'available': false},
  ],
  'better_time': '09:00',
  'provenance': {'source': 'fixture', 'is_live': false},
};

Widget _harness({
  required BestWindowFetcher windowFetcher,
  ScenarioFetcher? scenarioFetcher,
  UiPrefs? prefs,
}) {
  final p = prefs ?? UiPrefs();
  return UiPrefsScope(
    prefs: p,
    child: ListenableBuilder(
      listenable: p,
      builder: (context, _) => MaterialApp(
        theme: buildAppTheme(personaThemeFor(p.persona)),
        home: BestWindowPage(
          windowFetcher: windowFetcher,
          scenarioFetcher: scenarioFetcher ?? ({required city, required day, required times, activity = 'outdoor'}) async => _scenarioOk(),
        ),
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
  testWidgets('a suitable window shows its range and justifying values', (tester) async {
    final days = <String>[];
    await tester.pumpWidget(
      _harness(
        windowFetcher: ({required city, required day, activity = 'outdoor'}) async {
          days.add(day);
          return _windowOk();
        },
      ),
    );
    await _settle(tester);

    expect(days, ['today']);
    expect(find.text('09:00 – 11:00'), findsOneWidget);
    expect(find.text('27.3°C'), findsOneWidget);
    expect(find.text('15%'), findsOneWidget);
    expect(find.text('12 km/h'), findsOneWidget);
    expect(find.textContaining('source: Google Weather API'), findsOneWidget);
  });

  testWidgets('no suitable window is a distinct, honest result', (tester) async {
    await tester.pumpWidget(_harness(windowFetcher: ({required city, required day, activity = 'outdoor'}) async => _windowNoSuitable()));
    await _settle(tester);

    expect(find.text('No suitable window'), findsOneWidget);
    expect(find.textContaining("none passed"), findsOneWidget);
    expect(find.text('09:00 – 11:00'), findsNothing);
  });

  testWidgets('unavailable is neutral, never a suitable or unsuitable verdict', (tester) async {
    await tester.pumpWidget(_harness(windowFetcher: ({required city, required day, activity = 'outdoor'}) async => _windowUnavailable()));
    await _settle(tester);

    expect(find.text('No hourly forecast to check'), findsOneWidget);
    expect(find.text('No suitable window'), findsNothing);
  });

  testWidgets('switching to Tomorrow re-fetches with that day', (tester) async {
    final days = <String>[];
    await tester.pumpWidget(
      _harness(
        windowFetcher: ({required city, required day, activity = 'outdoor'}) async {
          days.add(day);
          return day == 'tomorrow' ? _windowUnavailable() : _windowOk();
        },
      ),
    );
    await _settle(tester);
    expect(days, ['today']);

    await tester.tap(find.text('Tomorrow'));
    await _settle(tester);
    expect(days, ['today', 'tomorrow']);
    expect(find.text('No hourly forecast to check'), findsOneWidget);
  });

  testWidgets('an error shows its message and retries', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      _harness(
        windowFetcher: ({required city, required day, activity = 'outdoor'}) async {
          calls++;
          if (calls == 1) {
            throw IntelligenceError(IntelligenceErrorKind.network, "Couldn't reach the weather intelligence service.");
          }
          return _windowOk();
        },
      ),
    );
    await _settle(tester);
    expect(find.text('Best window unavailable'), findsOneWidget);

    await tester.tap(find.text('Try again'));
    await _settle(tester);
    expect(calls, 2);
    expect(find.text('09:00 – 11:00'), findsOneWidget);
  });

  testWidgets('what-if: comparing two times names the lower rain chance and reports the unavailable one', (tester) async {
    _phone(tester);
    final requestedTimes = <List<String>>[];
    await tester.pumpWidget(
      _harness(
        windowFetcher: ({required city, required day, activity = 'outdoor'}) async => _windowOk(),
        scenarioFetcher: ({required city, required day, required times, activity = 'outdoor'}) async {
          requestedTimes.add(times);
          return _scenarioOk();
        },
      ),
    );
    await _settle(tester);

    await tester.tap(find.text('Compare'));
    await _settle(tester);

    expect(requestedTimes, [
      ['09:00', '17:00'],
    ]);
    expect(find.text('lower rain chance'), findsOneWidget);
    expect(find.text('Not available in this forecast.'), findsOneWidget);
    expect(find.text('24°C'), findsOneWidget);
  });

  testWidgets('a what-if error shows its message and retries', (tester) async {
    _phone(tester);
    var calls = 0;
    await tester.pumpWidget(
      _harness(
        windowFetcher: ({required city, required day, activity = 'outdoor'}) async => _windowOk(),
        scenarioFetcher: ({required city, required day, required times, activity = 'outdoor'}) async {
          calls++;
          if (calls == 1) {
            throw IntelligenceError(IntelligenceErrorKind.network, 'Something went wrong comparing those times.');
          }
          return _scenarioOk();
        },
      ),
    );
    await _settle(tester);

    await tester.tap(find.text('Compare'));
    await _settle(tester);
    expect(find.text('Comparison unavailable'), findsOneWidget);

    await tester.tap(find.text('Try again'));
    await _settle(tester);
    expect(calls, 2);
    expect(find.text('lower rain chance'), findsOneWidget);
  });
}
