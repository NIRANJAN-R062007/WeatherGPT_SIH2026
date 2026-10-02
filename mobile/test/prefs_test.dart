// Settings remembered across launches: the file-backed store (round trip,
// the older language-only file, an unreadable file), UiPrefs.applySaved
// (validation, settings changed this launch kept), and the app restoring and
// saving all five settings.
import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/pages/home_page.dart';
import 'package:weathergpt/pages/onboarding_pages.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/state/ui_prefs.dart';

const _farmer = {'lang': 'en', 'unit': 'fahrenheit', 'city': 'madurai', 'persona': 'farmer', 'appearance': 'dark'};

final _noNetwork = MockClient((_) async => http.Response('{}', 500));

Future<AuthStore> _guest() async {
  final store = AuthStore(
    storage: MemorySessionStorage({'guest': true}),
    client: AuthClient(client: _noNetwork),
  );
  await store.restore();
  return store;
}

Future<AuthStore> _signedOut() async {
  final store = AuthStore(
    storage: MemorySessionStorage(),
    client: AuthClient(client: _noNetwork),
  );
  await store.restore();
  return store;
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

UiPrefs _prefsOf(WidgetTester tester, Type page) => UiPrefs.read(tester.element(find.byType(page)));

/// A store whose read waits for [answer] — "the file is still being read".
class _SlowStore implements PrefsStore {
  final Completer<Map<String, String>?> answer = Completer();
  final List<Map<String, String>> writes = [];

  @override
  Future<Map<String, String>?> read() => answer.future;
  @override
  Future<void> write(Map<String, String> prefs) async => writes.add(prefs);
}

void main() {
  group('FilePrefsStore', () {
    late Directory dir;
    late FilePrefsStore store;
    setUp(() async {
      dir = await Directory.systemTemp.createTemp('prefs');
      store = FilePrefsStore(dir: () async => dir);
    });
    tearDown(() => dir.delete(recursive: true));

    test('nothing saved yet reads as null', () async {
      expect(await store.read(), isNull);
    });

    test('what is written is read back', () async {
      await store.write(_farmer);
      expect(await store.read(), _farmer);
      expect(File('${dir.path}/app_prefs.json').existsSync(), isTrue);
    });

    test("an older build's language file is read, then removed once settings are saved", () async {
      final legacy = File('${dir.path}/app_language')..writeAsStringSync('ta\n');
      expect(await store.read(), {'lang': 'ta'});

      await store.write({..._farmer, 'lang': 'ta'});
      expect(legacy.existsSync(), isFalse);
      expect((await store.read())!['lang'], 'ta');
    });

    test('an unreadable or wrong-shaped file reads as null, never throws', () async {
      final file = File('${dir.path}/app_prefs.json');
      file.writeAsStringSync('{not json');
      expect(await store.read(), isNull);
      file.writeAsStringSync('["a list"]');
      expect(await store.read(), isNull);
      file.writeAsStringSync('{"city": "delhi", "unit": 3}');
      expect(await store.read(), {'city': 'delhi'}); // the non-string value is dropped
    });
  });

  group('UiPrefs.applySaved', () {
    test('applies every known setting, with one notification', () {
      final prefs = UiPrefs();
      var notified = 0;
      prefs.addListener(() => notified++);
      prefs.applySaved({..._farmer, 'lang': 'ta'});
      expect(prefs.toSaved(), {..._farmer, 'lang': 'ta'});
      expect(prefs.unit, TempUnit.fahrenheit);
      expect(prefs.appearance, Appearance.dark);
      expect(notified, 1);
    });

    test('unknown values are skipped and keep their defaults', () {
      final prefs = UiPrefs()..applySaved({'lang': 'fr', 'unit': 'kelvin', 'persona': 'pirate', 'appearance': 'sepia'});
      expect(prefs.toSaved(), UiPrefs().toSaved());
    });

    test("a city the bundled list lacks waits for the server's list, and is kept meanwhile", () {
      final prefs = UiPrefs()..applySaved({'city': 'pune'});
      expect(prefs.city, 'chennai'); // nothing to answer for Pune yet
      expect(prefs.toSaved()['city'], 'pune'); // but not forgotten
    });

    test('settings in `keep` are left as they are', () {
      final prefs = UiPrefs()..city = 'delhi';
      prefs.applySaved(_farmer, keep: {'city'});
      expect(prefs.city, 'delhi');
      expect(prefs.persona, 'farmer');
    });

    test('nothing new, no notification', () {
      final prefs = UiPrefs();
      var notified = 0;
      prefs.addListener(() => notified++);
      prefs.applySaved(UiPrefs().toSaved());
      prefs.applySaved({});
      expect(notified, 0);
    });
  });

  group('the app', () {
    testWidgets('opens with the city, unit, persona and appearance from last time', (tester) async {
      await tester.pumpWidget(WeatherGptApp(auth: await _guest(), prefsStore: MemoryPrefsStore(Map.of(_farmer))));
      await _settle(tester);

      final prefs = _prefsOf(tester, HomePage);
      expect(prefs.toSaved(), _farmer);
      expect(find.text('Madurai, Tamil Nadu'), findsOneWidget);
      expect(Theme.of(tester.element(find.byType(HomePage))).brightness, Brightness.dark);
    });

    testWidgets('every change is saved', (tester) async {
      final store = MemoryPrefsStore();
      await tester.pumpWidget(WeatherGptApp(auth: await _guest(), prefsStore: store));
      await _settle(tester);
      expect(store.saved, UiPrefs().toSaved()); // the defaults, written once read

      final prefs = _prefsOf(tester, HomePage);
      prefs.city = 'hyderabad';
      prefs.persona = 'fisherman';
      prefs.unit = TempUnit.fahrenheit;
      prefs.appearance = Appearance.system;
      await _settle(tester);
      expect(store.saved, {
        'lang': 'en',
        'unit': 'fahrenheit',
        'city': 'hyderabad',
        'persona': 'fisherman',
        'appearance': 'system',
      });
    });

    testWidgets('a change made before the saved settings arrive wins, and nothing is written before', (tester) async {
      final store = _SlowStore();
      await tester.pumpWidget(WeatherGptApp(auth: await _signedOut(), prefsStore: store));
      await _settle(tester);

      // Still reading: the user picks Hindi on the Languages page.
      _prefsOf(tester, LanguagePage).lang = 'hi';
      await _settle(tester);
      expect(store.writes, isEmpty); // the saved settings can't be overwritten yet

      store.answer.complete(Map.of(_farmer));
      await _settle(tester);
      final prefs = _prefsOf(tester, LanguagePage);
      expect(prefs.lang, 'hi'); // kept
      expect(prefs.city, 'madurai'); // the rest restored
      expect(prefs.persona, 'farmer');
      expect(store.writes.last, {..._farmer, 'lang': 'hi'});
    });

    testWidgets('a store that fails to read starts from the defaults', (tester) async {
      final store = _SlowStore();
      await tester.pumpWidget(WeatherGptApp(auth: await _guest(), prefsStore: store));
      store.answer.complete(null);
      await _settle(tester);
      expect(_prefsOf(tester, HomePage).toSaved(), UiPrefs().toSaved());
    });
  });
}
