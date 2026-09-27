// Client for the orchestrator's GET /facts endpoint — the raw facts dict
// behind an answer, for surfaces that show individual figures rather than a
// narrated sentence (services/orchestrator/main.py's facts()). It's what
// lets the Home hero and the Forecast page show live numbers instead of the
// static design samples web/src/pages/ still carries.
//
// Only three (intent, day) shapes are accepted by the backend — anything
// else is a 422:
//   current_weather + today    -> current conditions (temp_c, feels_like_c,
//                                 humidity_pct, wind_kmh, wind_dir, uv_index…)
//   will_it_rain    + today    -> today's forecast entry
//   current_weather + tonight / tomorrow -> that forecast entry
// (rain_probability_pct, high_c, low_c, condition). Tonight's high/low are
// the whole day's, since the backend reads them off the same forecast day.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';

/// Fixture/cache lookup with no LLM work — same budget as /warnings.
const Duration kFactsTimeout = Duration(seconds: 10);

enum FactsErrorKind { http, network, timeout, malformed }

class FactsError implements Exception {
  final FactsErrorKind kind;
  final String message;
  final int? status;
  FactsError(this.kind, this.message, {this.status});
  @override
  String toString() => message;
}

/// One /facts reply. An unsupported city or a missing snapshot is a 200
/// with only `message` (and maybe `city`) — [facts] is null then.
class FactsResult {
  final String? city;
  final String? cityName;
  final String? conditionLabel;
  final Map<String, dynamic>? facts;
  final String? message;

  const FactsResult({this.city, this.cityName, this.conditionLabel, this.facts, this.message});

  factory FactsResult.fromJson(Map<String, dynamic> json) => FactsResult(
        city: json['city'] as String?,
        cityName: json['city_name'] as String?,
        conditionLabel: json['condition_label'] as String?,
        facts: json['facts'] is Map<String, dynamic> ? json['facts'] as Map<String, dynamic> : null,
        message: json['message'] as String?,
      );

  bool get hasData => facts != null;

  num? number(String key) {
    final v = facts?[key];
    return v is num ? v : null;
  }

  String? text(String key) {
    final v = facts?[key];
    return v is String && v.isNotEmpty ? v : null;
  }

  /// Canonical condition key (data/decoders/weather_conditions.json).
  String? get condition => text('condition');
  String? get source => text('source');
  String? get issued => text('issued');
  bool get isLive => facts?['is_live'] == true;
}

Future<FactsResult> fetchFacts({
  required String city,
  String intent = 'current_weather',
  String day = 'today',
  String? lang,
}) async {
  final params = <String, String>{'city': city, 'intent': intent, 'day': day};
  if (lang != null) params['lang'] = lang;
  final uri = Uri.parse('$kApiBaseUrl/facts').replace(queryParameters: params);

  http.Response res;
  try {
    res = await http.get(uri).timeout(kFactsTimeout);
  } on TimeoutException {
    throw FactsError(
      FactsErrorKind.timeout,
      'No answer within ${kFactsTimeout.inSeconds}s — the weather service timed out.',
    );
  } catch (_) {
    throw FactsError(
      FactsErrorKind.network,
      "Couldn't reach the weather service at $kApiBaseUrl. Is the orchestrator running?",
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw FactsError(
      FactsErrorKind.http,
      'The weather service replied HTTP ${res.statusCode}.',
      status: res.statusCode,
    );
  }

  try {
    return FactsResult.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  } catch (_) {
    throw FactsError(FactsErrorKind.malformed, "The weather service's reply wasn't valid JSON.");
  }
}
