// Travel and Sowing advice (TFA-13): the /advisory client, the page's
// conversation (the backend asks for what it still needs, carried slot by
// slot, then answers with a verdict and its reasons), and which personas
// see which page in the drawer.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/advisory_client.dart';
import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/components/common.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/pages/advisory_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/response_cache.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

import 'support/fake_backend.dart';

const _askBack = {
  'kind': 'travel',
  'status': 'ask_back',
  'question': 'Where are you travelling from?',
  'slots': {'destination': 'madurai'},
  'asking': 'origin',
  'unsupported': {},
};

/// The page with a scripted backend that records each turn it was sent.
Future<List<(String, Map<String, String>, String?)>> _pumpPage(
  WidgetTester tester,
  List<Map<String, dynamic>> replies, {
  String lang = 'en',
}) async {
  final sent = <(String, Map<String, String>, String?)>[];
  final prefs = UiPrefs()..lang = lang;
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    UiPrefsScope(
      prefs: prefs,
      child: MaterialApp(
        theme: buildAppTheme(personaThemeFor(prefs.persona)),
        home: AdvisoryPage(
          kind: AdvisoryKind.travel,
          fetcher: (kind, {required text, required lang, slots = const {}, asking}) async {
            sent.add((text, slots, asking));
            return AdvisoryReply.fromJson(replies[sent.length - 1]);
          },
        ),
      ),
    ),
  );
  return sent;
}

void main() {
  test('an answer parses: verdict, reasons, window, sources', () {
    final reply = AdvisoryReply.fromJson(advisoryReply('travel'));
    expect(reply.isAnswer, isTrue);
    expect(reply.verdict, 'caution');
    expect(reply.pros, hasLength(2));
    expect(reply.cons, ['The IMD warning for the destination is not available.']);
    expect(reply.window, (start: '09:00', end: '11:00'));
    expect(reply.sources, [kFakeSource]);
    expect(reply.allLive, isTrue);
    expect(reply.slots['origin'], 'chennai');
  });

  test('a turn posts the text, the slots so far and what was asked', () async {
    late Map<String, dynamic> body;
    late Uri url;
    await http.runWithClient(
      () => fetchAdvisory(
        AdvisoryKind.sowing,
        text: 'groundnut',
        lang: 'ta',
        slots: {'district': 'madurai'},
        asking: 'crop',
      ),
      () => MockClient((req) async {
        url = req.url;
        body = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response(jsonEncode(advisoryReply('sowing')), 200);
      }),
    );
    expect(url.path, '/advisory/sowing');
    expect(body, {
      'text': 'groundnut',
      'lang': 'ta',
      'slots': {'district': 'madurai'},
      'asking': 'crop',
    });
  });

  testWidgets('the backend asks back, the answer goes with the carried slots, then a verdict', (tester) async {
    final sent = await _pumpPage(tester, [_askBack, advisoryReply('travel')]);
    expect(find.text('Try asking'), findsOneWidget);

    await tester.tap(find.text('Chennai to Madurai tomorrow by train'));
    await tester.pump();
    expect(find.text('Where are you travelling from?'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Chennai');
    await tester.tap(find.byTooltip('Send'));
    await tester.pump();
    final (text, slots, asking) = sent.last;
    expect(text, 'Chennai');
    expect(slots, {'destination': 'madurai'});
    expect(asking, 'origin');
    expect(find.text('Go with caution'), findsOneWidget);
    // The trip in reading order, as names: from, to, when, how.
    // Reading order (row, then position): the chips may wrap.
    final at = [
      for (final c in ['Chennai', 'Madurai', 'Tomorrow', 'Train']) tester.getTopLeft(find.widgetWithText(TagChip, c)),
    ];
    for (var i = 1; i < at.length; i++) {
      expect(
        at[i].dy > at[i - 1].dy || (at[i].dy == at[i - 1].dy && at[i].dx > at[i - 1].dx),
        isTrue,
        reason: 'chip $i',
      );
    }
    expect(find.text('Rain chance at the origin is 15%.'), findsOneWidget);
    expect(find.text('Best window: 09:00–11:00'), findsOneWidget);
    expect(find.textContaining('Awareness only.'), findsOneWidget);
    expect(find.text('The reasons are shown in English.'), findsNothing);

    await tester.ensureVisible(find.text('Start over'));
    await tester.pump();
    await tester.tap(find.text('Start over'));
    await tester.pump();
    expect(find.text('Try asking'), findsOneWidget);
  });

  testWidgets('in another language the page says the reasons are English', (tester) async {
    await _pumpPage(tester, [advisoryReply('travel')], lang: 'hi');
    await tester.tap(find.text('कल ट्रेन से चेन्नई से मदुरै'));
    await tester.pump();
    expect(find.text('कारण अंग्रेज़ी में दिखाए गए हैं।'), findsOneWidget);
  });

  for (final (persona, sowing) in [('farmer', true), ('general', false), ('aviation', false)]) {
    testWidgets('the drawer: Travel advice for everyone, Sowing advice ${sowing ? '' : 'not '}for $persona', (
      tester,
    ) async {
      await tester.pumpWidget(
        WeatherGptApp(
          auth: await guestAuth(),
          prefsStore: MemoryPrefsStore({'persona': persona}),
          citiesFetcher: () async => null,
          responseCache: MemoryResponseCache(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.byTooltip('Menu'));
      await tester.pump(const Duration(milliseconds: 500));
      final drawer = find.byType(Drawer);
      expect(find.descendant(of: drawer, matching: find.text('Travel advice')), findsOneWidget);
      expect(find.descendant(of: drawer, matching: find.text('Sowing advice')), sowing ? findsOneWidget : findsNothing);
      await tester.pumpWidget(const SizedBox());
    });
  }

  testWidgets('the drawer opens Travel advice', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      WeatherGptApp(
        auth: await guestAuth(),
        prefsStore: MemoryPrefsStore(),
        citiesFetcher: () async => null,
        responseCache: MemoryResponseCache(),
      ),
    );
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.byTooltip('Menu'));
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    final tile = find.descendant(of: find.byType(Drawer), matching: find.text('Travel advice'));
    await tester.ensureVisible(tile);
    await tester.pump();
    await tester.tap(tile);
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 100)); // the drawer closes, the page slides in
    }
    expect(find.byType(AdvisoryPage), findsOneWidget);
    expect(find.byType(BottomNav), findsNothing); // a page on top
    await tester.pumpWidget(const SizedBox());
  });
}
