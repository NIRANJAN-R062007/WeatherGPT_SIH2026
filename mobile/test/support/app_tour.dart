// A tour of every page of the app against the fake backend, for checks that
// apply everywhere (large text, accessibility guidelines). [at] runs at each
// stop: a page's top and its end, with its expandable parts open.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:weathergpt/advisory_client.dart';
import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/components/common.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/pages/advisory_page.dart';
import 'package:weathergpt/pages/auth_page.dart';
import 'package:weathergpt/pages/aviation_page.dart';
import 'package:weathergpt/pages/best_window_page.dart';
import 'package:weathergpt/pages/edit_profile_page.dart';
import 'package:weathergpt/pages/history_page.dart';
import 'package:weathergpt/pages/onboarding_pages.dart';
import 'package:weathergpt/pages/persona_page.dart';
import 'package:weathergpt/pages/profile_page.dart';
import 'package:weathergpt/pages/reset_password_page.dart';
import 'package:weathergpt/response_cache.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/prefs_store.dart';
import 'package:weathergpt/ui_strings.dart';

import 'fake_backend.dart';

/// A stop on the tour: [where] names the page and the spot.
typedef TourStop = Future<void> Function(String where);

/// The app's fonts, from the asset bundle's font manifest, so text measures
/// as it does on a phone (the test font draws every glyph a full em wide).
Future<void> loadAppFonts() async {
  final manifest = jsonDecode(await rootBundle.loadString('FontManifest.json')) as List;
  for (final family in manifest.cast<Map<String, dynamic>>()) {
    final loader = FontLoader(family['family'] as String);
    for (final font in (family['fonts'] as List).cast<Map<String, dynamic>>()) {
      loader.addFont(rootBundle.load(font['asset'] as String));
    }
    await loader.load();
  }
}

/// [en] as the app shows it in [lang].
String shown(String lang, String en) => kUiStrings[lang]?[en] ?? en;

Future<void> settle(WidgetTester tester) async {
  // Home's hero gradient drifts forever, so pumpAndSettle would time out.
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

/// [at] the page's top, then drags it to its end (so every lazily built row
/// is laid out once) and [at] the end.
Future<void> scrollThrough(WidgetTester tester, String where, TourStop? at) async {
  await at?.call('$where (top)');
  final centre = tester.getCenter(find.byType(Navigator).first);
  for (var i = 0; i < 14; i++) {
    await tester.dragFrom(centre, const Offset(0, -350));
    await tester.pump(const Duration(milliseconds: 50));
  }
  await settle(tester);
  await at?.call('$where (end)');
}

/// Scrolls the current page until [finder] is on screen, [up] or down.
Future<void> reveal(WidgetTester tester, Finder finder, {bool up = false}) async {
  await tester.dragUntilVisible(finder, find.byType(ListView).first, Offset(0, up ? 300 : -300));
  await tester.pump();
}

/// A context under the app's navigator.
BuildContext _ctx(WidgetTester tester) => tester.element(find.byType(Scaffold).first);

/// Opens a page or sheet on top with [open], tours it, and closes it.
Future<void> _visit(WidgetTester tester, String where, void Function(BuildContext) open, TourStop? at) async {
  open(_ctx(tester));
  await settle(tester);
  expect(Navigator.of(_ctx(tester)).canPop(), isTrue, reason: '$where opened');
  await scrollThrough(tester, where, at);
  Navigator.of(_ctx(tester)).pop();
  await settle(tester);
}

/// Opens an advisory page, asks [example], scrolls to the answer's
/// [verdict], and tours the page.
Future<void> _visitAdvisory(
  WidgetTester tester,
  String lang,
  AdvisoryKind kind, {
  required String example,
  required String verdict,
  TourStop? at,
}) async {
  final where = kind == AdvisoryKind.travel ? 'Travel advice' : 'Sowing advice';
  openAdvisory(_ctx(tester), kind);
  await settle(tester);
  await at?.call('$where (examples)');
  await reveal(tester, find.text(shown(lang, example)));
  await tester.tap(find.text(shown(lang, example)));
  await settle(tester);
  await reveal(tester, find.text(shown(lang, verdict)));
  await scrollThrough(tester, '$where (answer)', at);
  Navigator.of(_ctx(tester)).pop();
  await settle(tester);
}

void Function(BuildContext) _push(Widget page) =>
    (context) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));

const _user = {
  'id': 'u1',
  'email': 'someone@example.com',
  'created_at': '2026-09-29T10:00:00Z',
  'user_metadata': {'full_name': 'Test User', 'phone': '9876543210', 'occupation': 'Farmer'},
};

