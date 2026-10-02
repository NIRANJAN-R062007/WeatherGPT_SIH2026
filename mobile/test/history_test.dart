// Query history: the /history client (bearer token, error kinds, row
// parsing), AuthStore.accessToken (guest, fresh, refreshed, failed refresh),
// the History page's states (list, filters, search, empty, errors, clear,
// "Ask again", guest), the drawer item, and Chat sending the token on /ask so
// signed-in questions are recorded. Row shapes match public.history
// (services/orchestrator/sql/supabase_schema.sql) as GET /history returns it.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/history_client.dart';
import 'package:weathergpt/main.dart';
import 'package:weathergpt/pages/history_page.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/auth_store.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';

const _user = {
  'id': 'u1',
  'email': 'chelsea@example.com',
  'created_at': '2026-09-29T10:00:00Z',
  'user_metadata': {'full_name': 'Chelsea Joseph', 'phone': '9876543210', 'occupation': 'Farmer'},
};

Map<String, dynamic> _session({String access = 'access', Duration expiresIn = const Duration(hours: 1)}) => {
  'access_token': access,
  'refresh_token': 'refresh',
  'expires_at': DateTime.now().add(expiresIn).millisecondsSinceEpoch ~/ 1000,
  'user': _user,
};

final _noNetwork = MockClient((_) async => http.Response('{}', 500));

Future<AuthStore> _signedIn({http.Client? client}) async {
  final store = AuthStore(
    storage: MemorySessionStorage(_session()),
    client: AuthClient(client: client ?? _noNetwork),
  );
  await store.restore();
  return store;
}

Future<AuthStore> _guest() async {
  final store = AuthStore(
    storage: MemorySessionStorage({'guest': true}),
    client: AuthClient(client: _noNetwork),
  );
  await store.restore();
  return store;
}

Map<String, dynamic> _row(
  String id,
  String query, {
  String? intent = 'will_it_rain',
  String? city = 'chennai',
  String? lang = 'en',
  String? response = 'No rain is expected in Chennai today.',
  String createdAt = '2026-10-01T08:19:00Z',
}) => {
  'id': id,
  'user_id': 'u1',
  'query': query,
  'intent': intent,
  'city': city,
  'lang': lang,
  'response': response,
  'created_at': createdAt,
};

final _rows = [
  _row('r1', 'will it rain today in Chennai'),
  _row('r2', 'any warnings for Mumbai', intent: 'warnings', city: 'mumbai', response: null),
  _row(
    'r3',
    'दिल्ली में तापमान',
    intent: 'current_temperature',
    city: 'delhi',
    lang: 'hi',
    response: 'दिल्ली में 31°C',
  ),
];

List<HistoryRow> _parsed() => [for (final r in _rows) HistoryRow.fromJson(r)!];

/// The page on its own, themed, with the shared prefs and [auth].
Widget _harness(AuthStore auth, Widget page) {
  final p = UiPrefs();
  return AuthScope(
    store: auth,
    child: UiPrefsScope(
      prefs: p,
      child: MaterialApp(theme: buildAppTheme(personaThemeFor(p.persona)), home: page),
    ),
  );
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 3200);
  tester.view.devicePixelRatio = 2.625;
  addTearDown(tester.view.reset);
}

Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
  await _settle(tester);
}

