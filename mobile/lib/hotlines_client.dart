// Client for the orchestrator's GET /hotlines: a city's emergency numbers —
// 112, then its state's, district's and city's own lines — each read off an
// official government page (services/orchestrator/hotlines.py,
// data/hotlines.json). `name` and `note` are English keys into
// ui-strings/ui_strings.json, translated where they're shown.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'response_cache.dart';

const Duration kHotlinesTimeout = Duration(seconds: 10);

class Hotline {
  /// As shown: "1077", "040 2111 1111".
  final String number;

  /// Digits only, for a tel: link.
  final String dial;
  final String name;
  final String note;

  const Hotline({required this.number, required this.dial, required this.name, required this.note});

  static Hotline? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final number = json['number'];
    final dial = json['dial'];
    if (number is! String || dial is! String || dial.isEmpty) return null;
    return Hotline(
      number: number,
      dial: dial,
      name: json['name'] is String ? json['name'] as String : number,
      note: json['note'] is String ? json['note'] as String : '',
    );
  }
}

/// 112 works anywhere in India (MHA's ERSS page, data/hotlines.json), so it
/// is shown even when the list can't be fetched.
const kEmergencyHotline = Hotline(
  number: '112',
  dial: '112',
  name: 'Emergency',
  note: 'Any emergency, anywhere in India',
);

class HotlineList {
  final List<Hotline> lines;

  /// When the numbers were last checked against their sources (YYYY-MM-DD).
  final String? checked;

  /// When this list was saved, if it's a saved copy rather than fresh.
  final DateTime? savedAt;

  const HotlineList(this.lines, {this.checked, this.savedAt});
}

/// Throws on any failure (no connection, an HTTP error, a backend from
/// before /hotlines); the caller falls back to [kEmergencyHotline]. With a
/// [cache], a failure of any kind returns the saved list instead, if there
/// is one: emergency numbers are wanted most when the network isn't there.
Future<HotlineList> fetchHotlines({required String city, String? lang, ResponseCache? cache}) async {
  final params = <String, String>{'city': city};
  if (lang != null) params['lang'] = lang;
  final uri = Uri.parse('$kApiBaseUrl/hotlines').replace(queryParameters: params);
  final (json, savedAt) = await fetchOrSaved(cache, replyKey('/hotlines', params), () async {
    final res = await http.get(uri).timeout(kHotlinesTimeout);
    if (res.statusCode != 200) throw http.ClientException('HTTP ${res.statusCode}', uri);
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final raw = json['hotlines'];
    if (raw is! List || !raw.any((e) => Hotline.fromJson(e) != null)) throw http.ClientException('no hotlines', uri);
    return json;
  }, useSaved: (_) => true);
  final raw = json['hotlines'] as List;
  return HotlineList(
    [for (final e in raw) ?Hotline.fromJson(e)],
    checked: json['checked'] is String ? json['checked'] as String : null,
    savedAt: savedAt,
  );
}
