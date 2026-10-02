// GPS position for "Use my location". /ask and /warnings have no lat/lon
// param (services/orchestrator/main.py), so this is as far as "location"
// goes: the city picker finds the nearest registered city (cities.dart's
// nearestCity) and selects it, exactly like picking it from the list would,
// and says how far away it is.
import 'package:geolocator/geolocator.dart';

class LocationDenied implements Exception {
  final String message;
  LocationDenied(this.message);
  @override
  String toString() => message;
}

/// Where the device is; tests pass a stub to the city picker.
typedef Locator = Future<({double lat, double lon})> Function();

/// Throws [LocationDenied] when location is off or not allowed.
Future<({double lat, double lon})> currentPosition() async {
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

  final position = await Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(accuracy: LocationAccuracy.low),
  );
  return (lat: position.latitude, lon: position.longitude);
}
