// Client for the orchestrator's per-user query history. GET /history returns
// the signed-in user's past /ask calls, newest first; DELETE /history erases
// them (services/orchestrator/main.py). Both send the user's Supabase access
// token as `Authorization: Bearer <token>`; the backend forwards it to
// Supabase, where row-level security decides whose rows come back. Mirrors
// web/src/lib/history.ts.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'i18n.dart';

const Duration kHistoryTimeout = Duration(seconds: 15);

enum HistoryErrorKind { auth, unavailable, http, network, timeout, malformed }

class HistoryError implements Exception {
  final HistoryErrorKind kind;
  final String message;
  /// Values for the `{name}` placeholders in [message], a ui_strings.json key.
  final Map<String, Object?> args;
  HistoryError(this.kind, this.message, {this.args = const {}});
  @override
  String toString() => fillPlaceholders(message, args);
}

/// One row of `public.history` (services/orchestrator/sql/supabase_schema.sql).
class HistoryRow {
  final String id;
  final String query;
  final String? intent;
  final String? city;
  final String? lang;

  /// The answer that was shown; null when the question got no grounded answer.
  final String? response;

  /// ISO timestamp.
  final String createdAt;

  const HistoryRow({
    required this.id,
    required this.query,
    this.intent,
    this.city,
    this.lang,
    this.response,
    required this.createdAt,
  });

  /// Null for a row without an id or question, which can't be shown.
  static HistoryRow? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final id = json['id'];
    final query = json['query'];
    if (id is! String || query is! String) return null;
    String? str(String key) => json[key] is String ? json[key] as String : null;
    return HistoryRow(
      id: id,
      query: query,
      intent: str('intent'),
      city: str('city'),
      lang: str('lang'),
      response: str('response'),
      createdAt: str('created_at') ?? '',
    );
  }
}

typedef HistoryFetcher = Future<List<HistoryRow>> Function(String token);
typedef HistoryClearer = Future<void> Function(String token);

Future<Object?> _call({required bool delete, required String token}) async {
  final uri = Uri.parse('$kApiBaseUrl/history');
  final headers = {'Authorization': 'Bearer $token'};
  http.Response res;
  try {
    res = await (delete ? http.delete(uri, headers: headers) : http.get(uri, headers: headers)).timeout(
      kHistoryTimeout,
    );
  } on TimeoutException {
    throw HistoryError(HistoryErrorKind.timeout, 'The history service took too long to answer.');
  } catch (_) {
    throw HistoryError(
      HistoryErrorKind.network,
      "Couldn't reach the server at {url}. Is the orchestrator running?",
      args: {'url': kApiBaseUrl},
    );
  }

  if (res.statusCode == 401 || res.statusCode == 403) {
    throw HistoryError(HistoryErrorKind.auth, 'Your session has expired. Sign in again to see your history.');
  }
  if (res.statusCode == 503) {
    throw HistoryError(HistoryErrorKind.unavailable, 'History is not set up on this server.');
  }
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw HistoryError(
      HistoryErrorKind.http,
      'The history service replied HTTP {status}.',
      args: {'status': res.statusCode},
    );
  }
  try {
    return jsonDecode(res.body);
  } catch (_) {
    throw HistoryError(HistoryErrorKind.malformed, "The history service's reply wasn't valid JSON.");
  }
}

Future<List<HistoryRow>> fetchHistory(String token) async {
  final body = await _call(delete: false, token: token);
  final rows = body is Map<String, dynamic> ? body['history'] : null;
  if (rows is! List) {
    throw HistoryError(HistoryErrorKind.malformed, "The history service's reply didn't look like a history list.");
  }
  return [for (final r in rows) ?HistoryRow.fromJson(r)];
}

Future<void> clearHistory(String token) async {
  try {
    await _call(delete: true, token: token);
  } on HistoryError catch (e) {
    if (e.kind != HistoryErrorKind.auth) rethrow;
    throw HistoryError(HistoryErrorKind.auth, 'Your session has expired. Sign in again to clear your history.');
  }
}

/// Groups for the filter chips; matches nlu.py's INTENTS.
enum HistoryFilter { all, alerts, rain }

bool matchesFilter(HistoryRow row, HistoryFilter filter) => switch (filter) {
  HistoryFilter.alerts => row.intent == 'warnings',
  HistoryFilter.rain => row.intent == 'will_it_rain' || row.intent == 'rainfall_so_far_today',
  HistoryFilter.all => true,
};
