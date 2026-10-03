// Client for the orchestrator's GET /ask endpoint.
//
// Since the location resolver (PR #44) an answer may be for any place in
// India: `city` is then null and `location` names it; a fallback may offer
// places to tap (`ambiguous`), the nearest one (`not_found` + `nearest`), or
// ask where (`needs_location`). AskAnswer renders those.
//
// Mirrors web/src/lib/api.ts's classifyAsk() exactly — same five branches,
// same discrimination order (services/orchestrator/main.py's ask() is the
// source of truth for both). Kept as a loosely-typed Map here rather than
// Dart classes per field, since the branches share almost no shape and a
// full sealed-class mirror of api.ts wasn't worth the duplication for a
// first mobile pass.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'i18n.dart';

/// /ask is synchronous over the whole NLU + weather + narration chain.
/// web/src/lib/api.ts uses the same 30s budget for the same reason: the
/// Gemini->Groq fallback path can push a multi-day forecast well past 15s.
const Duration kAskTimeout = Duration(seconds: 30);

enum AskErrorKind { http, network, timeout, malformed }

class AskError implements Exception {
  final AskErrorKind kind;
  final String message;
  final int? status;
  /// Values for the `{name}` placeholders in [message], a ui_strings.json key.
  final Map<String, Object?> args;
  AskError(this.kind, this.message, {this.status, this.args = const {}});
  @override
  String toString() => fillPlaceholders(message, args);
}

enum AskKind { success, warnings, warningsUnavailable, ungrounded, fallback }

class AskOutcome {
  final AskKind kind;
  final Map<String, dynamic> data;
  const AskOutcome(this.kind, this.data);
}

/// Sort a raw /ask body into its branch. Order matters — see api.ts's
/// classifyAsk() docstring for why:
/// - intent == "warnings" never carries a weather-success shape.
/// - a success also carries `grounding`, so `response` is checked first.
/// - ungrounded is the only `message` branch that also carries `grounding`.
AskOutcome classifyAsk(Map<String, dynamic> data) {
  if (data['intent'] == 'warnings') {
    return data.containsKey('response')
        ? AskOutcome(AskKind.warnings, data)
        : AskOutcome(AskKind.warningsUnavailable, data);
  }
  if (data.containsKey('response')) {
    return AskOutcome(AskKind.success, data);
  }
  if (data.containsKey('grounding')) {
    return AskOutcome(AskKind.ungrounded, data);
  }
  return AskOutcome(AskKind.fallback, data);
}

Future<AskOutcome> askWeather({
  required String text,
  String? lang,
  String? city,
  String? token,
  /// persona.PERSONAS (services/orchestrator/persona.py): changes narration
  /// framing only, never the facts. Omitted for the backend's own default,
  /// "general", so default requests stay byte-identical to before.
  String? persona,

  /// The user's location, already snapped to the 0.05° grid: used when the
  /// question names no place or says "here". It wins over [city].
  ({double lat, double lon})? here,

  /// A place the user tapped from an `ambiguous` reply (`gn:<digits>`):
  /// wins over everything else.
  String? placeId,
}) async {
  final params = <String, String>{'text': text};
  if (lang != null) params['lang'] = lang;
  if (city != null) params['city'] = city;
  if (persona != null && persona != 'general') params['persona'] = persona;
  if (here != null) {
    params['lat'] = '${here.lat}';
    params['lon'] = '${here.lon}';
  }
  if (placeId != null) params['place_id'] = placeId;
  final uri = Uri.parse('$kApiBaseUrl/ask').replace(queryParameters: params);

  final headers = <String, String>{};
  if (token != null) headers['Authorization'] = 'Bearer $token';

  http.Response res;
  try {
    res = await http.get(uri, headers: headers).timeout(kAskTimeout);
  } on TimeoutException {
    throw AskError(
      AskErrorKind.timeout,
      'No answer within {seconds}s — the weather service timed out.',
      args: {'seconds': kAskTimeout.inSeconds},
    );
  } catch (_) {
    throw AskError(
      AskErrorKind.network,
      "Couldn't reach the weather service at {url}. Is the orchestrator running?",
      args: {'url': kApiBaseUrl},
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw AskError(
      AskErrorKind.http,
      'The weather service replied HTTP {status}.',
      status: res.statusCode,
      args: {'status': res.statusCode},
    );
  }

  Map<String, dynamic> payload;
  try {
    payload = jsonDecode(res.body) as Map<String, dynamic>;
  } catch (_) {
    throw AskError(AskErrorKind.malformed, "The weather service's reply wasn't valid JSON.");
  }
  if (!payload.containsKey('intent')) {
    throw AskError(AskErrorKind.malformed, "The weather service's reply didn't look like an answer.");
  }
  return classifyAsk(payload);
}
