// Mirrors data/cities.json (repo root) — the shared source of truth also
// consumed by services/orchestrator/cities.py and web/src/data/cities.ts.
// Only the fields the app needs (key, coords, display name, region) are
// copied here; keep in sync until the app fetches a live GET /cities.
import 'dart:math' as math;

class City {
  final String key;
  final double lat;
  final double lon;
  final String name;
  final String region;

  const City({
    required this.key,
    required this.lat,
    required this.lon,
    required this.name,
    required this.region,
  });
}

const List<City> kCities = [
  City(key: 'chennai', lat: 13.0827, lon: 80.2707, name: 'Chennai', region: 'Tamil Nadu'),
  City(key: 'madurai', lat: 9.9252, lon: 78.1198, name: 'Madurai', region: 'Tamil Nadu'),
  City(key: 'coimbatore', lat: 11.0168, lon: 76.9558, name: 'Coimbatore', region: 'Tamil Nadu'),
  City(key: 'bengaluru', lat: 12.9716, lon: 77.5946, name: 'Bengaluru', region: 'Karnataka'),
  City(key: 'hyderabad', lat: 17.385, lon: 78.4867, name: 'Hyderabad', region: 'Telangana'),
  City(key: 'mumbai', lat: 19.076, lon: 72.8777, name: 'Mumbai', region: 'Maharashtra'),
  City(key: 'delhi', lat: 28.6139, lon: 77.209, name: 'Delhi', region: 'Delhi'),
  City(
    key: 'thiruvananthapuram',
    lat: 8.5241,
    lon: 76.9366,
    name: 'Thiruvananthapuram',
    region: 'Kerala',
  ),
];

City cityByKey(String key) => kCities.firstWhere(
      (c) => c.key == key,
      orElse: () => kCities.first,
    );

/// /ask and /warnings only know the 8 registered demo cities and take a
/// city name, not lat/lon (services/orchestrator/main.py has no lat/lon
/// param) — so "use my location" means finding the nearest of these 8
/// points on-device, not a real reverse-geocode.
City nearestCity(double lat, double lon) {
  City best = kCities.first;
  double bestDist = double.infinity;
  for (final c in kCities) {
    final d = _haversineKm(lat, lon, c.lat, c.lon);
    if (d < bestDist) {
      bestDist = d;
      best = c;
    }
  }
  return best;
}

double _haversineKm(double lat1, double lon1, double lat2, double lon2) {
  const r = 6371.0;
  final dLat = _deg2rad(lat2 - lat1);
  final dLon = _deg2rad(lon2 - lon1);
  final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(_deg2rad(lat1)) *
          math.cos(_deg2rad(lat2)) *
          math.sin(dLon / 2) *
          math.sin(dLon / 2);
  final c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  return r * c;
}

double _deg2rad(double deg) => deg * (math.pi / 180.0);
