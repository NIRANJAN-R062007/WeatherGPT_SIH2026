// Client for the orchestrator's GET /cities: the cities this backend answers
// for (services/orchestrator/cities.py, from data/cities.json). main.dart
// asks once at start-up and hands the list to UiPrefs; any failure keeps the
// bundled list in cities.dart.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'cities.dart';
import 'config.dart';

const Duration kCitiesTimeout = Duration(seconds: 10);

typedef CitiesFetcher = Future<List<City>?> Function();

/// The server's cities, or null when it can't be reached or its answer has
/// no usable city — never throws.
Future<List<City>?> fetchCities() async {
  try {
    final res = await http.get(Uri.parse('$kApiBaseUrl/cities')).timeout(kCitiesTimeout);
    if (res.statusCode != 200) return null;
    final body = jsonDecode(utf8.decode(res.bodyBytes));
    final list = body is Map<String, dynamic> ? body['cities'] : null;
    if (list is! List) return null;
    final cities = [for (final c in list) ?City.fromJson(c)];
    return cities.isEmpty ? null : cities;
  } catch (_) {
    return null;
  }
}
