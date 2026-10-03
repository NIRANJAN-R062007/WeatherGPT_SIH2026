// Large text (README status item 24): every page, scrolled end to end with
// its expandable parts open, signed in and signed out, at the text sizes
// phones offer (Android's largest is 2×), in all five languages, on a small
// 360 dp phone:
// - nothing overflows;
// - no text is squeezed into a sliver, one word or one letter per line,
//   which never errors but can't be read.
// The app's own fonts are loaded so English measures as on a phone; Indic
// text has no font here and measures somewhat wider than real Noto glyphs,
// so this errs strict.
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/app_tour.dart';

const _langs = ['en', 'hi', 'ta', 'te', 'mr'];

/// A 360 × 740 dp phone with the system text size at [scale].
void _smallPhone(WidgetTester tester, double scale) {
  tester.view.physicalSize = const Size(945, 1943);
  tester.view.devicePixelRatio = 2.625;
  tester.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(tester.view.reset);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

/// Runs [body], collecting every overflow the framework reports as
/// "lib/...dart:line" of the widget that overflowed (or the whole message).
Future<Set<String>> _overflows(Future<void> Function() body) async {
  final found = <String>{};
  final previous = FlutterError.onError;
  FlutterError.onError = (details) {
    final text = details.toString();
    if (!text.contains('overflowed')) return previous?.call(details);
    final at = RegExp(r'(lib/[\w/]+\.dart:\d+)').firstMatch(text);
    found.add(at?.group(1) ?? text.split('\n').take(3).join(' '));
  };
  try {
    await body();
  } finally {
    FlutterError.onError = previous;
  }
  return found;
}

/// Text in a sliver: under 2.5 em wide yet three or more lines tall.
bool _squeezed(RenderParagraph p) {
  final em = p.textScaler.scale(p.text.style?.fontSize ?? 14);
  return p.text.toPlainText().trim().length > 3 && p.size.width < em * 2.5 && p.size.height > em * 3.4;
}

void main() {
  setUpAll(loadAppFonts);

  for (final lang in _langs) {
    for (final scale in [1.3, 1.6, 2.0]) {
      testWidgets('$lang at $scale× text: nothing overflows or is squeezed', (tester) async {
        _smallPhone(tester, scale);
        final squeezed = <String>{};
        Future<void> look(String where) async {
          for (final p in tester.allRenderObjects.whereType<RenderParagraph>()) {
            if (p.hasSize && _squeezed(p)) squeezed.add('$where: "${p.text.toPlainText()}"');
          }
        }

        final overflows = await _overflows(() async {
          await tourApp(tester, lang, at: look);
          await tourSignedOut(tester, lang, at: look);
        });
        expect(overflows, isEmpty, reason: 'overflowing at $scale× in $lang');
        expect(squeezed, isEmpty, reason: 'squeezed at $scale× in $lang');
      });
    }
  }
}
