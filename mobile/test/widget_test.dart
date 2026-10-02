import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/components/app_shell.dart';
import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/components/forms.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/lang_store.dart';
import 'package:weathergpt/pages/onboarding_pages.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';

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

const _user = {
  'id': 'u1',
  'email': 'chelsea@example.com',
  'created_at': '2026-09-29T10:00:00Z',
  'user_metadata': {'full_name': 'Chelsea Joseph', 'phone': '9876543210', 'occupation': 'Farmer'},
};

Map<String, dynamic> _sessionJson() => {
  'access_token': 'access',
  'refresh_token': 'refresh',
  'expires_at': DateTime.now().add(const Duration(hours: 1)).millisecondsSinceEpoch ~/ 1000,
  'user': _user,
};

final _noNetwork = MockClient((_) async => http.Response('{}', 500));

/// A store already signed in (session in memory, no network).
Future<AuthStore> _signedIn() async {
  final store = AuthStore(
    storage: MemorySessionStorage(_sessionJson()),
    client: AuthClient(client: _noNetwork),
  );
  await store.restore();
  return store;
}

/// A signed-out store whose Supabase calls are answered by [handler].
Future<AuthStore> _signedOut(Future<http.Response> Function(http.Request) handler) async {
  final store = AuthStore(
    storage: MemorySessionStorage(),
    client: AuthClient(client: MockClient(handler)),
  );
  await store.restore();
  return store;
}

/// A phone-sized screen (Pixel 7), reset after the test.
void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

/// Scrolls [finder] into view, then taps it.
Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
  await _settle(tester);
}

/// Lets file IO started by the app finish: real time passes, then the
/// test's fake-async zone runs the callbacks.
Future<void> _realIo(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 20)));
    await tester.pump();
  }
}

/// Languages page → Continue (English stays selected) → Welcome + log in.
Future<void> _continueToLogin(WidgetTester tester) async {
  await _tapVisible(tester, find.text('Continue'));
  await _settle(tester);
}

Future<void> _enter(WidgetTester tester, String label, String text) async {
  await tester.enterText(find.widgetWithText(TextFormField, label), text);
}

