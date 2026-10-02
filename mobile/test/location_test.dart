// currentPosition() against a fake geolocator: it gives up after
// kLocationTimeout (falling back to the last known fix), and every failure
// is a LocationDenied whose message is a ui_strings.json key, never
// geolocator's own English exception text.
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:weathergpt/location.dart';
import 'package:weathergpt/ui_strings.dart';

Position _at(double lat, double lon) => Position(
  latitude: lat,
  longitude: lon,
  timestamp: DateTime(2026, 10, 3),
  accuracy: 20,
  altitude: 0,
  altitudeAccuracy: 0,
  heading: 0,
  headingAccuracy: 0,
  speed: 0,
  speedAccuracy: 0,
);

class _FakeGeolocator extends GeolocatorPlatform {
  bool serviceEnabled = true;
  LocationPermission permission = LocationPermission.whileInUse;

  /// What getCurrentPosition does: return a Position or throw.
  Future<Position> Function() current = () async => _at(13.0, 80.2);
  Position? lastKnown;
  LocationSettings? askedWith;

  @override
  Future<bool> isLocationServiceEnabled() async => serviceEnabled;

  @override
  Future<LocationPermission> checkPermission() async => permission;

  @override
  Future<LocationPermission> requestPermission() async => permission;

  @override
  Future<Position> getCurrentPosition({LocationSettings? locationSettings}) {
    askedWith = locationSettings;
    return current();
  }

  @override
  Future<Position?> getLastKnownPosition({bool forceLocationManager = false}) async => lastKnown;
}

Future<String> _deniedMessage() async {
  try {
    await currentPosition();
  } on LocationDenied catch (e) {
    return e.message;
  }
  fail('expected LocationDenied');
}

void main() {
  late GeolocatorPlatform original;
  late _FakeGeolocator geo;

  setUp(() {
    original = GeolocatorPlatform.instance;
    geo = _FakeGeolocator();
    GeolocatorPlatform.instance = geo;
  });
  tearDown(() => GeolocatorPlatform.instance = original);

  test('a fix comes back as lat/lon, asked for with a time limit', () async {
    final here = await currentPosition();
    expect((here.lat, here.lon), (13.0, 80.2));
    expect(geo.askedWith?.timeLimit, kLocationTimeout);
  });

  test('no fix in time: the last known position is used', () async {
    geo.current = () async => throw TimeoutException('no fix');
    geo.lastKnown = _at(9.9, 78.1);
    final here = await currentPosition();
    expect((here.lat, here.lon), (9.9, 78.1));
  });

  test('no fix in time and none known: says so instead of spinning', () async {
    geo.current = () async => throw TimeoutException('no fix');
    expect(await _deniedMessage(), "Couldn't get a location fix in time. Try again, or pick a city manually.");
  });

  test("geolocator's own exceptions become translatable messages", () async {
    geo.current = () async => throw const LocationServiceDisabledException();
    expect(await _deniedMessage(), 'Location services are off. Enable them or pick a city manually.');

    geo.current = () async => throw const PermissionDeniedException('denied');
    expect(await _deniedMessage(), 'Location permission denied. Pick a city manually instead.');

    geo.current = () async => throw StateError('anything else');
    expect(await _deniedMessage(), "Couldn't get your location. Pick a city manually instead.");
  });

  test('location off or refused up front', () async {
    geo.serviceEnabled = false;
    expect(await _deniedMessage(), 'Location services are off. Enable them or pick a city manually.');

    geo
      ..serviceEnabled = true
      ..permission = LocationPermission.deniedForever;
    expect(await _deniedMessage(), 'Location permission denied. Pick a city manually instead.');
  });

  test('every message currentPosition can throw has hi / ta / te / mr', () async {
    final messages = <String>{};
    Future<void> collect(void Function() arrange) async {
      geo = _FakeGeolocator();
      GeolocatorPlatform.instance = geo;
      arrange();
      messages.add(await _deniedMessage());
    }

    await collect(() => geo.serviceEnabled = false);
    await collect(() => geo.permission = LocationPermission.denied);
    await collect(() => geo.current = () async => throw TimeoutException('no fix'));
    await collect(() => geo.current = () async => throw StateError('x'));
    expect(messages, hasLength(4));
    for (final lang in ['hi', 'ta', 'te', 'mr']) {
      for (final m in messages) {
        expect(kUiStrings[lang]?[m], isNotNull, reason: '$lang: $m');
      }
    }
  });
}
