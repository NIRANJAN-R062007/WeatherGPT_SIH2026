// SEC-N19: the session lives in the secure store, a plaintext
// auth_session.json left by an older build is moved there and deleted, and a
// release build refuses an http API or Supabase URL.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weathergpt/config.dart';
import 'package:weathergpt/state/auth_store.dart';

void main() {
  late Directory dir;
  late File legacy;

  SecureSessionStorage storage() => SecureSessionStorage(legacyDir: () async => dir);

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    dir = Directory.systemTemp.createTempSync('session_storage_test');
    legacy = File('${dir.path}/auth_session.json');
  });

  tearDown(() => dir.deleteSync(recursive: true));

  final session = {'access_token': 'access', 'refresh_token': 'refresh', 'expires_at': 1};

  group('SecureSessionStorage', () {
    test('round-trips a session without writing any file', () async {
      final s = storage();
      expect(await s.read(), isNull);
      await s.write(session);
      expect(await s.read(), session);
      expect(dir.listSync(), isEmpty);
      await s.clear();
      expect(await s.read(), isNull);
    });

    test('moves a legacy plaintext session into the secure store and deletes the file', () async {
      legacy.writeAsStringSync(jsonEncode(session));
      expect(await storage().read(), session);
      expect(legacy.existsSync(), isFalse);
      // Still there on the next launch, from the secure store.
      expect(await storage().read(), session);
    });

    test('keeps the secure session and deletes a stale legacy file', () async {
      await storage().write(session);
      legacy.writeAsStringSync(jsonEncode({'guest': true}));
      expect(await storage().read(), session);
      expect(legacy.existsSync(), isFalse);
    });

    test('drops an unreadable legacy file and starts signed out', () async {
      legacy.writeAsStringSync('not json');
      expect(await storage().read(), isNull);
      expect(legacy.existsSync(), isFalse);
    });
  });

  group('releaseConfigError', () {
    const https = 'https://example.org';

    test('allows http outside release builds', () {
      expect(releaseConfigError(release: false, apiBaseUrl: 'http://localhost:8001', supabaseUrl: https), isNull);
    });

    test('allows https in a release build', () {
      expect(releaseConfigError(release: true, apiBaseUrl: https, supabaseUrl: https), isNull);
    });

    test('rejects an http API base in a release build', () {
      expect(
        releaseConfigError(release: true, apiBaseUrl: 'http://localhost:8001', supabaseUrl: https),
        contains('API_BASE_URL'),
      );
    });

    test('rejects an http or malformed Supabase URL in a release build', () {
      expect(
        releaseConfigError(release: true, apiBaseUrl: https, supabaseUrl: 'http://x.supabase.co'),
        contains('SUPABASE_URL'),
      );
      expect(releaseConfigError(release: true, apiBaseUrl: https, supabaseUrl: 'https://'), contains('SUPABASE_URL'));
    });
  });
}
