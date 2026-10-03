// Shared components (lib/components/common.dart) at their size limits.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weathergpt/components/common.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

/// [child] in a themed app, [width] logical pixels wide.
Widget _narrow(double width, Widget child, {String lang = 'en'}) {
  final prefs = UiPrefs()..lang = lang;
  return UiPrefsScope(
    prefs: prefs,
    child: MaterialApp(
      theme: buildAppTheme(personaThemeFor(prefs.persona)),
      home: Scaffold(
        body: Align(
          alignment: Alignment.topLeft,
          child: SizedBox(width: width, child: child),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('a PillButton label too long for its row wraps instead of overflowing', (tester) async {
    await tester.pumpWidget(
      _narrow(
        160,
        PillButton(icon: Icons.refresh, label: 'A label much wider than the button may be', onPressed: () {}),
      ),
    );
    expect(tester.takeException(), isNull);
    final label = find.text('A label much wider than the button may be');
    expect(label, findsOneWidget);
    expect(tester.getRect(label).right, lessThanOrEqualTo(160));
  });

  testWidgets("an ErrorPanel's Try again fits a narrow screen in every language", (tester) async {
    for (final lang in ['en', 'hi', 'ta', 'te', 'mr']) {
      await tester.pumpWidget(
        _narrow(
          280,
          ErrorPanel(icon: Icons.wifi_off, title: 'Forecast unavailable', message: 'x', onRetry: () {}),
          lang: lang,
        ),
      );
      expect(tester.takeException(), isNull, reason: lang);
    }
  });
}
