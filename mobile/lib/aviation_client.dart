// Client for the orchestrator's GET /aviation endpoint: the current METAR and
// TAF for a demo city's airport (services/orchestrator/aviation.py). Mirrors
// web/src/lib/aviation.ts.
//
// Each report (`metar`, `taf`) is null when the source has none; a screen must
// show that as "not available", never as fair weather (plan.md §2 principle
// 3). `is_live` is false for an offline snapshot, which the screen labels.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

/// A live fetch plus decoding, cached server-side; well under /ask's 30 s.
const Duration kAviationTimeout = Duration(seconds: 15);

enum AviationErrorKind { http, network, timeout, malformed }

class AviationError implements Exception {
  final AviationErrorKind kind;
  final String message;
  final int? status;
  AviationError(this.kind, this.message, {this.status});
  @override
  String toString() => message;
}

/// One METAR or TAF as /aviation returns it.
class AviationReport {
  /// The report exactly as issued.
  final String raw;

  /// The English briefing, one line per element or forecast period.
  final List<String> lines;
  final bool isLive;

  /// When the text was fetched — a snapshot's own date when it isn't live.
  final String retrievedAt;
  final String source;

  /// "Observed 03:00 IST · 21:30 UTC" / "Issued …", or null.
  final String? stamp;

  const AviationReport({
    required this.raw,
    required this.lines,
    required this.isLive,
    required this.retrievedAt,
    required this.source,
    this.stamp,
  });

  static AviationReport? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final raw = json['raw'];
    final lines = json['lines'];
    if (raw is! String || lines is! List) return null;
    final decoded = json['decoded'] is Map<String, dynamic> ? json['decoded'] as Map<String, dynamic> : const {};
    String? stamp;
    for (final (key, label) in const [('observed', 'Observed'), ('issued', 'Issued')]) {
      final s = decoded[key];
      if (s is Map<String, dynamic> && s['time_ist'] is String && s['time_utc'] is String) {
        stamp = '$label ${s['time_ist']} IST · ${s['time_utc']} UTC';
        break;
      }
    }
    return AviationReport(
      raw: raw,
      lines: [
        for (final l in lines)
          if (l is String) l,
      ],
      isLive: json['is_live'] == true,
      retrievedAt: json['retrieved_at'] is String ? json['retrieved_at'] as String : '',
      source: json['source'] is String ? json['source'] as String : '',
      stamp: stamp,
    );
  }
}

class AviationData {
  final String station;
  final String? stationName;

  /// "ok" when at least one report exists, "unavailable" when neither does.
  final String status;
  final AviationReport? metar;
  final AviationReport? taf;
  final String disclaimer;

  const AviationData({
    required this.station,
    required this.stationName,
    required this.status,
    required this.metar,
    required this.taf,
    required this.disclaimer,
  });

  bool get unavailable => status == 'unavailable';

  /// "Chennai airport (VOMM)".
  String get where => stationName != null ? '$stationName airport ($station)' : 'Station $station';
}

typedef AviationFetcher = Future<AviationData> Function(String city);

Future<AviationData> fetchAviation(String city) async {
  final uri = Uri.parse('$kApiBaseUrl/aviation').replace(queryParameters: {'city': city});

  http.Response res;
  try {
    res = await http.get(uri).timeout(kAviationTimeout);
  } on TimeoutException {
    throw AviationError(AviationErrorKind.timeout, 'The airport weather service took too long to answer.');
  } catch (_) {
    throw AviationError(
      AviationErrorKind.network,
      "Couldn't reach the airport weather service at $kApiBaseUrl. Is the orchestrator running?",
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    final detail = res.statusCode == 404 ? 'No airport for that city.' : 'HTTP ${res.statusCode}.';
    throw AviationError(AviationErrorKind.http, 'The airport weather service replied $detail', status: res.statusCode);
  }

  final Object? body;
  try {
    body = jsonDecode(res.body);
  } catch (_) {
    throw AviationError(AviationErrorKind.malformed, "The airport weather service's reply wasn't valid JSON.");
  }
  if (body is! Map<String, dynamic> || body['station'] is! String || body['status'] is! String) {
    throw AviationError(AviationErrorKind.malformed, "The airport weather service's reply didn't look like a report.");
  }
  return AviationData(
    station: body['station'] as String,
    stationName: body['station_name'] as String?,
    status: body['status'] as String,
    metar: AviationReport.fromJson(body['metar']),
    taf: AviationReport.fromJson(body['taf']),
    disclaimer: body['disclaimer'] is String ? body['disclaimer'] as String : '',
  );
}
