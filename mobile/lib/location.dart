// GPS position for "Use my location". The city picker finds the nearest
// registered city (cities.dart's nearestCity) for the pages that take a
// city (/facts, /warnings) and says how far away it is; Chat also sends the
// fix itself to /ask (lat/lon), snapped to [snapToGrid] first so the raw
// position never leaves the phone.
import 'dart:async';

import 'package:geolocator/geolocator.dart';

class LocationDenied implements Exception {
  final String message;
  LocationDenied(this.message);
  @override
  String toString() => message;
}

/// [degrees] on the 0.05° grid (about 5 km), the same grid the backend
/// fetches and caches weather on: near enough for weather, too coarse to
/// pin down a home.
double snapToGrid(double degrees) => double.parse(((degrees / 0.05).round() * 0.05).toStringAsFixed(2));

/// Where the device is; tests pass a stub to the city picker.
typedef Locator = Future<({double lat, double lon})> Function();

/// How long to wait for a fix before falling back to the last known position.
/// Without a limit the picker spins for as long as the device has no fix.
const Duration kLocationTimeout = Duration(seconds: 15);

/// Throws [LocationDenied], whose message is an English key for `tr()`, when
/// location is off, not allowed or not found in time — never geolocator's own
/// English-only exception text.
Future<({double lat, double lon})> currentPosition() async {
  try {
    return await _currentPosition();
  } on LocationDenied {
    rethrow;
  } on LocationServiceDisabledException {
    throw LocationDenied('Location services are off. Enable them or pick a city manually.');
  } on PermissionDeniedException {
    throw LocationDenied('Location permission denied. Pick a city manually instead.');
  } catch (_) {
    throw LocationDenied("Couldn't get your location. Pick a city manually instead.");
  }
}

Future<({double lat, double lon})> _currentPosition() async {
  final serviceEnabled = await Geolocator.isLocationServiceEnabled();
  if (!serviceEnabled) {
    throw LocationDenied('Location services are off. Enable them or pick a city manually.');
  }

  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
    throw LocationDenied('Location permission denied. Pick a city manually instead.');
  }

  Position? position;
  try {
    position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.low, timeLimit: kLocationTimeout),
    );
  } on TimeoutException {
    // Indoors, or GPS still warming up: a recent fix still picks the right city.
    position = await Geolocator.getLastKnownPosition();
    if (position == null) {
      throw LocationDenied("Couldn't get a location fix in time. Try again, or pick a city manually.");
    }
  }
  return (lat: position.latitude, lon: position.longitude);
}
