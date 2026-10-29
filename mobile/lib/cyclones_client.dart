// Client for the orchestrator's GET /cyclones: tropical cyclones near India
// from GDACS, with each event's track, cone and wind areas
// (services/orchestrator/gdacs.py). GDACS is not IMD, and its alerts are
// automatic and not reviewed by experts — the payload's `attribution` and
// `disclaimer` are shown with the map.
//
// `events` is null when the fetch failed (status "unavailable"); a screen
// must show that as "not available", never as "no cyclones" (plan.md §2
// principle 3). `is_live` is false for a dated offline snapshot.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'i18n.dart';

/// A cold GDACS refresh can take up to 30 s server-side (gdacs.DEADLINE_SECONDS);
/// the result is then cached for 10 minutes.
const Duration kCyclonesTimeout = Duration(seconds: 35);

enum CyclonesErrorKind { http, network, timeout, malformed }

class CyclonesError implements Exception {
  final CyclonesErrorKind kind;
  final String message;
  final int? status;

  /// Values for the `{name}` placeholders in [message], a ui_strings.json key.
  final Map<String, Object?> args;
  CyclonesError(this.kind, this.message, {this.status, this.args = const {}});
  @override
  String toString() => fillPlaceholders(message, args);
}

/// A [longitude, latitude] point.
typedef LonLat = ({double lon, double lat});

LonLat? _point(Object? json) {
  if (json is! List || json.length < 2) return null;
  final lon = json[0];
  final lat = json[1];
  if (lon is! num || lat is! num || !lon.isFinite || !lat.isFinite) return null;
  return (lon: lon.toDouble(), lat: lat.toDouble());
}

List<LonLat> _line(Object? json) {
  if (json is! List) return const [];
  return [for (final p in json) ?_point(p)];
}

/// A polygon's rings (outer first); a ring with fewer than 3 points is dropped.
List<List<LonLat>> _rings(Object? json) {
  if (json is! List) return const [];
  return [
    for (final ring in json)
      if (_line(ring).length >= 3) _line(ring),
  ];
}

/// One leg of the track. `category` is GDACS's own label for the cyclone's
/// strength on that leg (TD, TS, HU …), shown as given. `isForecast` is true
/// for the predicted part of the path.
class TrackSegment {
  final String? category;
  final bool isForecast;
  final List<LonLat> points;
  const TrackSegment({required this.category, required this.isForecast, required this.points});

  static TrackSegment? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final points = _line(json['coordinates']);
    if (points.length < 2) return null;
    return TrackSegment(
      category: json['category'] is String ? json['category'] as String : null,
      isForecast: json['is_forecast'] == true,
      points: points,
    );
  }
}

/// A wind-radius area: `label` is GDACS's own wind speed ("60 km/h").
class WindArea {
  final String? label;
  final List<List<LonLat>> rings;
  const WindArea({required this.label, required this.rings});

  static WindArea? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final rings = _rings(json['coordinates']);
    if (rings.isEmpty) return null;
    return WindArea(label: json['label'] is String ? json['label'] as String : null, rings: rings);
  }
}

class CycloneEvent {
  final int eventId;
  final String name;
  final String title;

  /// GDACS's alert level exactly as given — "Green", "Orange" or "Red"; the
  /// app does not grade a storm itself (plan.md §2 principle 4).
  final String alertLevel;

  /// The level for the current episode, which can differ from [alertLevel].
  final String? episodeAlertLevel;
  final bool isCurrent;
  final String? fromDate;
  final String? toDate;
  final String? dateModified;
  final double? lon;
  final double? lat;

  /// The agency GDACS took the bulletin from (JTWC, NOAA, RSMC …).
  final String? sourceAgency;

  /// GDACS's maximum-wind text, e.g. "Tropical Storm (maximum wind speed of 222 km/h)".
  final String? severityText;
  final String? reportUrl;
  final List<TrackSegment> segments;
  final List<List<LonLat>> cone;
  final List<WindArea> windAreas;

  const CycloneEvent({
    required this.eventId,
    required this.name,
    required this.title,
    required this.alertLevel,
    required this.episodeAlertLevel,
    required this.isCurrent,
    required this.fromDate,
    required this.toDate,
    required this.dateModified,
    required this.lon,
    required this.lat,
    required this.sourceAgency,
    required this.severityText,
    required this.reportUrl,
    required this.segments,
    required this.cone,
    required this.windAreas,
  });

