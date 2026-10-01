import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/google_auth.dart';
import 'package:weathergpt/state/auth_store.dart';

const _session = {
  'access_token': 'at',
  'refresh_token': 'rt',
  'expires_in': 3600,
  'user': {'id': 'g1', 'email': 'someone@gmail.com', 'user_metadata': {'full_name': 'Some One'}},
};

/// A flow whose browser and lifecycle are scripted by the test.
class _Harness {
  final links = StreamController<Uri>.broadcast();
  final resumed = StreamController<void>.broadcast();
  final requests = <http.Request>[];
  Uri? opened;
  bool browserOpens = true;
  Duration grace = kGoogleReturnGrace;

  late final AuthClient client = AuthClient(
    baseUrl: 'https://example.supabase.co',
    anonKey: 'anon',
    client: MockClient((req) async {
      requests.add(req);
      return http.Response(jsonEncode(_session), 200);
    }),
  );

  GoogleSignInFlow flow(AuthClient c) => GoogleSignInFlow(
    client: c,
    openBrowser: (url) async {
      opened = url;
      return browserOpens;
    },
    links: links.stream,
    resumed: resumed.stream,
    returnGrace: grace,
  );
}

void main() {
  test('PKCE challenge matches the RFC 7636 appendix B example', () {
    expect(
      pkceChallenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'),
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    );
  });

  test('PKCE verifier is 43 unpadded base64url characters', () {
    final v = pkceVerifier();
    expect(v, hasLength(43));
    expect(RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(v), isTrue);
    expect(pkceVerifier(), isNot(v));
  });

  test('authorize URL carries the provider, redirect and S256 challenge', () {
    final url = AuthClient(baseUrl: 'https://example.supabase.co', anonKey: 'anon')
        .googleAuthorizeUrl(redirectTo: kGoogleRedirect, codeChallenge: 'abc');
    expect(url.path, '/auth/v1/authorize');
    expect(url.queryParameters, {
      'provider': 'google',
      'redirect_to': kGoogleRedirect,
      'code_challenge': 'abc',
      'code_challenge_method': 's256',
    });
  });

  group('redirect parsing', () {
    test('takes the code from the query', () {
      expect(codeFromRedirect(Uri.parse('$kGoogleRedirect?code=xyz')), 'xyz');
    });

    test('a denied consent counts as cancelled', () {
      expect(
        () => codeFromRedirect(Uri.parse('$kGoogleRedirect#error=access_denied&error_description=nope')),
        throwsA(isA<AuthError>().having((e) => e.code, 'code', 'google_cancelled')),
      );
    });

    test('other errors keep their description', () {
      expect(
        () => codeFromRedirect(Uri.parse('$kGoogleRedirect?error=server_error&error_description=Boom')),
        throwsA(isA<AuthError>().having((e) => e.message, 'message', contains('Boom'))),
      );
    });

    test('only the sign-in link counts as the redirect', () {
      expect(isGoogleRedirect(Uri.parse('$kGoogleRedirect?code=1')), isTrue);
      expect(isGoogleRedirect(Uri.parse('com.weathergpt.weathergpt://other?code=1')), isFalse);
      expect(isGoogleRedirect(Uri.parse('https://login-callback/?code=1')), isFalse);
    });
  });

  test('sign-in exchanges the redirect code with the matching verifier and signs in', () async {
    final h = _Harness();
    final store = AuthStore(client: h.client, storage: MemorySessionStorage(), googleFlow: h.flow);

    final done = store.signInWithGoogle();
    await pumpEventQueue();
    expect(h.opened?.queryParameters['provider'], 'google');

    h.links.add(Uri.parse('com.weathergpt.weathergpt://other?code=ignored'));
    h.resumed.add(null);
    h.links.add(Uri.parse('$kGoogleRedirect?code=the-code'));
    await done;

    expect(store.status, AuthStatus.signedIn);
    expect(store.user?.email, 'someone@gmail.com');
    final req = h.requests.single;
    expect(req.url.path, '/auth/v1/token');
    expect(req.url.queryParameters['grant_type'], 'pkce');
    final body = jsonDecode(req.body) as Map<String, dynamic>;
    expect(body['auth_code'], 'the-code');
    expect(pkceChallenge(body['code_verifier'] as String), h.opened?.queryParameters['code_challenge']);
  });

  test('coming back without the redirect cancels the sign-in', () async {
    final h = _Harness()..grace = const Duration(milliseconds: 20);
    final store = AuthStore(client: h.client, storage: MemorySessionStorage(), googleFlow: h.flow);
    final done = store.signInWithGoogle();
    await pumpEventQueue();

    h.resumed.add(null);
    await expectLater(done, throwsA(isA<AuthError>().having((e) => e.code, 'code', 'google_cancelled')));
    expect(store.status, isNot(AuthStatus.signedIn));
    expect(h.requests, isEmpty);
  });

  test('a browser that will not open is an error, not a hang', () async {
    final h = _Harness()..browserOpens = false;
    final store = AuthStore(client: h.client, storage: MemorySessionStorage(), googleFlow: h.flow);
    await expectLater(store.signInWithGoogle(), throwsA(isA<AuthError>()));
    expect(h.requests, isEmpty);
  });
}
