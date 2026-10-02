// The signed-in account, app-wide. main.dart shows the landing page while
// [AuthStatus.signedOut] and the app shell once signed in or browsing as a
// guest; the drawer's Profile page reads the user and signs out through here.
//
// Guest mode is local only (the Supabase project has anonymous sign-ins off):
// the full app, no account, no profile. The choice is remembered like a
// session, and signing in from guest mode replaces it.
//
// The session is kept in the platform's secure store (Android Keystore,
// iOS Keychain) so a user stays signed in across restarts; on launch an
// expired access token is swapped for a fresh one with the refresh token, and
// a refresh the server rejects signs the user out. It is never written to a
// plain file and stays out of device backups (SEC-N19, plan.md F11): the
// Keychain item is this-device-only, and android/app/src/main's manifest
// turns off backup and device transfer.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

import '../auth_client.dart';
import '../google_auth.dart';

enum AuthStatus { restoring, signedOut, guest, signedIn }

/// Where the session is kept between launches.
abstract class SessionStorage {
  Future<Map<String, dynamic>?> read();
  Future<void> write(Map<String, dynamic> session);
  Future<void> clear();
}

class SecureSessionStorage implements SessionStorage {
  static const _key = 'auth_session';

  final FlutterSecureStorage _store;

  /// The app support directory, where builds before SEC-N19 kept the session
  /// as plaintext `auth_session.json`; tests point it at a temp directory.
  final Future<Directory> Function() _legacyDir;

  SecureSessionStorage({FlutterSecureStorage? store, Future<Directory> Function()? legacyDir})
    : _store =
          store ??
          const FlutterSecureStorage(
            // Readable after the first unlock (a background token refresh
            // works), never restored onto another device.
            iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
          ),
      _legacyDir = legacyDir ?? getApplicationSupportDirectory;

  @override
  Future<Map<String, dynamic>?> read() async {
    var json = await _store.read(key: _key);
    // One-time move of a session an older build left in a plain file: into
    // the secure store, then the file is deleted.
    final legacy = File('${(await _legacyDir()).path}/auth_session.json');
    if (await legacy.exists()) {
      if (json == null) {
        try {
          json = await legacy.readAsString();
          jsonDecode(json);
          await _store.write(key: _key, value: json);
        } catch (_) {
          json = null; // unreadable — start signed out
        }
      }
      await legacy.delete();
    }
    return json == null ? null : jsonDecode(json) as Map<String, dynamic>;
  }

  @override
  Future<void> write(Map<String, dynamic> session) => _store.write(key: _key, value: jsonEncode(session));

  @override
  Future<void> clear() => _store.delete(key: _key);
}

/// Keeps nothing — widget tests and previews.
class MemorySessionStorage implements SessionStorage {
  Map<String, dynamic>? _session;
  MemorySessionStorage([this._session]);

  @override
  Future<Map<String, dynamic>?> read() async => _session;
  @override
  Future<void> write(Map<String, dynamic> session) async => _session = session;
  @override
  Future<void> clear() async => _session = null;
}

class AuthStore extends ChangeNotifier {
  final AuthClient client;
  final SessionStorage storage;

  /// Builds the Google sign-in flow; tests swap in one without the browser.
  final GoogleSignInFlow Function(AuthClient client) googleFlow;

  AuthStore({AuthClient? client, SessionStorage? storage, GoogleSignInFlow Function(AuthClient)? googleFlow})
    : client = client ?? AuthClient(),
      storage = storage ?? SecureSessionStorage(),
      googleFlow = googleFlow ?? GoogleSignInFlow.platform;

  AuthStatus _status = AuthStatus.restoring;
  AuthSession? _session;

  AuthStatus get status => _status;
  AuthSession? get session => _session;
  AuthUser? get user => _session?.user;
  bool get isGuest => _status == AuthStatus.guest;

  /// What the session storage holds while browsing as a guest.
  static const _guestMarker = {'guest': true};

