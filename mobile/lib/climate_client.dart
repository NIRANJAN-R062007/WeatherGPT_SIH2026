// Client for the orchestrator's GET /climate: a demo city's rainfall and mean
// temperature history from Open-Meteo's ERA5 reanalysis, with the yearly and
// seasonal figures and trends already computed server-side
// (services/orchestrator/climate.py) — the app only draws and words them.
// ERA5 is a ~25 km model grid, NOT IMD station data, and the payload's label,
// credit link and "computed by WeatherGPT" note are shown with every chart.
//
// A period without a complete set of days has a null figure: it is "missing",
// never zero (plan.md §2 principle 3), and the chart leaves a gap there.
// `status` "unavailable" means no data at all — "not available", never "no
// change".
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'i18n.dart';

/// A cold ERA5 fetch is ~800 Open-Meteo calls' worth of data; the server caches
/// it for a day (climate.TTL_SECONDS) and its own timeout is 30 s.
const Duration kClimateTimeout = Duration(seconds: 35);

enum ClimateErrorKind { http, network, timeout, malformed }

class ClimateError implements Exception {
  final ClimateErrorKind kind;
  final String message;
  final int? status;

  /// Values for the `{name}` placeholders in [message], a ui_strings.json key.
  final Map<String, Object?> args;
  ClimateError(this.kind, this.message, {this.status, this.args = const {}});
  @override
  String toString() => fillPlaceholders(message, args);
}

/// What a chart plots.
enum ClimateMetric {
  rain('rain_mm', 'mm'),
  temperature('temp_mean_c', '°C');

  /// The key in the payload's rows and trends.
  final String key;
  final String unit;
  const ClimateMetric(this.key, this.unit);
}

/// The time window a chart covers: the whole year, or one of climate.py's fixed
/// calendar seasons (not IMD's declared monsoon onset or withdrawal).
enum ClimatePeriod {
  year(null),
  winter('winter'),
  preMonsoon('pre_monsoon'),
  monsoon('monsoon'),
  postMonsoon('post_monsoon');

  /// The season's key in the payload, null for the whole year.
  final String? key;
  const ClimatePeriod(this.key);
}

/// One year's figure; [value] is null when the year (or season) has missing days.
class YearValue {
  final int year;
  final double? value;
  const YearValue(this.year, this.value);
}

/// An ordinary least-squares trend over the complete years (climate.linear_trend).
class ClimateTrend {
  /// "ok" or "insufficient_data" — no slope in the second case.
  final String status;

  /// Complete years in the fit.
  final int n;
  final int? firstYear;
  final int? lastYear;
  final double? mean;
  final double? slopePerDecade;
  final double? stderrPerDecade;

  /// Whether the slope is clear of natural year-to-year variation at the 95%
  /// level. False means "can't tell", not "no change".
  final bool significant95;

  const ClimateTrend({
    required this.status,
    required this.n,
    required this.firstYear,
    required this.lastYear,
    required this.mean,
    required this.slopePerDecade,
    required this.stderrPerDecade,
    required this.significant95,
  });

  bool get hasSlope => status == 'ok' && slopePerDecade != null && mean != null;

  static ClimateTrend? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final status = json['status'];
    if (status is! String) return null;
    double? num_(String k) {
      final v = json[k];
      return v is num && v.isFinite ? v.toDouble() : null;
    }

    return ClimateTrend(
      status: status,
      n: json['n'] is int ? json['n'] as int : 0,
      firstYear: json['first_year'] is int ? json['first_year'] as int : null,
      lastYear: json['last_year'] is int ? json['last_year'] as int : null,
      mean: num_('mean'),
      slopePerDecade: num_('slope_per_decade'),
      stderrPerDecade: num_('stderr_per_decade'),
      significant95: json['significant_95'] == true,
    );
  }
}

class ClimateData {
  /// "ok" or "unavailable" (never "unsupported_city": the route 404s on that).
  final String status;
  final String city;
  final bool isLive;
  final String? retrievedAt;

  /// "Open-Meteo / ERA5 reanalysis, not IMD station data".
  final String label;
  final String creditText;
  final String creditUrl;
  final String changesNote;
  final String calendarNote;
  final String licenceUrl;
  final String termsUrl;

  /// Fewest complete years a trend needs (climate.MIN_TREND_YEARS).
  final int minTrendYears;

  /// The first and last dates asked of Open-Meteo (YYYY-MM-DD), if known.
  final String? firstDate;
  final String? lastDate;

  final List<Map<String, dynamic>> annual;
  final List<Map<String, dynamic>> seasonal;
  final Map<String, dynamic> trends;

  const ClimateData._({
    required this.status,
    required this.city,
    required this.isLive,
    required this.retrievedAt,
    required this.label,
    required this.creditText,
    required this.creditUrl,
    required this.changesNote,
    required this.calendarNote,
    required this.licenceUrl,
    required this.termsUrl,
    required this.minTrendYears,
    required this.firstDate,
    required this.lastDate,
    required this.annual,
    required this.seasonal,
    required this.trends,
  });

