// The mockups' coloured weather glyphs (a yellow sun peeking over a blue
// cloud, a cloud with rain…), composed from Material icons so they stay
// crisp at any size. Keyed on the canonical condition from
// data/decoders/weather_conditions.json, grouped the same way as
// format.dart's conditionStyle.
import 'package:flutter/material.dart';

import '../theme.dart';

enum _Kind { sun, moon, partly, partlyNight, cloud, rain, storm, wind }

_Kind _kindOf(String? condition, bool night) {
  switch (condition) {
    case 'clear':
    case 'mostly_clear':
      return night ? _Kind.moon : _Kind.sun;
    case 'partly_cloudy':
      return night ? _Kind.partlyNight : _Kind.partly;
    case 'light_rain':
    case 'rain_showers':
    case 'rain':
    case 'heavy_rain':
      return _Kind.rain;
    case 'thunderstorm':
    case 'thunderstorm_with_rain':
    case 'scattered_thunderstorms':
      return _Kind.storm;
    case 'windy':
      return _Kind.wind;
    default:
      return _Kind.cloud;
  }
}

class WeatherGlyph extends StatelessWidget {
  final String? condition;
  final bool night;
  final double size;
  const WeatherGlyph(this.condition, {super.key, this.night = false, this.size = 40});

  @override
  Widget build(BuildContext context) {
    final s = size;
    Widget icon(IconData i, Color c, double f, {Alignment at = Alignment.center}) =>
        Align(alignment: at, child: Icon(i, size: s * f, color: c));

    final List<Widget> layers = switch (_kindOf(condition, night)) {
      _Kind.sun => [icon(Icons.wb_sunny, AppColors.sun, 0.95)],
      _Kind.moon => [icon(Icons.nightlight_round, AppColors.moonGlyph, 0.8)],
      _Kind.partly => [
          icon(Icons.wb_sunny, AppColors.sun, 0.72, at: const Alignment(-0.7, -0.75)),
          icon(Icons.cloud, AppColors.cloudGlyph, 0.8, at: const Alignment(0.6, 0.7)),
        ],
      _Kind.partlyNight => [
          icon(Icons.nightlight_round, AppColors.moonGlyph, 0.6, at: const Alignment(-0.7, -0.75)),
          icon(Icons.cloud, AppColors.cloudGlyph, 0.8, at: const Alignment(0.6, 0.7)),
        ],
      _Kind.cloud => [icon(Icons.cloud, AppColors.cloudGlyph, 0.92)],
      _Kind.rain => [
          icon(Icons.cloud, AppColors.cloudGlyph, 0.8, at: const Alignment(0, -0.6)),
          icon(Icons.water_drop, AppColors.rainGlyph, 0.3, at: const Alignment(-0.35, 0.95)),
          icon(Icons.water_drop, AppColors.rainGlyph, 0.3, at: const Alignment(0.35, 0.95)),
        ],
      _Kind.storm => [
          icon(Icons.cloud, AppColors.cloudGlyph, 0.8, at: const Alignment(0, -0.6)),
          icon(Icons.bolt, AppColors.sun, 0.45, at: const Alignment(0, 1)),
        ],
      _Kind.wind => [icon(Icons.air, AppColors.cloudGlyph, 0.9)],
    };
    return SizedBox.square(dimension: s, child: Stack(children: layers));
  }
}