void main() {
  testWidgets('boots to Home: city pill, quick questions and the now card', (tester) async {
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);

    expect(find.text('Chennai, Tamil Nadu'), findsOneWidget);
    expect(find.text('Quick Actions'), findsOneWidget);
    // /facts got a 400 -> the hero shows the error panel, not stale numbers.
    expect(find.text('Live conditions unavailable'), findsOneWidget);
  });

  testWidgets('drawer mirrors web Sidebar nav, without History', (tester) async {
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);
    await tester.tap(find.byTooltip('Menu'));
    await _settle(tester);

    final drawer = find.byType(Drawer);
    for (final label in ['Home', 'Chat & Evidence', 'Forecast', 'Alerts & Warnings', 'Settings']) {
      expect(
        find.descendant(of: drawer, matching: find.text(label)),
        findsOneWidget,
        reason: label,
      );
    }
    expect(find.descendant(of: drawer, matching: find.text('History')), findsNothing);
    expect(find.descendant(of: drawer, matching: find.text('Profile')), findsOneWidget);
    expect(find.descendant(of: drawer, matching: find.text('chelsea@example.com')), findsOneWidget);
  });

  testWidgets('every page renders', (tester) async {
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
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
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);

    await _tab(tester, 'Chat');
    expect(find.text('Suggested Questions'), findsOneWidget);
    await _tab(tester, 'Alerts');
    expect(find.text('Active Alerts'), findsOneWidget);
    await _tab(tester, 'More');
    expect(find.text('Change Persona'), findsOneWidget);
    await _tab(tester, 'Home');
    expect(find.text('Quick Actions'), findsOneWidget);
  });

  testWidgets('a Home quick question is asked in Chat', (tester) async {
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);

    await tester.ensureVisible(find.text('Will it rain today?'));
    await _settle(tester);
    await tester.tap(find.text('Will it rain today?'));
    await _settle(tester);

    expect(find.text('Will it rain today in Chennai?'), findsOneWidget); // the user bubble
    expect(find.text('Suggested Questions'), findsNothing); // transcript mode
  });

  testWidgets('Android back: closes the drawer first, then returns Home', (tester) async {
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
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
    expect(find.text('Quick Actions'), findsOneWidget);
  });

  testWidgets('city picker updates the shared city', (tester) async {
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
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
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);
    await _tab(tester, 'More');

    await tester.tap(find.text('Language'));
    await _settle(tester);
    await tester.tap(find.text('हिन्दी'));
    await _settle(tester);
    expect(find.text('हिन्दी'), findsOneWidget); // the row's value, sheet closed
    expect(find.text('English'), findsNothing);
    // The app's own text follows the language too.
    expect(find.text('भाषा'), findsOneWidget);

    await tester.tap(find.text('इकाइयाँ')); // Units
    await _settle(tester);
    await tester.tap(find.text('फ़ारेनहाइट (°F)'));
    await _settle(tester);
    expect(find.text('फ़ारेनहाइट (°F)'), findsOneWidget);

    await tester.tap(find.text('पर्सोना बदलें')); // Change Persona
    await _settle(tester);
    expect(find.text('अपना पर्सोना चुनें'), findsOneWidget);
    await tester.ensureVisible(find.text('किसान'));
    await _settle(tester);
    await tester.tap(find.text('किसान')); // Farmer
    await _settle(tester);
    await _settle(tester); // the picker lingers a beat so the re-theme shows
    expect(find.text('अपना पर्सोना चुनें'), findsNothing);
    expect(find.text('किसान'), findsOneWidget);
    expect(find.text('खेती, फ़सलें और मौसम योजना।'), findsOneWidget);
  });

  testWidgets('the persona is the app-wide theme and survives page switches', (tester) async {
    PersonaTheme active() => PersonaTheme.of(tester.element(find.byType(BottomNav)));

    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
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

  testWidgets('Appearance > Dark switches every persona to its dark palette', (tester) async {
    PersonaTheme active() => PersonaTheme.of(tester.element(find.byType(BottomNav)));

    _phone(tester);
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);
    await _tab(tester, 'More');
    await _tapVisible(tester, find.text('Appearance'));
    await tester.tap(find.text('Dark Mode'));
    await _settle(tester);
    expect(active().isDark, isTrue);
    expect(active().primary, personaThemesDark['general']!.primary);
    expect(Theme.of(tester.element(find.byType(BottomNav))).brightness, Brightness.dark);

    await _tapVisible(tester, find.text('Change Persona'));
    await _tapVisible(tester, find.text('Aviation'));
    await _settle(tester);
    for (final tab in ['Home', 'Chat', 'Forecast', 'Alerts', 'More']) {
      await _tab(tester, tab);
      expect(active().primary, personaThemesDark['aviation']!.primary, reason: tab);
      expect(active().isDark, isTrue, reason: tab);
    }
  });

  testWidgets('signed out: languages first, then welcome + log in; Sign Up opens the account form', (tester) async {
    _phone(tester);
    await tester.pumpWidget(WeatherGptApp(auth: await _signedOut((_) async => http.Response('{}', 500))));
    await _settle(tester);
    expect(find.text('Languages'), findsOneWidget);
    for (final label in ['English', 'हिन्दी', 'தமிழ்', 'తెలుగు', 'मराठी']) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
    expect(find.text('Quick Actions'), findsNothing);

    await _continueToLogin(tester);
    expect(find.text('Welcome to'), findsOneWidget);
    for (final label in [
      'Email or phone number',
      'Password',
      'Forgot password?',
      'Log In',
      'or',
      'Continue with Google',
      "Don't have an account?",
      'Sign Up',
      'Sign in as Guest',
    ]) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
    await _tapVisible(tester, find.text('Log In'));
    expect(find.text('Enter your email or phone number.'), findsOneWidget);
    expect(find.text('Enter your password.'), findsOneWidget);
    await _enter(tester, 'Email or phone number', '98765 43210');
    await tester.pump();
    expect(find.text("Phone sign-in isn't available yet — please use your email."), findsOneWidget);

    await _tapVisible(tester, find.text('Sign Up'));
    expect(find.text('Create your account'), findsOneWidget);
    for (final label in ['Full name', 'Email', 'Phone number', 'Occupation', 'Password', 'Confirm password']) {
      expect(find.widgetWithText(TextFormField, label), findsOneWidget, reason: label);
    }
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Create account'));
    expect(find.text('Enter your name.'), findsOneWidget);
    expect(find.text('Enter your email.'), findsOneWidget);
    expect(find.text('Enter your phone number.'), findsOneWidget);
  });

  testWidgets('creating an account ends on the confirm-your-email step', (tester) async {
    _phone(tester);
    Map<String, dynamic>? sent;
    final auth = await _signedOut((req) async {
      expect(req.url.path, '/auth/v1/signup');
      expect(req.url.queryParameters['redirect_to'], endsWith('/email-confirmed.html?from=mobile'));
      sent = jsonDecode(req.body) as Map<String, dynamic>;
      return http.Response(jsonEncode(_user), 200); // no session: confirmation required
    });
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    await _continueToLogin(tester);
    await _tapVisible(tester, find.text('Sign Up'));

    await _enter(tester, 'Full name', 'Chelsea Joseph');
    await _enter(tester, 'Email', 'chelsea@example.com');
    await _enter(tester, 'Phone number', '98765 43210');
    await _enter(tester, 'Occupation', 'Farmer');
    await _enter(tester, 'Password', 'correct-horse');
    await _enter(tester, 'Confirm password', 'correct-horse');
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Create account'));

    expect(sent!['email'], 'chelsea@example.com');
    expect(sent!['data'], {'full_name': 'Chelsea Joseph', 'phone': '9876543210', 'occupation': 'Farmer'});
    expect(find.text('Confirm your email'), findsOneWidget);
    expect(auth.status, AuthStatus.signedOut);
  });

  testWidgets('a wrong password shows the error; the right one opens the app', (tester) async {
    _phone(tester);
    final auth = await _signedOut((req) async {
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      if (body['password'] != 'right-password') {
        return http.Response(
          jsonEncode({'code': 400, 'error_code': 'invalid_credentials', 'msg': 'Invalid login credentials'}),
          400,
        );
      }
      return http.Response(jsonEncode(_sessionJson()), 200);
    });
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    await _continueToLogin(tester);

    await _enter(tester, 'Email or phone number', 'chelsea@example.com');
    await _enter(tester, 'Password', 'wrong');
    await _tapVisible(tester, find.text('Log In'));
    expect(find.text('Wrong email or password.'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).at(1), 'right-password');
    await _tapVisible(tester, find.text('Log In'));
    expect(auth.status, AuthStatus.signedIn);
    expect(find.text('Quick Actions'), findsOneWidget);
  });

  testWidgets('drawer Profile shows the account details and signs out', (tester) async {
    _phone(tester);
    final auth = await _signedIn();
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    await _openDrawerAndGo(tester, 'Profile');

    expect(find.text('Chelsea Joseph'), findsOneWidget);
    expect(find.text('chelsea@example.com'), findsWidgets);
    expect(find.text('98765 43210'), findsOneWidget);
    expect(find.text('Farmer'), findsWidgets);
    expect(find.text('29 Sep 2026'), findsOneWidget);

    await _tapVisible(tester, find.text('Sign out'));
    await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('Sign out')));
    await _settle(tester);
    await _settle(tester);
    expect(auth.status, AuthStatus.signedOut);
    expect(find.text('Languages'), findsOneWidget);
  });

  testWidgets('Sign in as Guest opens the app; Profile offers sign-in; exit returns to Languages', (tester) async {
    _phone(tester);
    final storage = MemorySessionStorage();
    final auth = AuthStore(storage: storage, client: AuthClient(client: _noNetwork));
    await auth.restore();
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);

    await _continueToLogin(tester);
    await _tapVisible(tester, find.text('Sign in as Guest'));
    expect(auth.status, AuthStatus.guest);
    expect(await storage.read(), {'guest': true});
    expect(find.text('Quick Actions'), findsOneWidget);

    await _openDrawerAndGo(tester, 'Profile');
    expect(find.text('Guest'), findsOneWidget);
    expect(find.text("You're using WeatherGPT without an account."), findsOneWidget);
    expect(find.widgetWithText(GradientButton, 'Create account'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);

    await _tapVisible(tester, find.text('Exit guest mode'));
    await _settle(tester);
    expect(auth.status, AuthStatus.signedOut);
    expect(await storage.read(), isNull);
    expect(find.text('Languages'), findsOneWidget);
  });

  testWidgets('Edit profile saves name, phone and occupation to the account', (tester) async {
    _phone(tester);
    Map<String, dynamic>? sent;
    String? bearer;
    final storage = MemorySessionStorage(_sessionJson());
    final auth = AuthStore(
      storage: storage,
      client: AuthClient(
        client: MockClient((req) async {
          expect(req.method, 'PUT');
          expect(req.url.path, '/auth/v1/user');
          bearer = req.headers['Authorization'];
          sent = jsonDecode(req.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              ..._user,
              'user_metadata': sent!['data'],
            }),
            200,
          );
        }),
      ),
    );
    await auth.restore();
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    await _openDrawerAndGo(tester, 'Profile');

    await _tapVisible(tester, find.text('Edit profile'));
    expect(find.widgetWithText(TextFormField, 'Chelsea Joseph'), findsOneWidget); // prefilled
    await _enter(tester, 'Full name', 'Chelsea J');
    await _enter(tester, 'Phone number', '+91 91234 56789');
    await _enter(tester, 'Occupation', 'Fisherman');
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Save changes'));

    expect(bearer, 'Bearer access');
    expect(sent!['data'], {'full_name': 'Chelsea J', 'phone': '+919123456789', 'occupation': 'Fisherman'});
    expect(find.text('Edit profile'), findsOneWidget); // back on Profile (the button)
    expect(find.text('Chelsea J'), findsOneWidget);
    expect(find.text('+91 91234 56789'), findsOneWidget);
    expect(auth.user!.occupation, 'Fisherman');
    expect(((await storage.read())!['user'] as Map)['user_metadata']['occupation'], 'Fisherman');
  });

  testWidgets('Edit profile validates and shows a server error', (tester) async {
    _phone(tester);
    final auth = AuthStore(
      storage: MemorySessionStorage(_sessionJson()),
      client: AuthClient(
        client: MockClient(
          (_) async => http.Response(jsonEncode({'error_code': 'unexpected_failure', 'msg': 'Database error'}), 500),
        ),
      ),
    );
    await auth.restore();
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    await _openDrawerAndGo(tester, 'Profile');
    await _tapVisible(tester, find.text('Edit profile'));

    await _enter(tester, 'Full name', '  ');
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Save changes'));
    expect(find.text('Enter your name.'), findsOneWidget);

    await _enter(tester, 'Full name', 'Chelsea');
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Save changes'));
    expect(find.text('Database error'), findsOneWidget);
    expect(auth.user!.fullName, 'Chelsea Joseph'); // unchanged
  });

  testWidgets('Forgot password: code + new password signs in', (tester) async {
    _phone(tester);
    final calls = <String>[];
    final auth = await _signedOut((req) async {
      calls.add('${req.method} ${req.url.path}');
      final body = req.body.isEmpty ? const {} : jsonDecode(req.body) as Map<String, dynamic>;
      switch (req.url.path) {
        case '/auth/v1/recover':
          expect(body, {'email': 'chelsea@example.com'});
          return http.Response('{}', 200);
        case '/auth/v1/verify':
          if (body['token'] != '123456') {
            return http.Response(
              jsonEncode({'error_code': 'otp_expired', 'msg': 'Token has expired or is invalid'}),
              403,
            );
          }
          expect(body['type'], 'recovery');
          return http.Response(jsonEncode(_sessionJson()), 200);
        case '/auth/v1/user':
          expect(body, {'password': 'new-password-1'});
          expect(req.headers['Authorization'], 'Bearer access');
          return http.Response(jsonEncode(_user), 200);
      }
      return http.Response('{}', 404);
    });
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    await _continueToLogin(tester);
    await _enter(tester, 'Email or phone number', 'chelsea@example.com');
    await _tapVisible(tester, find.text('Forgot password?'));

    expect(find.text('Reset your password'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'chelsea@example.com'), findsOneWidget); // carried over
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Send reset code'));
    expect(find.text('We sent a reset code to chelsea@example.com.'), findsOneWidget);

    await _enter(tester, 'Reset code', '999999');
    await _enter(tester, 'New password', 'new-password-1');
    await _enter(tester, 'Confirm new password', 'new-password-1');
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Set new password'));
    expect(find.text('That code is wrong or has expired. Request a new one.'), findsOneWidget);
    expect(auth.status, AuthStatus.signedOut);

    await _enter(tester, 'Reset code', '123456');
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'Set new password'));
    expect(auth.status, AuthStatus.signedIn);
    expect(find.text('Quick Actions'), findsOneWidget);
    expect(calls, [
      'POST /auth/v1/recover',
      'POST /auth/v1/verify',
      'POST /auth/v1/verify',
      'PUT /auth/v1/user',
    ]);
  });

  testWidgets('the language picked first translates the welcome page and becomes the app language', (
    tester,
  ) async {
    _phone(tester);
    await tester.pumpWidget(WeatherGptApp(auth: await _signedOut((_) async => http.Response('{}', 500))));
    await _settle(tester);

    await _tapVisible(tester, find.text('हिन्दी'));
    expect(find.text('भाषाएँ'), findsOneWidget); // the page follows the pick
    await _tapVisible(tester, find.text('आगे बढ़ें'));
    await _settle(tester);

    for (final label in [
      'आपका स्वागत है!',
      'ईमेल या फ़ोन नंबर',
      'पासवर्ड',
      'पासवर्ड भूल गए?',
      'लॉग इन करें',
      'या',
      'Google के साथ जारी रखें',
      'खाता नहीं है?',
      'साइन अप करें',
      'अतिथि के रूप में साइन इन करें',
    ]) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
    expect(find.text('Log In'), findsNothing);
    expect(UiPrefs.read(tester.element(find.byType(WelcomeLoginPage))).lang, 'hi');

    // Back to Languages: Tamil this time.
    await tester.tap(find.byTooltip('वापस'));
    await _settle(tester);
    await _tapVisible(tester, find.text('தமிழ்'));
    await _tapVisible(tester, find.text('தொடரவும்'));
    await _settle(tester);
    expect(find.text('வரவேற்கிறோம்!'), findsOneWidget);
    expect(find.text('விருந்தினராக உள்நுழைக'), findsOneWidget);
  });

  testWidgets('the language picked before sign-in carries into sign-up and the whole app', (tester) async {
    _phone(tester);
    await tester.pumpWidget(WeatherGptApp(auth: await _signedOut((_) async => http.Response('{}', 500))));
    await _settle(tester);
    await _tapVisible(tester, find.text('हिन्दी'));
    await _tapVisible(tester, find.text('आगे बढ़ें'));
    await _settle(tester);

    // Sign up: page, field labels and validation in Hindi.
    await _tapVisible(tester, find.text('साइन अप करें'));
    expect(find.text('अपना खाता बनाएँ'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'पूरा नाम'), findsOneWidget);
    await _tapVisible(tester, find.widgetWithText(GradientButton, 'खाता बनाएँ'));
    expect(find.text('अपना नाम दर्ज करें।'), findsOneWidget);
    await tester.tap(find.byTooltip('वापस'));
    await _settle(tester);

    // Guest: the app itself in Hindi.
    await _tapVisible(tester, find.text('अतिथि के रूप में साइन इन करें'));
    expect(find.text('त्वरित कार्य'), findsOneWidget); // Quick Actions
    expect(find.text('चेन्नई, तमिलनाडु'), findsOneWidget); // the city pill
    for (final tab in ['होम', 'चैट', 'पूर्वानुमान', 'अलर्ट', 'और']) {
      expect(find.descendant(of: find.byType(BottomNav), matching: find.text(tab)), findsOneWidget, reason: tab);
    }
    await _tab(tester, 'और');
    expect(find.text('सेटिंग्स'), findsWidgets);
    expect(find.text('भाषा'), findsOneWidget);
  });

  testWidgets('the language is remembered across launches', (tester) async {
    _phone(tester);
    final dir = await tester.runAsync(() => Directory.systemTemp.createTemp('lang'));
    addTearDown(() => dir!.deleteSync(recursive: true));
    final store = LangStore(dir: () async => dir!);

    // First launch: pick Telugu before signing in.
    await tester.pumpWidget(
      WeatherGptApp(auth: await _signedOut((_) async => http.Response('{}', 500)), langStore: store),
    );
    await _settle(tester);
    await _tapVisible(tester, find.text('తెలుగు'));
    await _tapVisible(tester, find.text('కొనసాగించండి'));
    await _realIo(tester);
    expect(await tester.runAsync(store.read), 'te');

    // Next launch, already signed in: the app opens in Telugu.
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn(), langStore: store));
    await _realIo(tester);
    await _settle(tester);
    expect(find.text('త్వరిత చర్యలు'), findsOneWidget); // Quick Actions
  });

  testWidgets('onboarding has its own light and dark designs, with the saved logo cuts', (tester) async {
    _phone(tester);
    await tester.pumpWidget(WeatherGptApp(auth: await _signedOut((_) async => http.Response('{}', 500))));
    await _settle(tester);

    Brightness brightness() => Theme.of(tester.element(find.byType(LanguagePage))).brightness;
    String logo() => ((tester.widget<Image>(find.byType(Image).first).image) as AssetImage).assetName;
    expect(brightness(), Brightness.light);
    expect(logo(), 'assets/branding/weathergpt-onboarding-light.png');

    await tester.tap(find.byTooltip('Dark mode'));
    await _settle(tester);
    expect(brightness(), Brightness.dark);
    expect(logo(), 'assets/branding/weathergpt-onboarding-dark.png');

    await _continueToLogin(tester);
    expect(Theme.of(tester.element(find.byType(WelcomeLoginPage))).brightness, Brightness.dark);
    expect(find.text('Sign in as Guest'), findsOneWidget);
  });

  testWidgets('guest mode is remembered across launches', (tester) async {
    final auth = AuthStore(storage: MemorySessionStorage({'guest': true}), client: AuthClient(client: _noNetwork));
    await auth.restore();
    expect(auth.status, AuthStatus.guest);
    await tester.pumpWidget(WeatherGptApp(auth: auth));
    await _settle(tester);
    expect(find.text('Quick Actions'), findsOneWidget);
  });
}
