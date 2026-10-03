// The colour legend on Alerts comes from GET /glossary (the one shared
// wording, plan.md §3.1) when it answers, and says so when a translation
// hasn't been reviewed by a native speaker; /warnings' own legend stands in
// otherwise.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/glossary_client.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/response_cache.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/ui_strings.dart';

import 'support/fake_backend.dart';

const _note = 'These translations have not been reviewed by a native speaker yet.';

Future<void> _alerts(WidgetTester tester, String lang) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
  final backend = FakeBackend()..warningStatus = 'unavailable';
  await http.runWithClient(() async {
    await tester.pumpWidget(
      WeatherGptApp(
        auth: await guestAuth(),
        prefsStore: MemoryPrefsStore({'lang': lang}),
        citiesFetcher: () async => null,
        responseCache: MemoryResponseCache(),
      ),
    );
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.byIcon(Icons.notifications_none)));
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }, () => backend.client);
}

void main() {
  test('the legend runs green to red, from the colour words and meanings', () {
    final g = Glossary.fromJson(glossaryReply('hi'));
    expect(g.legend!.map((r) => r['colour']), ['green', 'yellow', 'orange', 'red']);
    expect(g.legend!.first, {'colour': 'green', 'label': 'Green (hi)', 'meaning': 'Green means something (hi)'});
    expect(g.legendReviewed, isFalse);
    expect(Glossary.fromJson(glossaryReply('en')).legendReviewed, isTrue);
    expect(Glossary.fromJson({'entries': {}}).legend, isNull);
  });

  testWidgets('Alerts shows the glossary legend, marked as unreviewed in Hindi', (tester) async {
    await _alerts(tester, 'hi');
    expect(find.textContaining('Orange means something (hi)', findRichText: true), findsOneWidget);
    expect(find.text(kUiStrings['hi']![_note]!), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('in English the legend needs no note', (tester) async {
    await _alerts(tester, 'en');
    expect(find.textContaining('Orange means something (en)', findRichText: true), findsOneWidget);
    expect(find.text(_note), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
}
