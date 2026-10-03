// Errors that carry a value (the server URL, an HTTP status, a reason) are
// shown in the app language: each client's message is a ui_strings.json key
// with `{name}` placeholders, and the value travels in `args`. Before, the
// value was baked into the English, so no table entry matched it.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:weathergpt/api_client.dart';
import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/aviation_client.dart';
import 'package:weathergpt/components/common.dart';
import 'package:weathergpt/config.dart';
import 'package:weathergpt/facts_client.dart';
import 'package:weathergpt/google_auth.dart';
import 'package:weathergpt/history_client.dart';
import 'package:weathergpt/i18n.dart';
import 'package:weathergpt/intelligence_client.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';
import 'package:weathergpt/ui_strings.dart';
import 'package:weathergpt/voice_client.dart';
import 'package:weathergpt/warnings_client.dart';

const _langs = ['hi', 'ta', 'te', 'mr'];

/// [call] with every HTTP request answered by [status] (or failing to
/// connect when [status] is null); returns the (message, args) it throws.
Future<(String, Map<String, Object?>)> _failure(Future<Object?> Function() call, int? status) async {
  final client = MockClient((_) async {
    if (status == null) throw http.ClientException('connection refused');
    return http.Response('{}', status);
  });
  try {
    await http.runWithClient(call, () => client);
  } on AskError catch (e) {
    return (e.message, e.args);
  } on FactsError catch (e) {
    return (e.message, e.args);
  } on WarningsError catch (e) {
    return (e.message, e.args);
  } on AviationError catch (e) {
    return (e.message, e.args);
  } on HistoryError catch (e) {
    return (e.message, e.args);
  } on IntelligenceError catch (e) {
    return (e.message, e.args);
  }
  fail('expected an error for HTTP $status');
}

/// [message] is in every language's table, and its values survive.
void _translated(String message, Map<String, Object?> args) {
  for (final lang in _langs) {
    expect(kUiStrings[lang]?[message], isNotNull, reason: '$lang has no entry for "$message"');
    final shown = trIn(lang, message, args);
    expect(shown, isNot(contains('{')), reason: '$lang: a placeholder was left in "$shown"');
    args.forEach((k, v) {
      if (message.contains('{$k}')) expect(shown, contains('$v'), reason: '$lang: "$shown" lost $v');
    });
  }
}

void main() {
  final calls = <String, Future<Object?> Function()>{
    'ask': () => askWeather(text: 'will it rain', city: 'chennai'),
    'facts': () => fetchFacts(city: 'chennai'),
    'warnings': () => fetchWarnings(city: 'chennai'),
    'aviation': () => fetchAviation('chennai'),
    'history': () => fetchHistory('token'),
    'best-window': () => fetchBestWindow(city: 'chennai', day: 'today'),
  };

  for (final MapEntry(key: name, value: call) in calls.entries) {
    test('$name: no connection, HTTP 500 and HTTP 404 all translate, values kept', () async {
      final (offline, offlineArgs) = await _failure(call, null);
      expect(fillPlaceholders(offline, offlineArgs), contains(kApiBaseUrl));
      _translated(offline, offlineArgs);

      final (http500, http500Args) = await _failure(call, 500);
      expect(fillPlaceholders(http500, http500Args), contains('HTTP 500'));
      _translated(http500, http500Args);

      final (http404, http404Args) = await _failure(call, 404);
      _translated(http404, http404Args);
    });
  }

  test("best-window's 422 translates", () async {
    final (message, args) = await _failure(calls['best-window']!, 422);
    _translated(message, args);
  });

  test('the timeout messages translate', () {
    for (final seconds in [kAskTimeout.inSeconds, kFactsTimeout.inSeconds]) {
      _translated('No answer within {seconds}s — the weather service timed out.', {'seconds': seconds});
    }
    _translated('No answer within {seconds}s — the warnings service timed out.', {
      'seconds': kWarningsTimeout.inSeconds,
    });
  });

  test('the voice notice for an HTTP error translates', () async {
    String? notice;
    var args = const <String, Object?>{};
    await http.runWithClient(
      () => transcribeAudio(
        audioBase64: 'AAAA',
        lang: 'hi',
        onNotice: (m, [a = const {}]) {
          notice = m;
          args = a;
        },
      ),
      () => MockClient((_) async => http.Response('{}', 502)),
    );
    expect(fillPlaceholders(notice!, args), 'The voice service replied HTTP 502.');
    _translated(notice!, args);
  });

  test('sign-in: an unexplained HTTP failure and a Google failure translate', () async {
    final auth = AuthClient(client: MockClient((_) async => http.Response('{}', 500)));
    try {
      await auth.signIn(email: 'a@b.co', password: 'secret12');
      fail('expected AuthError');
    } on AuthError catch (e) {
      expect(e.toString(), 'Sign-in failed (HTTP 500). Please try again.');
      _translated(e.message, e.args);
    }

    try {
      codeFromRedirect(
        Uri.parse('com.weathergpt.weathergpt://login-callback?error=server_error&error_description=Boom'),
      );
      fail('expected AuthError');
    } on AuthError catch (e) {
      expect(e.toString(), 'Google sign-in failed: Boom');
      _translated(e.message, e.args);
    }
  });

  test('the airport label translates', () {
    final named = AviationData(
      station: 'VOMM',
      stationName: 'Chennai',
      status: 'live',
      metar: null,
      taf: null,
      disclaimer: '',
    );
    expect(named.where, 'Chennai airport (VOMM)');
    expect(trIn('hi', named.whereKey, named.whereArgs), 'Chennai हवाई अड्डा (VOMM)');
    final bare = AviationData(
      station: 'VECC',
      stationName: null,
      status: 'live',
      metar: null,
      taf: null,
      disclaimer: '',
    );
    expect(bare.where, 'Station VECC');
    _translated(bare.whereKey, bare.whereArgs);
  });

  testWidgets('an ErrorPanel shows the message in the app language, URL included', (tester) async {
    final prefs = UiPrefs()..lang = 'ta';
    await tester.pumpWidget(
      UiPrefsScope(
        prefs: prefs,
        child: MaterialApp(
          theme: buildAppTheme(personaThemeFor(prefs.persona)),
          home: const Scaffold(
            body: ErrorPanel(
              icon: Icons.wifi_off,
              title: 'Forecast unavailable',
              message: "Couldn't reach the weather service at {url}. Is the orchestrator running?",
              messageArgs: {'url': 'https://example.test'},
            ),
          ),
        ),
      ),
    );
    expect(
      find.text('https://example.test இல் உள்ள வானிலை சேவையை அணுக முடியவில்லை. ஆர்கெஸ்ட்ரேட்டர் இயங்குகிறதா?'),
      findsOneWidget,
    );
  });
}
