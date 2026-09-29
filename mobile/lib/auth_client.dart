// Email + password accounts on the team's Supabase project (config.dart), via
// Supabase Auth's REST API (GoTrue) — the same project prototype/frontend/
// auth.js signs in to with Google. The profile fields the app shows (name,
// phone, occupation) live in the account's user_metadata, so they follow the
// user to any device. The project requires email confirmation, so a fresh
// sign-up returns no session until the link in the confirmation mail is
// opened.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart' show StringCharacters;
import 'package:http/http.dart' as http;

import 'config.dart';

const Duration kAuthTimeout = Duration(seconds: 15);

class AuthError implements Exception {
  final String message;

  /// GoTrue's `error_code` ("invalid_credentials", "email_not_confirmed", …)
  /// when it sent one.
  final String? code;
  AuthError(this.message, {this.code});

  bool get emailNotConfirmed => code == 'email_not_confirmed';

  @override
  String toString() => message;
}

/// The signed-in account, as Supabase returns it.
class AuthUser {
  final String id;
  final String email;
  final String fullName;
  final String phone;
  final String occupation;
  final DateTime? createdAt;

  const AuthUser({
    required this.id,
    required this.email,
    this.fullName = '',
    this.phone = '',
    this.occupation = '',
    this.createdAt,
  });

  factory AuthUser.fromJson(Map<String, dynamic> j) {
    final meta = j['user_metadata'] is Map ? (j['user_metadata'] as Map).cast<String, dynamic>() : const {};
    String s(Object? v) => v is String ? v.trim() : '';
    return AuthUser(
      id: s(j['id']),
      email: s(j['email']),
      fullName: s(meta['full_name']).isNotEmpty ? s(meta['full_name']) : s(meta['name']),
      phone: s(meta['phone']).isNotEmpty ? s(meta['phone']) : s(j['phone']),
      occupation: s(meta['occupation']),
      createdAt: DateTime.tryParse(s(j['created_at'])),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'email': email,
    'created_at': createdAt?.toIso8601String(),
    'user_metadata': {'full_name': fullName, 'phone': phone, 'occupation': occupation},
  };

  /// Name if given, else the part of the email before the @.
  String get displayName => fullName.isNotEmpty ? fullName : email.split('@').first;

  String get initials {
    final parts = displayName.split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    final first = parts.first.characters.first;
    final last = parts.length > 1 ? parts.last.characters.first : '';
    return (first + last).toUpperCase();
  }
}

class AuthSession {
  final String accessToken;
  final String refreshToken;

  /// When [accessToken] stops working.
  final DateTime expiresAt;
  final AuthUser user;

  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    required this.user,
  });

  factory AuthSession.fromJson(Map<String, dynamic> j) {
    final expiresAt = j['expires_at'] is num
        ? DateTime.fromMillisecondsSinceEpoch((j['expires_at'] as num).toInt() * 1000, isUtc: true)
        : DateTime.now().toUtc().add(Duration(seconds: (j['expires_in'] as num?)?.toInt() ?? 3600));
    return AuthSession(
      accessToken: j['access_token'] as String,
      refreshToken: j['refresh_token'] as String,
      expiresAt: expiresAt,
      user: AuthUser.fromJson((j['user'] as Map).cast<String, dynamic>()),
    );
  }

  Map<String, dynamic> toJson() => {
    'access_token': accessToken,
    'refresh_token': refreshToken,
    'expires_at': expiresAt.millisecondsSinceEpoch ~/ 1000,
    'user': user.toJson(),
  };

  AuthSession withUser(AuthUser user) =>
      AuthSession(accessToken: accessToken, refreshToken: refreshToken, expiresAt: expiresAt, user: user);

  /// Expired, or will be within a minute.
  bool get isStale => DateTime.now().toUtc().isAfter(expiresAt.subtract(const Duration(minutes: 1)));
}

/// What a sign-up produced: a session straight away (projects without email
/// confirmation) or a confirmation mail to open first (this project).
class SignUpResult {
  final AuthSession? session;
  final String email;
  const SignUpResult(this.email, this.session);
  bool get needsConfirmation => session == null;
}

class AuthClient {
  final String baseUrl;
  final String anonKey;
  final http.Client? _http;

  AuthClient({this.baseUrl = kSupabaseUrl, this.anonKey = kSupabaseAnonKey, http.Client? client}) : _http = client;

