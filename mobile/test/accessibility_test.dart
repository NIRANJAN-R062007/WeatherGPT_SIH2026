// Screen readers and touch (README status item 24), against Flutter's own
// accessibility guidelines at every stop of the app tour (each page's top
// and end, with its expandable parts open), signed in and signed out:
// - every tappable thing has a label TalkBack / VoiceOver can read;
// - every tap target is at least 48 × 48 dp (Android's minimum);
// - text meets WCAG AA contrast (4.5:1, or 3:1 for large text).
// The full tour runs for one persona in light and dark; the others share
// its layouts, so their palettes are checked on the main pages.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/app_tour.dart';

/// A stop that checks all three guidelines, naming the stop on failure.
TourStop _meetsGuidelines(WidgetTester tester) => (where) async {
  for (final guideline in [labeledTapTargetGuideline, androidTapTargetGuideline, textContrastGuideline]) {
    final result = await guideline.evaluate(tester);
    expect(result.passed, isTrue, reason: '$where — ${guideline.description}:\n${result.reason}');
  }
};

void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

void main() {
  // No app fonts here, unlike the large-text test: the contrast check samples
  // pixels, and real fonts' thin anti-aliased strokes read paler than the
  // colour that's drawn. The test font's solid glyphs sample true.

  for (final appearance in ['light', 'dark']) {
    testWidgets('every page meets the guidelines ($appearance)', (tester) async {
      _phone(tester);
      final semantics = tester.ensureSemantics();
      await tourApp(tester, 'en', persona: 'general', appearance: appearance, at: _meetsGuidelines(tester));
      await tourSignedOut(tester, 'en', appearance: appearance, at: _meetsGuidelines(tester));
      semantics.dispose();
    });
  }

  for (final persona in ['farmer', 'fisherman', 'aviation', 'city_official']) {
    for (final appearance in ['light', 'dark']) {
      testWidgets('the $persona palette meets the guidelines ($appearance)', (tester) async {
        _phone(tester);
        final semantics = tester.ensureSemantics();
        final check = _meetsGuidelines(tester);
        await tourApp(
          tester,
          'en',
          persona: persona,
          appearance: appearance,
          // The main pages' tops: where each palette's colours all appear.
          at: (where) async => where.endsWith('(top)') || where == 'Drawer' ? check(where) : null,
        );
        semantics.dispose();
      });
    }
  }
}