  /// Null for an entry without an id, a name or an alert level.
  static CycloneEvent? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final id = json['event_id'];
    final name = json['name'];
    final level = json['alert_level'];
    if (id is! int || name is! String || name.isEmpty || level is! String || level.isEmpty) return null;
    String? str(String key) => json[key] is String ? json[key] as String : null;
    final track = json['track'] is Map<String, dynamic> ? json['track'] as Map<String, dynamic> : const {};
    final severity = json['severity'] is Map<String, dynamic> ? json['severity'] as Map<String, dynamic> : const {};
    final lon = json['lon'];
    final lat = json['lat'];
    return CycloneEvent(
      eventId: id,
      name: name,
      title: str('title') ?? name,
      alertLevel: level,
      episodeAlertLevel: str('episode_alert_level'),
      isCurrent: json['is_current'] == true,
      fromDate: str('from_date'),
      toDate: str('to_date'),
      dateModified: str('date_modified'),
      lon: lon is num && lon.isFinite ? lon.toDouble() : null,
      lat: lat is num && lat.isFinite ? lat.toDouble() : null,
      sourceAgency: str('source_agency'),
      severityText: severity['text'] is String ? severity['text'] as String : null,
      reportUrl: str('report_url'),
      segments: [
        if (track['segments'] is List)
          for (final s in track['segments'] as List) ?TrackSegment.fromJson(s),
      ],
      cone: [
        if (track['cones'] is List)
          for (final c in track['cones'] as List)
            if (c is Map<String, dynamic>) ..._rings(c['coordinates']),
      ],
      windAreas: [
        if (track['areas'] is List)
          for (final a in track['areas'] as List) ?WindArea.fromJson(a),
      ],
    );
  }
}

class CyclonesData {
  /// "ok" or "unavailable".
  final String status;

  /// Null when [status] is "unavailable" — not the same as an empty list.
  final List<CycloneEvent>? events;
  final bool isLive;
  final bool complete;
  final String? retrievedAt;
  final String attribution;
  final String disclaimer;
  final String sourceUrl;
  final String termsUrl;

  /// The box GDACS events are kept in: (lonMin, lonMax, latMin, latMax).
  final (double, double, double, double) area;
  final int windowDays;

  const CyclonesData({
    required this.status,
    required this.events,
    required this.isLive,
    required this.complete,
    required this.retrievedAt,
    required this.attribution,
    required this.disclaimer,
    required this.sourceUrl,
    required this.termsUrl,
    required this.area,
    required this.windowDays,
  });

  bool get unavailable => status != 'ok' || events == null;

  /// A live, complete, successful answer with no event (gdacs.no_cyclones_confirmed).
  /// A snapshot or a truncated search never confirms it.
  bool get noCyclonesConfirmed => !unavailable && isLive && complete && events!.isEmpty;

  static CyclonesData? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final status = json['status'];
    if (status is! String) return null;
    final raw = json['events'];
    final events = raw is List ? [for (final e in raw) ?CycloneEvent.fromJson(e)] : null;
    final area = json['area'];
    double box(String key, double fallback) {
      final v = area is Map ? area[key] : null;
      return v is num && v.isFinite ? v.toDouble() : fallback;
    }

    String text(String key, String fallback) => json[key] is String ? json[key] as String : fallback;
    return CyclonesData(
      status: status,
      events: events,
      isLive: json['is_live'] == true,
      complete: json['complete'] == true,
      retrievedAt: json['retrieved_at'] is String ? json['retrieved_at'] as String : null,
      attribution: text('attribution', 'Cyclone data: Global Disaster Alert and Coordination System, GDACS. Not an IMD product.'),
      disclaimer: text(
        'disclaimer',
        'GDACS cyclone alerts are produced automatically, are not reviewed by human experts and do not replace official warnings. Follow IMD and your state disaster authority.',
      ),
      sourceUrl: text('source_url', 'https://www.gdacs.org/'),
      termsUrl: text('terms_url', ''),
      area: (box('lon_min', 55), box('lon_max', 100), box('lat_min', 0), box('lat_max', 30)),
      windowDays: json['window_days'] is int ? json['window_days'] as int : 14,
    );
  }
}

typedef CyclonesFetcher = Future<CyclonesData> Function();

Future<CyclonesData> fetchCyclones() async {
  final uri = Uri.parse('$kApiBaseUrl/cyclones');

  http.Response res;
  try {
    res = await http.get(uri).timeout(kCyclonesTimeout);
  } on TimeoutException {
    throw CyclonesError(CyclonesErrorKind.timeout, 'The cyclone service took too long to answer.');
  } catch (_) {
    throw CyclonesError(
      CyclonesErrorKind.network,
      "Couldn't reach the cyclone service at {url}. Is the orchestrator running?",
      args: {'url': kApiBaseUrl},
    );
  }

  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw CyclonesError(
      CyclonesErrorKind.http,
      res.statusCode == 404
          ? "This server doesn't have the cyclone map yet."
          : 'The cyclone service replied HTTP {status}.',
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
  final data = CyclonesData.fromJson(json);
  if (data == null) {
    throw CyclonesError(CyclonesErrorKind.malformed, 'The cyclone service sent an answer the app could not read.');
  }
  return data;
}
