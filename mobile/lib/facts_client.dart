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
// Current conditions also carry `rain_so_far` ([FactsResult.rainSoFar]).
//
// GET /forecast/daily and /forecast/hourly (the day list, sun times and the
// hourly strip) come through the same helper and errors. A backend from
// before those routes answers 404; [FactsError.status] says so, and the
// pages fall back to the /facts rows.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'i18n.dart';

/// Fixture/cache lookup with no LLM work — same budget as /warnings.
const Duration kFactsTimeout = Duration(seconds: 10);

enum FactsErrorKind { http, network, timeout, malformed }

class FactsError implements Exception {
  final FactsErrorKind kind;
  final String message;
  final int? status;
  /// Values for the `{name}` placeholders in [message], a ui_strings.json key.
  final Map<String, Object?> args;
  FactsError(this.kind, this.message, {this.status, this.args = const {}});
  @override
  String toString() => fillPlaceholders(message, args);
}

/// A JSON object of figures, read with type checks: a missing or mistyped
/// field is null, never a crash.
class Figures {
  final Map<String, dynamic> raw;
  const Figures(this.raw);

  num? number(String key) {
    final v = raw[key];
    return v is num ? v : null;
  }

  String? text(String key) {
    final v = raw[key];
    return v is String && v.isNotEmpty ? v : null;
  }

  bool get isLive => raw['is_live'] == true;
}

Map<String, dynamic>? _object(Object? v) => v is Map<String, dynamic> ? v : null;

/// One /facts reply. An unsupported city or a missing snapshot is a 200
/// with only `message` (and maybe `city`) — [facts] is null then.
class FactsResult {
  final String? city;
  final String? cityName;
  final String? conditionLabel;
  final Map<String, dynamic>? facts;
  final String? message;

  /// Current conditions only: rain since local midnight (`rain_so_far_mm`,
  /// `since`) or, with no hourly history, the last 24 hours
  /// (`rain_last_24h_mm`); either with `rain_category`, `is_live`, `source`.
  final Figures? rainSoFar;

  const FactsResult({this.city, this.cityName, this.conditionLabel, this.facts, this.message, this.rainSoFar});

  factory FactsResult.fromJson(Map<String, dynamic> json) {
    final rain = _object(json['rain_so_far']);
    return FactsResult(
      city: json['city'] as String?,
      cityName: json['city_name'] as String?,
      conditionLabel: json['condition_label'] as String?,
      facts: _object(json['facts']),
      message: json['message'] as String?,
      rainSoFar: rain == null ? null : Figures(rain),
    );
  }

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

/// One day of GET /forecast/daily: `label` (today / tomorrow / a weekday),
/// `date` (YYYY-MM-DD), `condition` + `condition_label`, `night_condition`
/// + `night_condition_label`, `high_c`, `low_c`, `rain_probability_pct`,
/// `night_rain_probability_pct`, `rain_mm`, `wind_kmh`, `wind_dir`,
/// `humidity_pct`, `uv_index`, `sunrise`, `sunset` — each only when served.
class ForecastDay extends Figures {
  const ForecastDay(super.raw);

  String get label => text('label') ?? 'later';
  DateTime? get date => DateTime.tryParse(text('date') ?? '');
  String? get condition => text('condition');
  String? get conditionLabel => text('condition_label');
  String? get nightCondition => text('night_condition');
  String? get nightConditionLabel => text('night_condition_label');
  String? get sunrise => text('sunrise');
  String? get sunset => text('sunset');
}

/// One hour of GET /forecast/hourly: `time_iso`, `local_time` ("HH:MM",
/// city-local), `date`, `temp_c`, `feels_like_c`, `rain_probability_pct`,
/// `rain_mm`, `wind_kmh`, `condition` + `condition_label`, `uv_index`,
/// `is_daytime`.
class ForecastHour extends Figures {
  const ForecastHour(super.raw);

  String get localTime => text('local_time') ?? '';
  String? get date => text('date');
  String? get condition => text('condition');
  String? get conditionLabel => text('condition_label');
  bool get isNight => raw['is_daytime'] == false;
}

/// GET /forecast/daily or /forecast/hourly: the entries plus the series'
/// provenance. Empty [entries] means `status: unavailable`.
class ForecastSeries<T extends Figures> {
  final List<T> entries;
  final String? source;
  final bool isLive;
  final String? issued;

  const ForecastSeries(this.entries, {this.source, this.isLive = false, this.issued});

  factory ForecastSeries.fromJson(Map<String, dynamic> json, String key, T Function(Map<String, dynamic>) entry) {
    final provenance = Figures(_object(json['provenance']) ?? const {});
    final list = json[key];
    return ForecastSeries(
      [for (final e in list is List ? list : const []) if (e is Map<String, dynamic>) entry(e)],
      source: provenance.text('source'),
      isLive: provenance.isLive,
      issued: provenance.text('issued'),
    );
  }

  bool get isEmpty => entries.isEmpty;
}

typedef DailyForecast = ForecastSeries<ForecastDay>;
typedef HourlyForecast = ForecastSeries<ForecastHour>;

Future<FactsResult> fetchFacts({
  required String city,
  String intent = 'current_weather',
  String day = 'today',
  String? lang,
}) async {
  final params = <String, String>{'city': city, 'intent': intent, 'day': day};
  if (lang != null) params['lang'] = lang;
  return FactsResult.fromJson(await _getJson('/facts', params));
}

/// Up to [days] days (the backend serves 1–10).
Future<DailyForecast> fetchDailyForecast({required String city, String? lang, int days = 10}) async {
  final params = <String, String>{'city': city, 'days': '$days'};
  if (lang != null) params['lang'] = lang;
  return ForecastSeries.fromJson(await _getJson('/forecast/daily', params), 'days', ForecastDay.new);
}

/// The next 24 hours.
Future<HourlyForecast> fetchHourlyForecast({required String city, String? lang}) async {
  final params = <String, String>{'city': city};
  if (lang != null) params['lang'] = lang;
  return ForecastSeries.fromJson(await _getJson('/forecast/hourly', params), 'hours', ForecastHour.new);
}

Future<Map<String, dynamic>> _getJson(String path, Map<String, String> params) async {
  final uri = Uri.parse('$kApiBaseUrl$path').replace(queryParameters: params);

  http.Response res;
  try {
    res = await http.get(uri).timeout(kFactsTimeout);
  } on TimeoutException {
    throw FactsError(
      FactsErrorKind.timeout,
      'No answer within {seconds}s — the weather service timed out.',
      args: {'seconds': kFactsTimeout.inSeconds},
    );
  } catch (_) {
    throw FactsError(
      FactsErrorKind.network,
      "Couldn't reach the weather service at {url}. Is the orchestrator running?",
      args: {'url': kApiBaseUrl},
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw FactsError(
      FactsErrorKind.http,
      'The weather service replied HTTP {status}.',
      status: res.statusCode,
      args: {'status': res.statusCode},
    );
  }

  try {
    return jsonDecode(res.body) as Map<String, dynamic>;
  } catch (_) {
    throw FactsError(FactsErrorKind.malformed, "The weather service's reply wasn't valid JSON.");
  }
}
