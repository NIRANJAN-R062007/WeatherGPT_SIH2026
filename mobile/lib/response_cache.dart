// Saved copies of the backend's replies, so a screen that can't reach the
// backend shows the last good answer, labelled with when it was saved,
// instead of only an error (plan.md §2 principle 5, offline-degradable).
//
// Only public, non-personal replies are saved: /facts, /forecast/daily,
// /forecast/hourly, /warnings and /hotlines. Never /ask answers or History.
// Each reply is one small JSON file in the app support directory, keyed by
// its request path and query, so the set is bounded by cities × languages ×
// routes. A copy older than [kMaxSavedAge] is not used.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/widgets.dart';
import 'package:path_provider/path_provider.dart';

/// Older saved copies are ignored: a week-old forecast is no answer.
const Duration kMaxSavedAge = Duration(days: 7);

class SavedReply {
  final Map<String, dynamic> body;
  final DateTime savedAt;
  const SavedReply(this.body, this.savedAt);
}

abstract class ResponseCache {
  /// The saved copy for [key], or null (none, unreadable, or no storage).
  Future<SavedReply?> read(String key);

  /// Best effort: a failure is swallowed, the reply still reaches the screen.
  Future<void> write(String key, Map<String, dynamic> body);
}

/// The key for a GET: path plus query, parameters in a fixed order.
String replyKey(String path, Map<String, String> params) {
  final keys = params.keys.toList()..sort();
  return '$path?${keys.map((k) => '$k=${params[k]}').join('&')}';
}

/// [fetch]'s reply, saved for next time, with a null saved time. If [fetch]
/// fails in a way [useSaved] accepts (the backend couldn't be reached, not
/// "it answered no"), the saved copy and when it was saved instead; with no
/// usable copy, the original error.
Future<(Map<String, dynamic>, DateTime?)> fetchOrSaved(
  ResponseCache? cache,
  String key,
  Future<Map<String, dynamic>> Function() fetch, {
  required bool Function(Object error) useSaved,
}) async {
  try {
    final body = await fetch();
    if (cache != null) unawaited(cache.write(key, body));
    return (body, null);
  } catch (e) {
    if (cache == null || !useSaved(e)) rethrow;
    final saved = await cache.read(key);
    if (saved == null || DateTime.now().difference(saved.savedAt) > kMaxSavedAge) rethrow;
    return (saved.body, saved.savedAt);
  }
}

/// One file per reply under `<app support>/response_cache/`.
class FileResponseCache implements ResponseCache {
  /// Where the files go; tests pass a temporary directory.
  final Future<Directory> Function() _base;
  FileResponseCache({Future<Directory> Function()? base}) : _base = base ?? getApplicationSupportDirectory;

  Future<Directory>? _folder;

  Future<File> _file(String key) async {
    final folder = await (_folder ??= _base().then(
      (d) => Directory('${d.path}${Platform.pathSeparator}response_cache').create(recursive: true),
    ));
    return File('${folder.path}${Platform.pathSeparator}${sha1.convert(utf8.encode(key))}.json');
  }

  @override
  Future<SavedReply?> read(String key) async {
    try {
      final file = await _file(key);
      if (!await file.exists()) return null;
      final json = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      // The key is stored too, so a hash collision can't serve another reply.
      if (json['key'] != key) return null;
      return SavedReply(json['body'] as Map<String, dynamic>, DateTime.parse(json['saved_at'] as String));
    } catch (_) {
      return null; // no storage (widget tests), or a damaged file
    }
  }

  @override
  Future<void> write(String key, Map<String, dynamic> body) async {
    try {
      final file = await _file(key);
      // Write then rename, so a crash mid-write never leaves half a file.
      final temp = File('${file.path}.tmp');
      await temp.writeAsString(
        jsonEncode({'key': key, 'saved_at': DateTime.now().toUtc().toIso8601String(), 'body': body}),
      );
      await temp.rename(file.path);
    } catch (_) {}
  }
}

/// Keeps the replies in memory — widget tests. [now] sets the saved time.
class MemoryResponseCache implements ResponseCache {
  final Map<String, SavedReply> entries = {};
  DateTime Function() now;
  MemoryResponseCache({DateTime Function()? now}) : now = now ?? DateTime.now;

  @override
  Future<SavedReply?> read(String key) async => entries[key];

  @override
  Future<void> write(String key, Map<String, dynamic> body) async => entries[key] = SavedReply(body, now());
}

/// The app's [ResponseCache], for pages that fetch for themselves (Alerts).
class ResponseCacheScope extends InheritedWidget {
  final ResponseCache cache;
  const ResponseCacheScope({super.key, required this.cache, required super.child});

  static ResponseCache? of(BuildContext context) => context.getInheritedWidgetOfExactType<ResponseCacheScope>()?.cache;

  @override
  bool updateShouldNotify(ResponseCacheScope oldWidget) => cache != oldWidget.cache;
}
