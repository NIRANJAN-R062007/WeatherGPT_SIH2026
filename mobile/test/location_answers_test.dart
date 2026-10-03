// Answers for any place in India (the backend's location resolver, PR #44):
// the GPS fix travels snapped to the 0.05° grid, a reply naming a place
// outside the demo cities shows that place, and a "which one?" reply offers
// its places to tap, which re-asks for the one tapped.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/api_client.dart';
import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/components/ask_answer.dart';
import 'package:weathergpt/location.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/response_cache.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

import 'support/fake_backend.dart';

Future<void> _pumpAnswer(
  WidgetTester tester,
  Map<String, dynamic> body, {
  void Function(String, String)? onPickPlace,
  VoidCallback? onUseLocation,
}) {
  final prefs = UiPrefs();
  return tester.pumpWidget(
    UiPrefsScope(
      prefs: prefs,
      child: MaterialApp(
        theme: buildAppTheme(personaThemeFor(prefs.persona)),
        home: Scaffold(
          body: SingleChildScrollView(
            child: AskAnswer(outcome: classifyAsk(body), onPickPlace: onPickPlace, onUseLocation: onUseLocation),
          ),
        ),
      ),
    ),
  );
}

void main() {
  test('a fix is snapped to the 0.05° grid', () {
    expect(snapToGrid(13.0827), 13.1);
    expect(snapToGrid(80.2707), 80.25);
    expect(snapToGrid(12.97), 12.95);
  });

  test('Use my location keeps the snapped fix; choosing a city clears it', () {
    final prefs = UiPrefs()..useLocation(13.0827, 80.2707, 'chennai');
    expect(prefs.here, (lat: 13.1, lon: 80.25));
    expect(prefs.city, 'chennai');
    expect(prefs.toSaved().values.join(), isNot(contains('13.1')), reason: 'never saved');
    prefs.city = 'madurai';
    expect(prefs.here, isNull);
  });

  test('/ask carries the fix and a tapped place', () async {
    late Uri asked;
    await http.runWithClient(
      () => askWeather(text: 'weather', city: 'chennai', here: (lat: 13.1, lon: 80.25), placeId: 'gn:1259123'),
      () => MockClient((req) async {
        asked = req.url;
        return http.Response(jsonEncode(askReply()), 200);
      }),
    );
    expect(asked.queryParameters, containsPair('lat', '13.1'));
    expect(asked.queryParameters, containsPair('lon', '80.25'));
    expect(asked.queryParameters, containsPair('place_id', 'gn:1259123'));
  });

  testWidgets('an answer for a place outside the demo cities names that place', (tester) async {
    await _pumpAnswer(tester, placeAnswerReply('Ooty, Tamil Nadu'));
    expect(find.text('Ooty, Tamil Nadu'), findsOneWidget);
  });

  testWidgets('"which one?" offers its places, and a tap picks one', (tester) async {
    final picked = <(String, String)>[];
    await _pumpAnswer(tester, kPutturReply, onPickPlace: (id, label) => picked.add((id, label)));
    expect(find.text('Which place?'), findsOneWidget);
    await tester.tap(find.text('Puttūr, Karnataka · Dakshina Kannada'));
    expect(picked, [('gn:1259124', 'Puttūr, Karnataka')]);
  });

  testWidgets('"not found" offers the nearest place; "which place?" offers Use my location', (tester) async {
    final picked = <String>[];
    var located = 0;
    await _pumpAnswer(tester, {
      'intent': 'unsupported_city',
      'not_found': true,
      'nearest': {'place_id': 'gn:1264792', 'label': 'Londa, Karnataka', 'district': 'Belgaum', 'state': 'Karnataka'},
      'message': "I couldn't find London in India. The nearest known place is Londa, Karnataka.",
    }, onPickPlace: (id, _) => picked.add(id));
    expect(find.text('Place not found'), findsOneWidget);
    await tester.tap(find.text('Use Londa, Karnataka'));
    expect(picked, ['gn:1264792']);

    await _pumpAnswer(tester, {
      'intent': 'will_it_rain',
      'message': 'Which place? Name a town or city, or share your location.',
      'needs_location': true,
    }, onUseLocation: () => located++);
    await tester.tap(find.text('Use my location'));
    expect(located, 1);
  });

  testWidgets('in Chat, a tapped place is asked as a new turn that says where', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);
    final backend = FakeBackend();
    await http.runWithClient(() async {
      await tester.pumpWidget(
        WeatherGptApp(
          auth: await guestAuth(),
          prefsStore: MemoryPrefsStore(),
          citiesFetcher: () async => null,
          responseCache: MemoryResponseCache(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.text('Chat')));
      await tester.pump(const Duration(milliseconds: 300));
      await tester.enterText(find.byType(TextField).last, 'weather in Puttur');
      await tester.pump();
      await tester.tap(find.byTooltip('Send').last);
      await tester.pump(const Duration(seconds: 1));
      await tester.tap(find.text('Puttūr, Andhra Pradesh · Tirupati'));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('weather in Puttur'), findsNWidgets(2)); // the question, asked again
      expect(find.text('Puttūr, Andhra Pradesh'), findsWidgets); // the bubble's place and the answer's chip
      expect(find.textContaining('31°C in Puttūr'), findsOneWidget);
    }, () => backend.client);
    await tester.pumpWidget(const SizedBox());
  });
}
