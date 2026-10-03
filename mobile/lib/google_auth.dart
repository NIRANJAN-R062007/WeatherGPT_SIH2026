// "Continue with Google" — Supabase's OAuth flow with PKCE, in the system
// browser (Google refuses sign-in inside embedded web views). The app opens
// /auth/v1/authorize, Supabase hands over to Google, and Google's answer comes
// back through Supabase to [kGoogleRedirect], a custom-scheme link the app
// catches (AndroidManifest.xml intent filter, Info.plist CFBundleURLTypes).
// The `code` on that link plus the PKCE verifier buys a session from
// /auth/v1/token?grant_type=pkce.
//
// [kGoogleRedirect] must be listed under Authentication → URL Configuration →
// Redirect URLs in the Supabase dashboard, or Supabase falls back to the Site
// URL and the app never hears back.
//
// The verifier lives only in memory: if Android kills the app while the
// browser is open, the returning link is ignored and the user taps again.
import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:app_links/app_links.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter/widgets.dart';
import 'package:url_launcher/url_launcher.dart';

import 'auth_client.dart';

const String kGoogleRedirect = 'com.weathergpt.weathergpt://login-callback';

/// How long after the app comes back to the foreground the redirect may take
/// to arrive before the sign-in counts as abandoned (browser closed or back
/// pressed).
const Duration kGoogleReturnGrace = Duration(seconds: 3);

/// A random PKCE code verifier: 32 bytes, base64url without padding (43
/// characters, inside RFC 7636's 43–128).
String pkceVerifier([Random? random]) {
  final r = random ?? Random.secure();
  return base64UrlEncode(List<int>.generate(32, (_) => r.nextInt(256))).replaceAll('=', '');
}

/// The S256 challenge for [verifier]: base64url(sha256(verifier)), no padding.
String pkceChallenge(String verifier) =>
    base64UrlEncode(sha256.convert(ascii.encode(verifier)).bytes).replaceAll('=', '');

/// Whether [uri] is the sign-in redirect (and not some other link).
bool isGoogleRedirect(Uri uri) {
  final expected = Uri.parse(kGoogleRedirect);
  return uri.scheme == expected.scheme && uri.host == expected.host;
}

/// The `code` on the redirect. Throws [AuthError] with Supabase's or Google's
/// reason when the redirect carries an error instead (in the query or the
/// fragment).
String codeFromRedirect(Uri uri) {
  final params = {...Uri.splitQueryString(uri.fragment), ...uri.queryParameters};
  final code = params['code'];
  if (code != null && code.isNotEmpty) return code;
  final error = params['error'];
  if (error == 'access_denied') {
    throw AuthError('Google sign-in was cancelled.', code: 'google_cancelled');
  }
  final reason = params['error_description'] ?? error;
  throw AuthError(
    reason == null ? 'Google sign-in failed. Please try again.' : 'Google sign-in failed: {reason}',
    code: error ?? 'google_failed',
    args: {'reason': reason},
  );
}

class GoogleSignInFlow {
  final AuthClient client;

  /// Opens the authorize URL; false when nothing could open it.
  final Future<bool> Function(Uri url) openBrowser;

  /// Incoming app links.
  final Stream<Uri> links;

  /// Fires each time the app comes back to the foreground after being hidden
  /// (not on a dialog such as the browser chooser closing).
  final Stream<void> resumed;

  /// How long to wait for the redirect after [resumed] fires.
  final Duration returnGrace;

  GoogleSignInFlow({
    required this.client,
    required this.openBrowser,
    required this.links,
    required this.resumed,
    this.returnGrace = kGoogleReturnGrace,
  });

  /// The real thing: system browser, app_links, app lifecycle.
  factory GoogleSignInFlow.platform(AuthClient client) {
    final resumed = StreamController<void>.broadcast();
    AppLifecycleListener? listener;
    var hidden = false;
    resumed.onListen = () => listener = AppLifecycleListener(
      onHide: () => hidden = true,
      onResume: () {
        if (!hidden) return;
        hidden = false;
        resumed.add(null);
      },
    );
    resumed.onCancel = () => listener?.dispose();
    return GoogleSignInFlow(
      client: client,
      openBrowser: (url) => launchUrl(url, mode: LaunchMode.externalApplication),
      links: AppLinks().uriLinkStream,
      resumed: resumed.stream,
    );
  }

  /// Runs the whole sign-in and returns the new session. Throws [AuthError];
  /// code `google_cancelled` means the user backed out, which needs no
  /// message.
  Future<AuthSession> signIn() async {
    final verifier = pkceVerifier();
    final url = client.googleAuthorizeUrl(redirectTo: kGoogleRedirect, codeChallenge: pkceChallenge(verifier));

    final redirect = Completer<Uri>();
    Timer? abandon;
    // app_links replays the link the app was launched with on listen; a
    // stale redirect from an earlier attempt must not be taken for this one.
    var browserOpened = false;
    final linkSub = links.where(isGoogleRedirect).listen((uri) {
      if (!browserOpened) return;
      abandon?.cancel();
      if (!redirect.isCompleted) redirect.complete(uri);
    });
    final resumeSub = resumed.listen((_) {
      abandon?.cancel();
      abandon = Timer(returnGrace, () {
        if (!redirect.isCompleted) {
          redirect.completeError(AuthError('Google sign-in was cancelled.', code: 'google_cancelled'));
        }
      });
    });
    try {
      final opened = await openBrowser(url).catchError((Object _) => false);
      if (!opened) throw AuthError("Couldn't open the browser for Google sign-in.");
      browserOpened = true;
      final code = codeFromRedirect(await redirect.future);
      return await client.exchangeCode(code: code, codeVerifier: verifier);
    } finally {
      abandon?.cancel();
      await linkSub.cancel();
      await resumeSub.cancel();
    }
  }
}
