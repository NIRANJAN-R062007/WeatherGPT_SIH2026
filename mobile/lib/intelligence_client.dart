// Client for the Weather Intelligence Engine's view-only slice (plan.md §8
// Phase 9, WIE-14): GET /intelligence/best-window and POST
// /intelligence/scenario (services/orchestrator/main.py +
// weather_intelligence/). Mirrors web/src/lib/intelligence.ts. Deterministic
// rules only — nothing here is narrated by an LLM (plan.md §2 principle 7),
// so these shapes are read directly, the same discipline as
// aviation_client.dart / warnings_client.dart.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

const Duration kIntelligenceTimeout = Duration(seconds: 15);

enum IntelligenceErrorKind { http, network, timeout, malformed }

class IntelligenceError implements Exception {
  final IntelligenceErrorKind kind;
  final String message;
  IntelligenceError(this.kind, this.message);
  @override
  String toString() => message;
}

Future<Map<String, dynamic>> _getJson(String path, Map<String, String> params) async {
  final uri = Uri.parse('$kApiBaseUrl$path').replace(queryParameters: params);
  return _send(() => http.get(uri));
}

Future<Map<String, dynamic>> _postJson(String path, Map<String, dynamic> body) async {
  final uri = Uri.parse('$kApiBaseUrl$path');
  return _send(() => http.post(uri, headers: {'Content-Type': 'application/json'}, body: jsonEncode(body)));
}

Future<Map<String, dynamic>> _send(Future<http.Response> Function() call) async {
  http.Response res;
  try {
    res = await call().timeout(kIntelligenceTimeout);
  } on TimeoutException {
    throw IntelligenceError(
      IntelligenceErrorKind.timeout,
      'The weather intelligence service took too long to answer.',
    );
  } catch (_) {
    throw IntelligenceError(
      IntelligenceErrorKind.network,
      "Couldn't reach the weather intelligence service at $kApiBaseUrl. Is the orchestrator running?",
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    final detail = res.statusCode == 404
        ? 'Unknown city.'
        : res.statusCode == 422
            ? 'Bad request.'
            : 'HTTP ${res.statusCode}.';
    throw IntelligenceError(IntelligenceErrorKind.http, 'The weather intelligence service replied $detail');
  }
  try {
    return jsonDecode(res.body) as Map<String, dynamic>;
  } catch (_) {
    throw IntelligenceError(
      IntelligenceErrorKind.malformed,
      "The weather intelligence service's reply wasn't valid JSON.",
    );
  }
}

/// "status": "ok" (a window exists) | "no_suitable_window" (checked, none
/// passed — a real negative result, never the least-bad hour) |
/// "unavailable" (no hourly forecast to check at all).
Future<Map<String, dynamic>> fetchBestWindow({
  required String city,
  required String day,
  String activity = 'outdoor',
}) {
  return _getJson('/intelligence/best-window', {'city': city, 'day': day, 'activity': activity});
}

/// A time outside the forecast's hours comes back `available: false` — never
/// filled in with an invented value.
Future<Map<String, dynamic>> fetchScenario({
  required String city,
  required String day,
  required List<String> times,
  String activity = 'outdoor',
}) {
  return _postJson('/intelligence/scenario', {'city': city, 'day': day, 'times': times, 'activity': activity});
}
