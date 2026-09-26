// GPS -> nearest registered city. /ask and /warnings have no lat/lon param
// (services/orchestrator/main.py), so this is as far as "location" goes:
// find the nearest of the 8 demo cities and pass its name as the `city`
// hint, exactly like picking it from the city dropdown would.
import 'package:geolocator/geolocator.dart';

import 'cities.dart';

class LocationDenied implements Exception {
  final String message;
  LocationDenied(this.message);
  @override
  String toString() => message;
}

Future<City> locateNearestCity() async {
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
  return nearestCity(position.latitude, position.longitude);
}
