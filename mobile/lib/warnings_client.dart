// Client for the orchestrator's standalone GET /warnings endpoint.
//
// NOT /ask's warnings branch — this is the flatter top-level shape from
// services/orchestrator/main.py's warnings_route(): city, city_name, status,
// warning, legend. Mirrors web/src/lib/warnings.ts.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';

/// /warnings does no LLM/narration work — fixture/cache lookup only — so a
/// shorter timeout than /ask's 30s is appropriate (web/src/lib/warnings.ts
/// uses the same 10s).
const Duration kWarningsTimeout = Duration(seconds: 10);

enum WarningsErrorKind { http, network, timeout, malformed }

class WarningsError implements Exception {
  final WarningsErrorKind kind;
  final String message;
  final int? status;
  WarningsError(this.kind, this.message, {this.status});
  @override
  String toString() => message;
}

/// Raw imd_warnings.public() JSON. `status` is 'unavailable' | 'clear' |
/// 'active'; `warning` is null only for 'unavailable' — never render
/// 'unavailable' as a green all-clear (plan.md §2 principle 3).
Future<Map<String, dynamic>> fetchWarnings({required String city, String? lang}) async {
  final params = <String, String>{'city': city};
  if (lang != null) params['lang'] = lang;
  final uri = Uri.parse('$kApiBaseUrl/warnings').replace(queryParameters: params);

  http.Response res;
  try {
    res = await http.get(uri).timeout(kWarningsTimeout);
  } on TimeoutException {
    throw WarningsError(
      WarningsErrorKind.timeout,
      'No answer within ${kWarningsTimeout.inSeconds}s — the warnings service timed out.',
    );
  } catch (_) {
    throw WarningsError(
      WarningsErrorKind.network,
      "Couldn't reach the warnings service at $kApiBaseUrl. Is the orchestrator running?",
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    final detail = res.statusCode == 404 ? 'Unknown city.' : 'HTTP ${res.statusCode}.';
    throw WarningsError(
      WarningsErrorKind.http,
      'The warnings service replied $detail',
      status: res.statusCode,
    );
  }

  try {
    return jsonDecode(res.body) as Map<String, dynamic>;
  } catch (_) {
    throw WarningsError(WarningsErrorKind.malformed, "The warnings service's reply wasn't valid JSON.");
  }
}