/// Every signed-in page, as a guest with the Aviation persona's extras
/// unless [persona] says otherwise.
Future<void> tourApp(
  WidgetTester tester,
  String lang, {
  String persona = 'aviation',
  String appearance = 'light',
  TourStop? at,
}) async {
  final backend = FakeBackend();
  await http.runWithClient(() async {
    await tester.pumpWidget(
      WeatherGptApp(
        auth: await guestAuth(),
        prefsStore: MemoryPrefsStore({'lang': lang, 'persona': persona, 'appearance': appearance}),
        citiesFetcher: () async => null,
        responseCache: MemoryResponseCache(),
      ),
    );
    await settle(tester);
    await scrollThrough(tester, 'Home', at);

    Future<void> tab(IconData icon) async {
      await tester.tap(find.descendant(of: find.byType(BottomNav), matching: find.byIcon(icon)));
      await settle(tester);
    }

    await tab(Icons.chat_bubble_outline); // Chat: ask, then the answer
    await tester.enterText(find.byType(TextField).last, 'weather in Chennai');
    await tester.pump(); // Send enables once there's text
    await tester.ensureVisible(find.byTooltip(shown(lang, 'Send')).last);
    await tester.pump();
    await tester.tap(find.byTooltip(shown(lang, 'Send')).last);
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }
    expect(find.textContaining('31°C in Chennai'), findsWidgets, reason: 'the answer');
    // A place two towns share: pick one of the offered places.
    await tester.enterText(find.byType(TextField).last, 'weather in Puttur');
    await tester.pump();
    await tester.ensureVisible(find.byTooltip(shown(lang, 'Send')).last);
    await tester.pump();
    await tester.tap(find.byTooltip(shown(lang, 'Send')).last);
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }
    final place = find.text('Puttūr, Karnataka · Dakshina Kannada');
    expect(place, findsOneWidget, reason: 'the places to pick from');
    await scrollThrough(tester, 'Chat (which place?)', at);
    await tester.ensureVisible(place);
    await tester.pump();
    await tester.tap(place);
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }
    expect(find.textContaining('31°C in Puttūr'), findsWidgets, reason: 'the picked place answered');
    await scrollThrough(tester, 'Chat', at);

    await tab(Icons.light_mode_outlined); // Forecast: an open day, then hourly
    await tester.ensureVisible(find.byIcon(Icons.expand_more).first);
    await tester.pump();
    await tester.tap(find.byIcon(Icons.expand_more).first);
    await settle(tester);
    expect(find.text(shown(lang, 'Rainfall')), findsOneWidget, reason: 'an open day');
    await scrollThrough(tester, 'Forecast days', at);
    await reveal(tester, find.text(shown(lang, 'Hourly')), up: true);
    await tester.tap(find.text(shown(lang, 'Hourly')));
    await settle(tester);
    expect(find.text(shown(lang, 'Now')), findsOneWidget, reason: 'the hourly strip');
    await scrollThrough(tester, 'Forecast hourly', at);

    await tab(Icons.notifications_none); // Alerts, with the warning's details open
    await tester.ensureVisible(find.text(shown(lang, 'View details')));
    await tester.pump();
    await tester.tap(find.text(shown(lang, 'View details')));
    await settle(tester);
    expect(find.text(shown(lang, 'Hide details')), findsOneWidget, reason: 'the warning details');
    await scrollThrough(tester, 'Alerts', at);

    await tab(Icons.more_horiz);
    await scrollThrough(tester, 'Settings', at);

    await tester.tap(find.byTooltip(shown(lang, 'Menu')));
    await settle(tester);
    await at?.call('Drawer');
    await tester.tapAt(const Offset(350, 400)); // outside it, to close it
    await settle(tester);

    await _visit(tester, 'City picker', (c) => showCityPicker(c), at);
    await _visit(tester, 'Persona', openPersonaPicker, at);
    await _visit(tester, 'Profile', openProfile, at);
    await _visit(tester, 'Edit profile', _push(EditProfilePage(user: AuthUser.fromJson(_user))), at);
    await _visit(tester, 'Airport weather', openAviation, at);
    await _visit(tester, 'Best time', openBestWindow, at);
    await _visit(tester, 'History', (c) => openHistory(c, onAskAgain: (_) {}), at);
    await _visitAdvisory(
      tester,
      lang,
      AdvisoryKind.travel,
      example: 'Chennai to Madurai tomorrow by train',
      verdict: 'Go with caution',
      at: at,
    );
    await _visitAdvisory(
      tester,
      lang,
      AdvisoryKind.sowing,
      example: 'When should I sow groundnut in Madurai?',
      verdict: 'Not available',
      at: at,
    );
  }, () => backend.client);
  await tester.pumpWidget(const SizedBox());
}

/// The signed-out pages: languages, welcome + log in, sign in, sign up and
/// the password reset.
Future<void> tourSignedOut(WidgetTester tester, String lang, {String appearance = 'light', TourStop? at}) async {
  final auth = AuthStore(
    storage: MemorySessionStorage(),
    client: AuthClient(client: FakeBackend().client),
  );
  await auth.restore();
  await tester.pumpWidget(
    WeatherGptApp(
      auth: auth,
      prefsStore: MemoryPrefsStore({'lang': lang, 'appearance': appearance}),
      citiesFetcher: () async => null,
    ),
  );
  await settle(tester);
  expect(find.byType(LanguagePage), findsOneWidget);
  await scrollThrough(tester, 'Languages', at);
  await _visit(tester, 'Welcome', _push(const WelcomeLoginPage()), at);
  await _visit(tester, 'Sign in', _push(const AuthPage()), at);
  await _visit(tester, 'Sign up', _push(const AuthPage(initialMode: AuthMode.signUp)), at);
  await _visit(tester, 'Reset password', _push(const ResetPasswordPage()), at);
  await tester.pumpWidget(const SizedBox());
}