  Map<String, String> _headers([String? accessToken]) => {
    'apikey': anonKey,
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ${accessToken ?? anonKey}',
  };

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic>? body, {String? accessToken}) =>
      _send('POST', path, body, accessToken: accessToken);

  Future<Map<String, dynamic>> _send(
    String method,
    String path,
    Map<String, dynamic>? body, {
    String? accessToken,
  }) async {
    final uri = Uri.parse('$baseUrl/auth/v1/$path');
    final encoded = body == null ? null : jsonEncode(body);
    final headers = _headers(accessToken);
    http.Response res;
    try {
      final c = _http;
      final Future<http.Response> req = switch (method) {
        'PUT' => c == null ? http.put(uri, headers: headers, body: encoded) : c.put(uri, headers: headers, body: encoded),
        _ => c == null ? http.post(uri, headers: headers, body: encoded) : c.post(uri, headers: headers, body: encoded),
      };
      res = await req.timeout(kAuthTimeout);
    } on TimeoutException {
      throw AuthError('The sign-in service took too long to answer. Check your connection and try again.');
    } catch (_) {
      throw AuthError("Couldn't reach the sign-in service. Check your internet connection.");
    }
    Map<String, dynamic> data = const {};
    if (res.body.isNotEmpty) {
      try {
        final decoded = jsonDecode(res.body);
        if (decoded is Map<String, dynamic>) data = decoded;
      } catch (_) {}
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return data;
    throw _error(res.statusCode, data);
  }

  static AuthError _error(int status, Map<String, dynamic> data) {
    final code = (data['error_code'] ?? data['error']) as String?;
    final raw = (data['msg'] ?? data['error_description'] ?? data['message']) as String?;
    final message = switch (code) {
      'invalid_credentials' || 'invalid_grant' => 'Wrong email or password.',
      'email_not_confirmed' => 'Please confirm your email first — open the link we sent to your inbox.',
      'user_already_exists' || 'email_exists' => 'An account with this email already exists. Sign in instead.',
      'weak_password' => raw ?? 'Please choose a stronger password.',
      'over_email_send_rate_limit' ||
      'over_request_rate_limit' => 'Too many attempts. Please wait a minute and try again.',
      'validation_failed' || 'email_address_invalid' => raw ?? 'Please check the details you entered.',
      'otp_expired' || 'otp_disabled' => 'That code is wrong or has expired. Request a new one.',
      'same_password' => 'Choose a password different from your current one.',
      _ =>
        status == 429
            ? 'Too many attempts. Please wait a minute and try again.'
            : (raw ?? 'Sign-in failed (HTTP $status). Please try again.'),
    };
    return AuthError(message, code: code);
  }

  Future<AuthSession> signIn({required String email, required String password}) async {
    final data = await _post('token?grant_type=password', {'email': email, 'password': password});
    return AuthSession.fromJson(data);
  }

  Future<SignUpResult> signUp({
    required String email,
    required String password,
    required String fullName,
    required String phone,
    required String occupation,
  }) async {
    final data = await _post('signup', {
      'email': email,
      'password': password,
      'data': {'full_name': fullName, 'phone': phone, 'occupation': occupation},
    });
    return SignUpResult(email, data['access_token'] is String ? AuthSession.fromJson(data) : null);
  }

  /// Sends the confirmation mail again.
  Future<void> resendConfirmation(String email) => _post('resend', {'type': 'signup', 'email': email});

  Future<AuthSession> refresh(String refreshToken) async {
    final data = await _post('token?grant_type=refresh_token', {'refresh_token': refreshToken});
    return AuthSession.fromJson(data);
  }

  /// Saves name, phone and occupation to the account's user_metadata and
  /// returns the updated user.
  Future<AuthUser> updateProfile(
    String accessToken, {
    required String fullName,
    required String phone,
    required String occupation,
  }) async {
    final data = await _send('PUT', 'user', {
      'data': {'full_name': fullName, 'phone': phone, 'occupation': occupation},
    }, accessToken: accessToken);
    return AuthUser.fromJson(data);
  }

  /// Mails a password-reset code. The mail template has to include
  /// `{{ .Token }}` for the code to appear (Supabase dashboard setting).
  Future<void> sendPasswordReset(String email) => _post('recover', {'email': email});

  /// Trades the emailed reset code for a session that may set a new password.
  Future<AuthSession> verifyRecoveryCode({required String email, required String code}) async {
    final data = await _post('verify', {'type': 'recovery', 'email': email, 'token': code});
    return AuthSession.fromJson(data);
  }

  Future<AuthUser> updatePassword(String accessToken, String password) async {
    final data = await _send('PUT', 'user', {'password': password}, accessToken: accessToken);
    return AuthUser.fromJson(data);
  }

  /// Revokes the session server-side. Best effort — the caller forgets the
  /// session locally either way.
  Future<void> signOut(String accessToken) => _post('logout', null, accessToken: accessToken);
}