  /// Loads a saved session, refreshing it if it has expired.
  Future<void> restore() async {
    AuthSession? saved;
    try {
      final json = await storage.read();
      if (json != null && json['guest'] == true) {
        _status = AuthStatus.guest;
        notifyListeners();
        return;
      }
      if (json != null) saved = AuthSession.fromJson(json);
    } catch (_) {
      saved = null; // unreadable or no storage — start signed out
    }
    if (saved != null && saved.isStale) {
      try {
        saved = await client.refresh(saved.refreshToken);
        await _save(saved);
      } on AuthError catch (e) {
        // Offline: keep the user signed in with what we have; the next
        // launch retries. Rejected by the server: sign out.
        if (e.code != null) {
          saved = null;
          await _forget();
        }
      }
    }
    _session = saved;
    _status = saved == null ? AuthStatus.signedOut : AuthStatus.signedIn;
    notifyListeners();
  }

  Future<void> signIn(String email, String password) async {
    final session = await client.signIn(email: email.trim(), password: password);
    await _adopt(session);
  }

  /// Signs in (or signs up — Supabase creates the account on first use) with
  /// Google in the system browser. Throws [AuthError]; code
  /// `google_cancelled` means the user backed out.
  Future<void> signInWithGoogle() async {
    final session = await googleFlow(client).signIn();
    await _adopt(session);
  }

  /// Creates the account. Returns the result so the caller can show the
  /// "check your inbox" step when confirmation is required.
  Future<SignUpResult> signUp({
    required String email,
    required String password,
    required String fullName,
    required String phone,
    required String occupation,
  }) async {
    final result = await client.signUp(
      email: email.trim(),
      password: password,
      fullName: fullName.trim(),
      phone: phone.trim(),
      occupation: occupation.trim(),
    );
    if (result.session != null) await _adopt(result.session!);
    return result;
  }

  Future<void> resendConfirmation(String email) => client.resendConfirmation(email.trim());

  /// Saves the edited profile to the account and to the saved session.
  Future<void> updateProfile({required String fullName, required String phone, required String occupation}) async {
    final session = await _freshSession();
    final user = await client.updateProfile(
      session.accessToken,
      fullName: fullName.trim(),
      phone: phone.trim(),
      occupation: occupation.trim(),
    );
    await _adopt(session.withUser(user));
  }

  Future<void> sendPasswordReset(String email) => client.sendPasswordReset(email.trim());

  /// Checks the emailed reset code, sets the new password, and signs in.
  Future<void> resetPassword({required String email, required String code, required String newPassword}) async {
    final session = await client.verifyRecoveryCode(email: email.trim(), code: code.trim());
    final user = await client.updatePassword(session.accessToken, newPassword);
    await _adopt(session.withUser(user));
  }

  /// The current session, refreshed first if its access token has expired.
  Future<AuthSession> _freshSession() async {
    final session = _session;
    if (session == null) throw AuthError('You are signed out. Sign in again to continue.');
    if (!session.isStale) return session;
    final fresh = await client.refresh(session.refreshToken);
    await _adopt(fresh);
    return fresh;
  }

  /// Use the app without an account.
  Future<void> continueAsGuest() async {
    _session = null;
    _status = AuthStatus.guest;
    notifyListeners();
    try {
      await storage.write(_guestMarker);
    } catch (_) {
      // Not remembered — the landing page shows again next launch.
    }
  }

  /// Signs out, or leaves guest mode; either way back to the landing page.
  Future<void> signOut() async {
    final session = _session;
    _session = null;
    _status = AuthStatus.signedOut;
    notifyListeners();
    await _forget();
    if (session != null) {
      try {
        await client.signOut(session.accessToken);
      } on AuthError {
        // Already expired or offline — the local session is gone either way.
      }
    }
  }

  Future<void> _adopt(AuthSession session) async {
    _session = session;
    _status = AuthStatus.signedIn;
    notifyListeners();
    await _save(session);
  }

  Future<void> _save(AuthSession session) async {
    try {
      await storage.write(session.toJson());
    } catch (_) {
      // Not persisted — the user just signs in again next launch.
    }
  }

  Future<void> _forget() async {
    try {
      await storage.clear();
    } catch (_) {}
  }

  /// Subscribes the caller to changes.
  static AuthStore of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AuthScope>()!.notifier!;

  /// Like [of], but null outside an AuthScope.
  static AuthStore? maybeOf(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AuthScope>()?.notifier;

  /// For event handlers — no rebuild subscription.
  static AuthStore read(BuildContext context) => context.getInheritedWidgetOfExactType<AuthScope>()!.notifier!;
}

class AuthScope extends InheritedNotifier<AuthStore> {
  const AuthScope({super.key, required AuthStore store, required super.child}) : super(notifier: store);
}