  bool get unavailable => status != 'ok' || annual.isEmpty;

  /// Each year's [metric] figure for [period], oldest first. A year with missing
  /// days is a null value, not zero.
  List<YearValue> series(ClimatePeriod period, ClimateMetric metric) {
    final rows = period.key == null
        ? annual
        : [
            for (final r in seasonal)
              if (r['season'] == period.key) r,
          ];
    final out = <YearValue>[];
    for (final r in rows) {
      final year = r['year'];
      if (year is! int) continue;
      final v = r[metric.key];
      out.add(YearValue(year, v is num && v.isFinite ? v.toDouble() : null));
    }
    out.sort((a, b) => a.year.compareTo(b.year));
    return out;
  }

  /// The trend for [period] and [metric], or null if the payload has none.
  ClimateTrend? trend(ClimatePeriod period, ClimateMetric metric) {
    final block = period.key == null
        ? trends['year']
        : (trends['season'] is Map
              ? (trends['season'] as Map)[period.key]
              : null);
    return block is Map ? ClimateTrend.fromJson(block[metric.key]) : null;
  }

  static List<Map<String, dynamic>> _rows(Object? json) => json is List
      ? [
          for (final r in json)
            if (r is Map<String, dynamic>) r,
        ]
      : const [];

  static ClimateData? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final status = json['status'];
    final city = json['city'];
    if (status is! String || city is! String) return null;
    String text(String k, String fallback) =>
        json[k] is String && (json[k] as String).isNotEmpty
        ? json[k] as String
        : fallback;
    final credit = json['credit'] is Map<String, dynamic>
        ? json['credit'] as Map<String, dynamic>
        : const {};
    final requested = json['requested'] is Map<String, dynamic>
        ? json['requested'] as Map<String, dynamic>
        : const {};
    return ClimateData._(
      status: status,
      city: city,
      isLive: json['is_live'] == true,
      retrievedAt: json['retrieved_at'] is String
          ? json['retrieved_at'] as String
          : null,
      label: text(
        'label',
        'Open-Meteo / ERA5 reanalysis, not IMD station data',
      ),
      creditText: credit['text'] is String
          ? credit['text'] as String
          : 'Weather data by Open-Meteo.com',
      creditUrl: credit['url'] is String
          ? credit['url'] as String
          : 'https://open-meteo.com/',
      changesNote: text(
        'changes_note',
        "Monthly, seasonal and annual figures and trends are computed by WeatherGPT from Open-Meteo's daily ERA5 values.",
      ),
      calendarNote: text(
        'calendar_note',
        "Months and seasons are fixed calendar windows. They are not IMD's declared monsoon onset or withdrawal.",
      ),
      licenceUrl: text('licence_url', 'https://open-meteo.com/en/licence'),
      termsUrl: text('terms_url', 'https://open-meteo.com/en/terms'),
      minTrendYears: json['min_trend_years'] is int
          ? json['min_trend_years'] as int
          : 10,
      firstDate: requested['start_date'] is String
          ? requested['start_date'] as String
          : null,
      lastDate: requested['end_date'] is String
          ? requested['end_date'] as String
          : null,
      annual: _rows(json['annual']),
      seasonal: _rows(json['seasonal']),
      trends: json['trends'] is Map<String, dynamic>
          ? json['trends'] as Map<String, dynamic>
          : const {},
    );
  }
}

typedef ClimateFetcher = Future<ClimateData> Function(String city);

Future<ClimateData> fetchClimate(String city) async {
  final uri = Uri.parse(
    '$kApiBaseUrl/climate',
  ).replace(queryParameters: {'city': city});

  http.Response res;
  try {
    res = await http.get(uri).timeout(kClimateTimeout);
  } on TimeoutException {
    throw ClimateError(
      ClimateErrorKind.timeout,
      'The climate service took too long to answer.',
    );
  } catch (_) {
    throw ClimateError(
      ClimateErrorKind.network,
      "Couldn't reach the climate service at {url}. Is the orchestrator running?",
      args: {'url': kApiBaseUrl},
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw ClimateError(
      ClimateErrorKind.http,
      res.statusCode == 404
          ? "This server doesn't have climate history for that city."
          : 'The climate service replied HTTP {status}.',
      status: res.statusCode,
      args: {'status': res.statusCode},
    );
  }

  Object? json;
  try {
    json = jsonDecode(utf8.decode(res.bodyBytes));
  } catch (_) {
    json = null;
  }
  final data = ClimateData.fromJson(json);
  if (data == null) {
    throw ClimateError(
      ClimateErrorKind.malformed,
      'The climate service sent an answer the app could not read.',
    );
  }
  return data;
}
