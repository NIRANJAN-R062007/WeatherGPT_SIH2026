import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/main.dart';

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

void main() {
  testWidgets('boots to Home with the web shell: topbar city pill and hero', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);

    expect(find.text('Chennai, Tamil Nadu'), findsOneWidget);
    expect(find.text('WeatherGPT Copilot'), findsOneWidget);
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
    expect(find.text('Ask WeatherGPT'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Forecast');
    expect(find.text('Forecast Provenance'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Alerts & Warnings');
    expect(find.text('Warnings service unreachable'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Settings');
    expect(find.text('Persona'), findsOneWidget);
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
    expect(find.text('WeatherGPT Copilot'), findsOneWidget);
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

  testWidgets('settings pills switch language, unit and persona', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    await _settle(tester);
    await _openDrawerAndGo(tester, 'Settings');

    Semantics semanticsOf(String text) => tester.widget<Semantics>(
          find
              .ancestor(
                of: find.text(text),
                matching: find.byWidgetPredicate((w) => w is Semantics && w.properties.selected != null),
              )
              .first,
        );

    expect(semanticsOf('English').properties.selected, isTrue);
    await tester.tap(find.text('हिन्दी'));
    await _settle(tester);
    expect(semanticsOf('हिन्दी').properties.selected, isTrue);
    expect(semanticsOf('English').properties.selected, isFalse);

    await tester.tap(find.text('Fahrenheit (°F)'));
    await _settle(tester);
    expect(semanticsOf('Fahrenheit (°F)').properties.selected, isTrue);

    await tester.ensureVisible(find.text('Farmer'));
    await _settle(tester);
    await tester.tap(find.text('Farmer'));
    await _settle(tester);
    expect(semanticsOf('Farmer').properties.selected, isTrue);
    expect(semanticsOf('General Citizen').properties.selected, isFalse);
  });
}
