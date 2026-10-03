// Display helpers shared by the pages: IST timestamps (web/src/lib/
// warningUi.ts's istTimestamp), city/day labels (web/src/components/
// AskAnswer.tsx's cityLabel/dayLabel), and the condition -> icon/accent map
// web/src/pages/HomePage.tsx calls CONDITION_META. IST is a fixed +05:30 with
// no DST, so it's computed directly rather than pulling in a tz package.
import 'package:flutter/material.dart';

import 'cities.dart';
import 'theme.dart';
import 'i18n.dart';

const Duration _istOffset = Duration(hours: 5, minutes: 30);
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

DateTime nowIst() => DateTime.now().toUtc().add(_istOffset);

DateTime? _parseIst(String? iso) {
  if (iso == null) return null;
  final d = DateTime.tryParse(iso);
  return d?.toUtc().add(_istOffset);
}

String _two(int n) => n.toString().padLeft(2, '0');

/// "27 Sep, 13:49 IST" — the raw string back if it doesn't parse.
String istTimestamp(String? iso) {
  final d = _parseIst(iso);
  if (d == null) return iso ?? '';
  return '${_two(d.day)} ${_months[d.month - 1]}, ${_two(d.hour)}:${_two(d.minute)} IST';
}

/// "13:49 IST".
String istTime(String? iso) {
  final d = _parseIst(iso);
  if (d == null) return iso ?? '';
  return '${_two(d.hour)}:${_two(d.minute)} IST';
}

/// "13:49" — [istTime] without the zone, for tight rows; '' if unparseable.
String istClock(String? iso) {
  final d = _parseIst(iso);
  return d == null ? '' : '${_two(d.hour)}:${_two(d.minute)}';
}

/// Minutes past IST midnight of [iso], for placing it on a day's timeline.
int? istMinuteOfDay(String? iso) {
  final d = _parseIst(iso);
  return d == null ? null : d.hour * 60 + d.minute;
}

/// "27 Sep" for [iso], or for today + [fallbackOffsetDays] when [iso] is
/// missing; the month in [lang].
String istDayMonth(String? iso, {int fallbackOffsetDays = 0, String lang = 'en'}) {
  final d = _parseIst(iso) ?? nowIst().add(Duration(days: fallbackOffsetDays));
  return '${d.day} ${trIn(lang, _months[d.month - 1])}';
}

/// "27 Sep" for a calendar [date], the month in [lang].
String dayMonth(DateTime date, String lang) => '${date.day} ${trIn(lang, _months[date.month - 1])}';

/// A forecast day's name in [lang]: "Today" and "Tomorrow" by the backend's
/// [label], else the short weekday of [date] ("Mon").
String forecastDayName(String label, DateTime? date, String lang) {
  if (label == 'today') return trIn(lang, 'Today');
  if (label == 'tomorrow') return trIn(lang, 'Tomorrow');
  return date == null ? trIn(lang, 'Later') : trIn(lang, _weekdays[date.weekday - 1]);
}

/// "11 h 59 min".
String hoursMinutes(Duration d, String lang) => trIn(lang, '{h} h {m} min', {'h': d.inHours, 'm': d.inMinutes % 60});

/// IMD rain categories (data/decoders/precipitation_categories.json) as
/// ui_strings.json keys; null for a key this table doesn't know.
String? rainCategoryLabel(String? key) => const {
  'no_rain': 'No rain',
  'light': 'Light rain',
  'moderate': 'Moderate rain',
  'heavy': 'Heavy rain',
  'very_heavy': 'Very heavy rain',
  'extremely_heavy': 'Extremely heavy rain',
}[key];

/// "0.6 mm": one decimal below 10 mm, whole millimetres above.
String millimetres(num mm) => '${mm < 10 ? mm.toStringAsFixed(1) : mm.round()} mm';

/// Resolved city keys come back lowercase ("chennai"); use the bundled
/// display name, falling back to capitalising a key cities.dart lacks.
String cityLabel(String? key) {
  if (key == null || key.isEmpty) return '';
  for (final c in kCities) {
    if (c.key == key) return c.name;
  }
  return key[0].toUpperCase() + key.substring(1);
}

/// router.legacy_day values -> a short label; `next_<n>_days` is built by
/// the backend, so it's parsed rather than enumerated.
String dayLabel(Object? day) {
  if (day is! String || day.isEmpty) return 'Unknown period';
  final span = RegExp(r'^next_(\d+)_days$').firstMatch(day);
  if (span != null) return 'Next ${span.group(1)} days';
  final spaced = day.replaceAll('_', ' ');
  return spaced[0].toUpperCase() + spaced.substring(1);
}

class ConditionStyle {
  final IconData icon;

  /// HomePage.tsx CONDITION_META accent — tints the hero gradient.
  final Color accent;

  /// Foreground for the icon on light surfaces.
  final Color iconColor;
  const ConditionStyle(this.icon, this.accent, this.iconColor);
}

/// Canonical keys from data/decoders/weather_conditions.json, grouped into
/// HomePage.tsx's five CONDITION_META moods (clear / partly cloudy / cloudy /
/// rain / storm) with the same accent tokens.
ConditionStyle conditionStyle(String? condition, {bool night = false}) {
  switch (condition) {
    case 'clear':
    case 'mostly_clear':
      return ConditionStyle(
        night ? Icons.nightlight_outlined : Icons.wb_sunny_outlined,
        AppColors.tertiaryContainer,
        night ? AppColors.primary : AppColors.tertiary,
      );
    case 'partly_cloudy':
      return const ConditionStyle(Icons.wb_cloudy_outlined, AppColors.primaryContainer, AppColors.primary);
    case 'light_rain':
    case 'rain_showers':
      return const ConditionStyle(Icons.grain, AppColors.secondary, AppColors.primary);
    case 'rain':
      return const ConditionStyle(Icons.umbrella_outlined, AppColors.secondary, AppColors.primary);
    case 'heavy_rain':
      return const ConditionStyle(Icons.water_drop, AppColors.secondary, AppColors.secondary);
    case 'thunderstorm':
    case 'thunderstorm_with_rain':
    case 'scattered_thunderstorms':
      return const ConditionStyle(Icons.thunderstorm_outlined, AppColors.inverseSurface, AppColors.primary);
    case 'windy':
      return const ConditionStyle(Icons.air, AppColors.outline, AppColors.onSurfaceVariant);
    case 'mostly_cloudy':
    case 'cloudy':
    default:
      return const ConditionStyle(Icons.cloud_outlined, AppColors.outline, AppColors.onSurfaceVariant);
  }
}

/// "light rain" -> "Light rain" (condition_label is lowercase in English).
String sentenceCase(String? s) {
  if (s == null || s.isEmpty) return '';
  return s[0].toUpperCase() + s.substring(1);
}
