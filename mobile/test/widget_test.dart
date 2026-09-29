import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/persona_theme.dart';

// flutter_test answers every real HTTP request with a 400, so pages that
// fetch on load land in their error state — which is also what's checked.
Future<void> _settle(WidgetTester tester) async {
  // Home's hero gradient drifts forever, so pumpAndSettle would time out.
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

Future<void> _openDrawerAndGo(WidgetTester tester, String label) async {
  await tester.tap(find.byTooltip('Menu'));
  await _settle(tester);
  await tester.tap(find.descendant(of: find.byType(Drawer), matching: find.text(label)));
  await _settle(tester);
}

Future<void> _tab(WidgetTester tester, String label) async {
  await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.text(label)));
  await _settle(tester);
}

void main() {
  testWidgets('boots to Home: city pill, quick questions and the now card', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);

    expect(find.text('Chennai, Tamil Nadu'), findsOneWidget);
    expect(find.text('Quick Questions'), findsOneWidget);
    // /facts got a 400 -> the hero shows the error panel, not stale numbers.
    expect(find.text('Live conditions unavailable'), findsOneWidget);
  });

  testWidgets('drawer mirrors web Sidebar nav, without History', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);
    await tester.tap(find.byTooltip('Menu'));
    await _settle(tester);

    final drawer = find.byType(Drawer);
    for (final label in ['Home', 'Chat & Evidence', 'Forecast', 'Alerts & Warnings', 'Settings']) {
      expect(find.descendant(of: drawer, matching: find.text(label)), findsOneWidget, reason: label);
    }
    expect(find.descendant(of: drawer, matching: find.text('History')), findsNothing);
  });

  testWidgets('every page renders', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);

    await _openDrawerAndGo(tester, 'Chat & Evidence');
    expect(find.text('Suggested Questions'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Forecast');
    expect(find.text('Forecast unavailable'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Alerts & Warnings');
    expect(find.text('Warnings service unreachable'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Settings');
    expect(find.text('Change Persona'), findsOneWidget);
  });

  testWidgets('bottom bar switches pages; More is Settings', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);

    await _tab(tester, 'Chat');
    expect(find.text('Suggested Questions'), findsOneWidget);
    await _tab(tester, 'Alerts');
    expect(find.text('Active Alerts'), findsOneWidget);
    await _tab(tester, 'More');
    expect(find.text('Change Persona'), findsOneWidget);
    await _tab(tester, 'Home');
    expect(find.text('Quick Questions'), findsOneWidget);
  });

  testWidgets('a Home quick question is asked in Chat', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);

    await tester.ensureVisible(find.text('Will it rain today?'));
    await _settle(tester);
    await tester.tap(find.text('Will it rain today?'));
    await _settle(tester);

    expect(find.text('Will it rain today in Chennai?'), findsOneWidget); // the user bubble
    expect(find.text('Suggested Questions'), findsNothing); // transcript mode
  });

  testWidgets('Android back: closes the drawer first, then returns Home', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);
    await _openDrawerAndGo(tester, 'Alerts & Warnings');
    expect(find.text('Warnings service unreachable'), findsOneWidget);

    await tester.tap(find.byTooltip('Menu'));
    await _settle(tester);
    expect(find.byType(Drawer), findsOneWidget);

    await tester.binding.handlePopRoute();
    await _settle(tester);
    expect(find.byType(Drawer), findsNothing);
    expect(find.text('Warnings service unreachable'), findsOneWidget); // still on Alerts

    await tester.binding.handlePopRoute();
    await _settle(tester);
    expect(find.text('Warnings service unreachable'), findsNothing); // back on Home
    expect(find.text('Quick Questions'), findsOneWidget);
  });

  testWidgets('city picker updates the shared city', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);

    await tester.tap(find.text('Chennai, Tamil Nadu'));
    await _settle(tester);
    expect(find.text('Use my location'), findsOneWidget);

    await tester.tap(find.text('Mumbai, Maharashtra'));
    await _settle(tester);
    expect(find.text('Mumbai, Maharashtra'), findsOneWidget);
    expect(find.text('Chennai, Tamil Nadu'), findsNothing);
  });

  testWidgets('settings rows switch language, unit and persona', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);
    await _tab(tester, 'More');

    await tester.tap(find.text('Language'));
    await _settle(tester);
    await tester.tap(find.text('हिन्दी'));
    await _settle(tester);
    expect(find.text('हिन्दी'), findsOneWidget); // the row's value, sheet closed
    expect(find.text('English'), findsNothing);

    await tester.tap(find.text('Units'));
    await _settle(tester);
    await tester.tap(find.text('Fahrenheit (°F)'));
    await _settle(tester);
    expect(find.text('Fahrenheit (°F)'), findsOneWidget);

    await tester.tap(find.text('Change Persona'));
    await _settle(tester);
    expect(find.text('Choose your persona'), findsOneWidget);
    await tester.ensureVisible(find.text('Farmer'));
    await _settle(tester);
    await tester.tap(find.text('Farmer'));
    await _settle(tester);
    await _settle(tester); // the picker lingers a beat so the re-theme shows
    expect(find.text('Choose your persona'), findsNothing);
    expect(find.text('Farmer'), findsOneWidget);
    expect(find.text('Better decisions for your crops.'), findsOneWidget);
  });

  testWidgets('the persona is the app-wide theme and survives page switches', (tester) async {
    PersonaTheme active() => PersonaTheme.of(tester.element(find.byType(BottomNav)));

    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);
    expect(active().primary, personaThemes['general']!.primary);

    for (final (label, id) in [
      ('Farmer', 'farmer'),
      ('Fisherman', 'fisherman'),
      ('Aviation', 'aviation'),
      ('City Official', 'city_official'),
      ('General Citizen', 'general'),
    ]) {
      await _tab(tester, 'More');
      await tester.tap(find.text('Change Persona'));
      await _settle(tester);
      await tester.ensureVisible(find.text(label));
      await _settle(tester);
      await tester.tap(find.text(label));
      await _settle(tester);
      await _settle(tester);

      final expected = personaThemes[id]!;
      expect(active().primary, expected.primary, reason: label);
      expect(active().scene, expected.scene, reason: label);
      // Material widgets follow it too.
      expect(Theme.of(tester.element(find.byType(BottomNav))).colorScheme.primary, expected.primary);
      for (final tab in ['Home', 'Chat', 'Forecast', 'Alerts', 'More']) {
        await _tab(tester, tab);
        expect(active().primary, expected.primary, reason: '$label on $tab');
      }
    }
  });
}