void main() {
  group('history client', () {
    test('GET /history sends the bearer token and parses rows, dropping unusable ones', () async {
      late http.Request seen;
      final rows = await http.runWithClient(
        () => fetchHistory('tok'),
        () => MockClient((req) async {
          seen = req;
          return http.Response(
            jsonEncode({
              'history': [
                ..._rows,
                {'id': 'bad'}, // no query
                'not a row',
              ],
            }),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
      );
      expect(seen.method, 'GET');
      expect(seen.url.path, '/history');
      expect(seen.headers['Authorization'], 'Bearer tok');
      expect(rows.map((r) => r.id), ['r1', 'r2', 'r3']);
      expect(rows[1].response, isNull);
      expect(rows[2].query, 'दिल्ली में तापमान');
      expect(rows[2].lang, 'hi');
    });

    Future<HistoryError> failure(Future<void> Function() call, http.Response res) async {
      try {
        await http.runWithClient(call, () => MockClient((_) async => res));
      } on HistoryError catch (e) {
        return e;
      }
      fail('expected a HistoryError');
    }

    test('error kinds: auth, not configured, other HTTP, bad JSON, wrong shape', () async {
      expect((await failure(() => fetchHistory('t'), http.Response('', 401))).kind, HistoryErrorKind.auth);
      expect((await failure(() => fetchHistory('t'), http.Response('', 403))).kind, HistoryErrorKind.auth);
      final unconfigured = await failure(() => fetchHistory('t'), http.Response('', 503));
      expect(unconfigured.kind, HistoryErrorKind.unavailable);
      expect(unconfigured.message, 'History is not set up on this server.');
      final other = await failure(() => fetchHistory('t'), http.Response('', 502));
      expect(other.kind, HistoryErrorKind.http);
      expect(other.message, contains('HTTP 502'));
      expect((await failure(() => fetchHistory('t'), http.Response('<html>', 200))).kind, HistoryErrorKind.malformed);
      expect(
        (await failure(() => fetchHistory('t'), http.Response('{"rows": []}', 200))).kind,
        HistoryErrorKind.malformed,
      );
    });

    test('DELETE /history sends the token; an expired session says "clear"', () async {
      late http.Request seen;
      await http.runWithClient(
        () => clearHistory('tok'),
        () => MockClient((req) async {
          seen = req;
          return http.Response('{"cleared": true}', 200);
        }),
      );
      expect(seen.method, 'DELETE');
      expect(seen.headers['Authorization'], 'Bearer tok');

      final e = await failure(() => clearHistory('t'), http.Response('', 401));
      expect(e.kind, HistoryErrorKind.auth);
      expect(e.message, 'Your session has expired. Sign in again to clear your history.');
    });

    test('filters group by intent', () {
      final rows = _parsed();
      expect(rows.where((r) => matchesFilter(r, HistoryFilter.all)), hasLength(3));
      expect(rows.where((r) => matchesFilter(r, HistoryFilter.alerts)).map((r) => r.id), ['r2']);
      expect(rows.where((r) => matchesFilter(r, HistoryFilter.rain)).map((r) => r.id), ['r1']);
    });
  });

  group('AuthStore.accessToken', () {
    test('null for a guest', () async {
      expect(await (await _guest()).accessToken(), isNull);
    });

    test('the current token while it is fresh, with no network call', () async {
      var calls = 0;
      final store = await _signedIn(
        client: MockClient((_) async {
          calls++;
          return http.Response('{}', 500);
        }),
      );
      expect(await store.accessToken(), 'access');
      expect(calls, 0);
    });

    test('an expired token is refreshed first', () async {
      final store = AuthStore(
        storage: MemorySessionStorage(),
        client: AuthClient(
          client: MockClient((req) async {
            final refresh = req.url.query.contains('grant_type=refresh_token');
            // The sign-in hands back an already-expired session.
            final body = refresh ? _session(access: 'fresh') : _session(expiresIn: const Duration(minutes: -5));
            return http.Response(jsonEncode(body), 200);
          }),
        ),
      );
      await store.restore();
      await store.signIn('chelsea@example.com', 'pw');
      expect(store.session!.isStale, isTrue);
      expect(await store.accessToken(), 'fresh');
      expect(store.session!.accessToken, 'fresh');
    });

    test('a failed refresh gives null instead of throwing', () async {
      final store = AuthStore(
        storage: MemorySessionStorage(),
        client: AuthClient(
          client: MockClient((req) async {
            if (req.url.query.contains('grant_type=refresh_token')) {
              return http.Response('{"error_code": "refresh_token_not_found", "msg": "Invalid Refresh Token"}', 400);
            }
            return http.Response(jsonEncode(_session(expiresIn: const Duration(minutes: -5))), 200);
          }),
        ),
      );
      await store.restore();
      await store.signIn('chelsea@example.com', 'pw');
      expect(await store.accessToken(), isNull);
    });
  });

  group('History page', () {
    testWidgets('lists past questions with chips, the answer shown, and a count', (tester) async {
      _phone(tester);
      final tokens = <String>[];
      final auth = await _signedIn();
      await tester.pumpWidget(
        _harness(
          auth,
          HistoryPage(
            fetcher: (token) async {
              tokens.add(token);
              return _parsed();
            },
            onAskAgain: (_) {},
          ),
        ),
      );
      await _settle(tester);

      expect(tokens, ['access']);
      expect(find.text('Query history'), findsOneWidget);
      expect(find.text('3 questions'), findsOneWidget);
      expect(find.text('“will it rain today in Chennai”'), findsOneWidget);
      expect(find.text('No rain is expected in Chennai today.'), findsOneWidget);
      // r2 got no grounded answer: said so, never left blank.
      expect(find.text('No answer was recorded for this question.'), findsOneWidget);
      expect(find.text('Chennai'), findsOneWidget);
      expect(find.text('WILL IT RAIN'), findsOneWidget);
      expect(find.text('HI'), findsOneWidget); // only the non-English row
      expect(find.text('1 Oct, 13:49 IST'), findsNWidgets(3));
      expect(find.text('Ask again'), findsNWidgets(3));
    });

    testWidgets('filter chips and search narrow the list', (tester) async {
      _phone(tester);
      await tester.pumpWidget(_harness(await _signedIn(), HistoryPage(fetcher: (_) async => _parsed())));
      await _settle(tester);

      await _tapVisible(tester, find.text('Alerts'));
      expect(find.text('1 question'), findsOneWidget);
      expect(find.text('“any warnings for Mumbai”'), findsOneWidget);
      expect(find.text('“will it rain today in Chennai”'), findsNothing);

      await _tapVisible(tester, find.text('Rain'));
      expect(find.text('“will it rain today in Chennai”'), findsOneWidget);

      await _tapVisible(tester, find.text('All queries'));
      await tester.enterText(find.byType(TextFormField), 'delhi');
      await _settle(tester);
      expect(find.text('1 question'), findsOneWidget);
      expect(find.text('“दिल्ली में तापमान”'), findsOneWidget); // matched by its city

      await tester.enterText(find.byType(TextFormField), 'no such thing');
      await _settle(tester);
      expect(find.text('Nothing matches that filter.'), findsOneWidget);
    });

    testWidgets('"Ask again" closes the page and hands the question over', (tester) async {
      _phone(tester);
      final asked = <String>[];
      final auth = await _signedIn();
      await tester.pumpWidget(
        _harness(
          auth,
          Builder(
            builder: (context) => TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => HistoryPage(fetcher: (_) async => _parsed(), onAskAgain: asked.add),
                ),
              ),
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await _settle(tester);
      expect(find.text('Query history'), findsOneWidget);

      await _tapVisible(tester, find.text('Ask again').first);
      expect(asked, ['will it rain today in Chennai']);
      expect(find.text('Query history'), findsNothing);
      expect(find.text('open'), findsOneWidget);
    });

    testWidgets('no questions yet invites a first one', (tester) async {
      _phone(tester);
      await tester.pumpWidget(_harness(await _signedIn(), HistoryPage(fetcher: (_) async => [])));
      await _settle(tester);
      expect(find.text('No questions yet'), findsOneWidget);
      expect(find.text('Ask something in Chat and it will show up here.'), findsOneWidget);
      expect(find.text('Clear history'), findsNothing);
    });

    testWidgets('an unreachable server shows the error and retries', (tester) async {
      _phone(tester);
      var calls = 0;
      await tester.pumpWidget(
        _harness(
          await _signedIn(),
          HistoryPage(
            fetcher: (_) async {
              calls++;
              if (calls == 1) throw HistoryError(HistoryErrorKind.unavailable, 'History is not set up on this server.');
              return _parsed();
            },
          ),
        ),
      );
      await _settle(tester);
      expect(find.text('History unavailable'), findsOneWidget);
      expect(find.text('History is not set up on this server.'), findsOneWidget);

      await _tapVisible(tester, find.text('Try again'));
      expect(calls, 2);
      expect(find.text('3 questions'), findsOneWidget);
    });

    testWidgets('a rejected session asks to sign in again, with no retry', (tester) async {
      _phone(tester);
      await tester.pumpWidget(
        _harness(
          await _signedIn(),
          HistoryPage(
            fetcher: (_) async => throw HistoryError(
              HistoryErrorKind.auth,
              'Your session has expired. Sign in again to see your history.',
            ),
          ),
        ),
      );
      await _settle(tester);
      expect(find.text('Sign in again'), findsOneWidget);
      expect(find.text('Sign out and sign in again'), findsOneWidget);
      expect(find.text('Try again'), findsNothing);
    });

    testWidgets('Clear history asks first, then erases with the token', (tester) async {
      _phone(tester);
      final cleared = <String>[];
      await tester.pumpWidget(
        _harness(await _signedIn(), HistoryPage(fetcher: (_) async => _parsed(), clearer: (t) async => cleared.add(t))),
      );
      await _settle(tester);

      await _tapVisible(tester, find.text('Clear history'));
      expect(find.text('Clear your history?'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await _settle(tester);
      expect(cleared, isEmpty);
      expect(find.text('3 questions'), findsOneWidget);

      await _tapVisible(tester, find.text('Clear history'));
      await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('Clear history')));
      await _settle(tester);
      expect(cleared, ['access']);
      expect(find.text('No questions yet'), findsOneWidget);
    });

    testWidgets('a failed clear keeps the list and says why', (tester) async {
      _phone(tester);
      await tester.pumpWidget(
        _harness(
          await _signedIn(),
          HistoryPage(
            fetcher: (_) async => _parsed(),
            clearer: (_) async => throw HistoryError(HistoryErrorKind.http, 'The history service replied HTTP 502.'),
          ),
        ),
      );
      await _settle(tester);
      await _tapVisible(tester, find.text('Clear history'));
      await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('Clear history')));
      await _settle(tester);
      expect(find.text('The history service replied HTTP 502.'), findsOneWidget);
      expect(find.text('3 questions'), findsOneWidget);
    });

    testWidgets('a guest is invited to sign in, and nothing is fetched', (tester) async {
      _phone(tester);
      var calls = 0;
      await tester.pumpWidget(
        _harness(
          await _guest(),
          HistoryPage(
            fetcher: (_) async {
              calls++;
              return [];
            },
          ),
        ),
      );
      await _settle(tester);
      expect(calls, 0);
      expect(find.text('Your questions are saved to your account'), findsOneWidget);
      expect(find.text('Sign in to see your history'), findsOneWidget);
      expect(find.text('Create account'), findsOneWidget);
    });
  });

  testWidgets('the drawer opens History (no server: the error state)', (tester) async {
    _phone(tester);
    await tester.pumpWidget(WeatherGptApp(auth: await _signedIn()));
    await _settle(tester);

    await tester.tap(find.byTooltip('Menu'));
    await _settle(tester);
    await tester.tap(find.descendant(of: find.byType(Drawer), matching: find.text('History')));
    await _settle(tester);

    // flutter_test answers every real HTTP request with a 400.
    expect(find.text('Query history'), findsOneWidget);
    expect(find.text('History unavailable'), findsOneWidget);
    expect(find.textContaining('HTTP 400'), findsOneWidget);
    expect(find.byTooltip('Back'), findsOneWidget);
  });

  group('Chat sends the token on /ask', () {
    // A fallback answer: the smallest body /ask can give.
    final askBody = jsonEncode({'intent': 'unknown', 'message': 'I can only answer weather questions.'});

    Future<List<http.Request>> askFromChat(WidgetTester tester, AuthStore auth) async {
      final asks = <http.Request>[];
      final client = MockClient((req) async {
        if (req.url.path == '/ask') {
          asks.add(req);
          return http.Response(askBody, 200);
        }
        return http.Response('{}', 400);
      });
      await http.runWithClient(() async {
        await tester.pumpWidget(WeatherGptApp(auth: auth));
        await _settle(tester);
        await tester.tap(find.byTooltip('Menu'));
        await _settle(tester);
        await tester.tap(find.descendant(of: find.byType(Drawer), matching: find.text('Chat & Evidence')));
        await _settle(tester);
        await tester.enterText(find.byType(TextField).first, 'will it rain today');
        await tester.testTextInput.receiveAction(TextInputAction.send);
        await _settle(tester);
      }, () => client);
      return asks;
    }

    testWidgets('signed in: Authorization carries the access token', (tester) async {
      _phone(tester);
      final asks = await askFromChat(tester, await _signedIn());
      expect(asks, hasLength(1));
      expect(asks.single.url.queryParameters['text'], 'will it rain today');
      expect(asks.single.headers['Authorization'], 'Bearer access');
    });

    testWidgets('guest: no Authorization header, so nothing is recorded', (tester) async {
      _phone(tester);
      final asks = await askFromChat(tester, await _guest());
      expect(asks, hasLength(1));
      expect(asks.single.headers.containsKey('Authorization'), isFalse);
    });
  });
}
