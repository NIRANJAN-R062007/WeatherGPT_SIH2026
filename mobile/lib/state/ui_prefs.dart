// App-wide UI preferences — the mobile twin of web/src/state/
// UiPrefsContext.tsx: language, temperature unit and the selected city, all
// shared so the Topbar's city picker and every page's /ask, /facts and
// /warnings calls stay in sync. Adds the persona flag, which web/'s Settings
// page shows but doesn't wire; here it reaches /ask's `persona` param and is
// the app-wide theme selector (main.dart builds the theme from it), plus the
// Light / Dark appearance. Unlike web/, all five are remembered across
// launches (prefs_store.dart; main.dart loads and saves them).
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../cities.dart';
import '../config.dart';
import '../persona_theme.dart';

enum TempUnit { celsius, fahrenheit }

/// Settings > Appearance. Every persona has a light and a dark palette.
enum Appearance { light, dark, system }

/// One of a persona card's four focus chips.
class PersonaFeature {
  final IconData icon;
  final String label;
  const PersonaFeature(this.icon, this.label);
}

/// A persona-flavoured question for Home's Quick Actions or Chat's
/// Suggested Questions. `{city}` is replaced with the selected city. Each is
/// something /ask's NLU answers (current weather, forecast, rain, rain so
/// far, warnings) — the persona reframes the answer, never the facts.
class PersonaQuestion {
  final IconData icon;
  final String template;

  /// Shorter text for Home's rows; the question itself when null.
  final String? label;
  const PersonaQuestion(this.icon, this.template, {this.label});

  String question(String city) => template.replaceAll('{city}', city);
  String title(String city) => (label ?? template).replaceAll('{city}', city);
}

class Persona {
  final String id;
  final String label;
  final IconData icon;

  /// One line under the name — Settings' profile card and the persona list.
  final String tagline;

  /// What the framing does; persona.py's hint, paraphrased.
  final String blurb;

  /// How Home greets this persona: "Good morning, Farmer!".
  final String role;

  /// The per-page lead lines (the pics/ persona mockups).
  final String homeLead;
  final String chatLead;
  final String askHint;
  final String forecastLead;
  final String alertsLead;

  /// What persona.py's hint actually frames — nothing it is told never to
  /// mention (soil, crops, sea state, visibility, runway data, safety
  /// verdicts), so a chip never promises data the answers can't carry.
  final List<PersonaFeature> features;

  final List<PersonaQuestion> quickActions;
  final List<PersonaQuestion> suggestions;

  const Persona(
    this.id,
    this.label,
    this.icon, {
    required this.tagline,
    required this.blurb,
    required this.role,
    required this.homeLead,
    required this.chatLead,
    required this.askHint,
    required this.forecastLead,
    required this.alertsLead,
    required this.features,
    required this.quickActions,
    required this.suggestions,
  });

  /// This persona's app-wide palette and scenery (persona_theme.dart).
  PersonaTheme get theme => personaThemeFor(id);
}

/// Ids are services/orchestrator/persona.py's PERSONAS; blurbs paraphrase
/// its prompt hints, which only reframe the same facts.
const List<Persona> kPersonas = [
  Persona(
    'general',
    'General Citizen',
    Icons.person,
    tagline: 'Daily weather, lifestyle & city planning.',
    blurb: 'Plain-language current conditions and forecast.',
    role: 'Citizen',
    homeLead: "Here's the latest weather and updates for your day.",
    chatLead:
        'Get accurate weather insights and updates for your daily life — every number checked against '
        'the source data.',
    askHint: 'Ask a question about the weather…',
    forecastLead: 'Plan your day with accurate weather updates.',
    alertsLead: 'Stay informed and stay safe.',
    features: [
      PersonaFeature(Icons.wb_sunny_outlined, 'Daily Forecast'),
      PersonaFeature(Icons.umbrella_outlined, 'Rain Chance'),
      PersonaFeature(Icons.air, 'Wind Updates'),
      PersonaFeature(Icons.warning_amber_rounded, 'IMD Warnings'),
    ],
    quickActions: [
      PersonaQuestion(Icons.umbrella_outlined, 'Will it rain today in {city}?', label: 'Will it rain today?'),
      PersonaQuestion(
        Icons.nights_stay_outlined,
        'What is the weather tonight in {city}?',
        label: 'What should I expect this evening?',
      ),
      PersonaQuestion(Icons.calendar_month_outlined, '5-day forecast for {city}', label: '5-day forecast'),
    ],
    suggestions: [
      PersonaQuestion(Icons.umbrella_outlined, 'Will it rain tomorrow in {city}?'),
      PersonaQuestion(Icons.calendar_month_outlined, '5-day forecast for {city}'),
      PersonaQuestion(Icons.water_drop_outlined, 'How much rain so far today in {city}?'),
      PersonaQuestion(Icons.warning_amber_rounded, 'Any weather warnings for {city}?'),
    ],
  ),
  Persona(
    'farmer',
    'Farmer',
    Icons.eco,
    tagline: 'Agriculture, crops & weather planning.',
    blurb: 'Whether conditions suit field work like spraying or harvest.',
    role: 'Farmer',
    homeLead: "Here's the latest weather for your fields.",
    chatLead:
        'Get accurate weather insights for your farming activities, backed by real-time data and trusted '
        'sources.',
    askHint: 'Ask a question about your fields…',
    forecastLead: 'Plan your farming activities with confidence.',
    alertsLead: 'Stay informed and protect your crops.',
    features: [
      PersonaFeature(Icons.water_drop_outlined, 'Rainfall Forecast'),
      PersonaFeature(Icons.eco_outlined, 'Spraying Window'),
      PersonaFeature(Icons.agriculture_outlined, 'Harvest Timing'),
      PersonaFeature(Icons.wb_sunny_outlined, 'Heat & UV'),
    ],
    quickActions: [
      PersonaQuestion(
        Icons.umbrella_outlined,
        'Will it rain today in {city}?',
        label: 'Will it rain on my fields today?',
      ),
      PersonaQuestion(
        Icons.water_drop_outlined,
        'How much rain so far today in {city}?',
        label: 'How much rain has fallen today?',
      ),
      PersonaQuestion(Icons.calendar_month_outlined, '5-day forecast for {city}', label: '5-day farm forecast'),
    ],
    suggestions: [
      PersonaQuestion(Icons.eco_outlined, 'Will it rain tomorrow in {city}?'),
      PersonaQuestion(Icons.eco_outlined, 'How much rain so far today in {city}?'),
      PersonaQuestion(Icons.eco_outlined, 'How hot will it be tomorrow in {city}?'),
      PersonaQuestion(Icons.eco_outlined, '5-day forecast for {city}'),
    ],
  ),
  Persona(
    'fisherman',
    'Fisherman',
    Icons.sailing,
    tagline: 'Fishing, marine & coastal weather planning.',
    blurb: 'Wind and rain framed around going out to sea.',
    role: 'Fisherman',
    homeLead: "Here's the latest weather for your sea operations.",
    chatLead: 'Get accurate weather insights with real-time data and evidence for your trips out to sea.',
    askHint: 'Ask a question about the sea weather…',
    forecastLead: 'Plan your fishing trips with confidence.',
    alertsLead: 'Stay informed and stay safe at sea.',
    features: [
      PersonaFeature(Icons.air, 'Wind Conditions'),
      PersonaFeature(Icons.grain, 'Rain Chance'),
      PersonaFeature(Icons.calendar_month_outlined, 'Calmest Day'),
      PersonaFeature(Icons.warning_amber_rounded, 'IMD Warnings'),
    ],
    quickActions: [
      PersonaQuestion(Icons.air, 'What are the winds like now in {city}?', label: 'How windy is it right now?'),
      PersonaQuestion(Icons.umbrella_outlined, 'Will it rain tomorrow in {city}?', label: 'Will it rain tomorrow?'),
      PersonaQuestion(Icons.calendar_month_outlined, '5-day forecast for {city}', label: '5-day forecast'),
    ],
    suggestions: [
      PersonaQuestion(Icons.waves, 'Will it rain tomorrow in {city}?'),
      PersonaQuestion(Icons.waves, 'How strong will the winds be tomorrow in {city}?'),
      PersonaQuestion(Icons.waves, 'Any weather warnings for {city}?'),
      PersonaQuestion(Icons.waves, '5-day forecast for {city}'),
    ],
  ),
  Persona(
    'aviation',
    'Aviation',
    Icons.flight,
    tagline: 'Flight operations and aviation weather.',
    blurb: 'Wind and visibility-relevant briefing language.',
    role: 'Pilot',
    homeLead: "Here's the latest weather for your flight operations.",
    chatLead: 'Get accurate weather insights with real-time data and evidence for your flight planning.',
    askHint: 'Ask a question about the weather…',
    forecastLead: 'Plan your flight with confidence.',
    alertsLead: 'Stay informed and fly safe.',
    features: [
      PersonaFeature(Icons.air, 'Wind & Direction'),
      PersonaFeature(Icons.foggy, 'Fog & Haze'),
      PersonaFeature(Icons.thunderstorm_outlined, 'Storm Watch'),
      PersonaFeature(Icons.flight_takeoff, 'Ops Impacts'),
    ],
    quickActions: [
      PersonaQuestion(Icons.air, 'What are the winds like now in {city}?', label: 'Current wind conditions'),
      PersonaQuestion(
        Icons.thunderstorm_outlined,
        'Will it rain this evening in {city}?',
        label: 'Any rain for evening departures?',
      ),
      PersonaQuestion(Icons.flight, 'METAR and TAF for {city} airport', label: 'Airport METAR and TAF'),
    ],
    suggestions: [
      PersonaQuestion(Icons.flight, 'METAR for {city} airport'),
      PersonaQuestion(Icons.flight, 'What are the winds like now in {city}?'),
      PersonaQuestion(Icons.flight, 'Any weather warnings for {city}?'),
      PersonaQuestion(Icons.flight, '5-day forecast for {city}'),
    ],
  ),
  Persona(
    'city_official',
    'City Official',
    Icons.account_balance,
    tagline: 'Safer cities, stronger communities.',
    blurb: 'Direct, operational public-safety framing.',
    role: 'Officer',
    homeLead: "Here's the latest weather and city updates for your operations.",
    chatLead:
        'Get accurate weather insights and city-level forecasts, backed by real-time data and official '
        'sources.',
    askHint: "Ask a question about the city's weather…",
    forecastLead: 'Plan your city operations with confidence.',
    alertsLead: 'Stay informed and keep the city safe.',
    features: [
      PersonaFeature(Icons.flood_outlined, 'Waterlogging'),
      PersonaFeature(Icons.thermostat, 'Heat Exposure'),
      PersonaFeature(Icons.air, 'Wind Hazards'),
      PersonaFeature(Icons.groups_outlined, 'Operational Outlook'),
    ],
    quickActions: [
      PersonaQuestion(
        Icons.location_city_outlined,
        'What is the weather now in {city}?',
        label: 'Check weather impact on the city',
      ),
      PersonaQuestion(
        Icons.warning_amber_rounded,
        'Any weather warnings for {city}?',
        label: 'View active alerts & advisories',
      ),
      PersonaQuestion(
        Icons.water_drop_outlined,
        'How much rain so far today in {city}?',
        label: 'Rainfall so far today',
      ),
    ],
    suggestions: [
      PersonaQuestion(Icons.settings_suggest_outlined, 'Any weather warnings for {city}?'),
      PersonaQuestion(Icons.settings_suggest_outlined, 'How much rain so far today in {city}?'),
      PersonaQuestion(Icons.settings_suggest_outlined, 'How hot will it be tomorrow in {city}?'),
      PersonaQuestion(Icons.settings_suggest_outlined, '5-day forecast for {city}'),
    ],
  ),
];

Persona personaById(String id) => kPersonas.firstWhere((p) => p.id == id, orElse: () => kPersonas.first);

class UiPrefs extends ChangeNotifier {
  String _lang = 'en';
  TempUnit _unit = TempUnit.celsius;
  String _city = 'chennai';
  String _persona = 'general';
  Appearance _appearance = Appearance.light;
  List<City> _cities = kCities;

  /// A saved city the current list doesn't have yet — one the server added
  /// after this build's bundled list. It is selected if the server's list
  /// (set [cities]) has it, and saved meanwhile so it isn't forgotten.
  String? _wantedCity;

  String get lang => _lang;
  TempUnit get unit => _unit;
  String get city => _city;
  String get persona => _persona;
  Appearance get appearance => _appearance;
  City get cityInfo => cityByKey(_city, _cities);

  /// The cities to offer: the server's (GET /cities) once it has answered,
  /// the bundled list until then or if it never does.
  List<City> get cities => _cities;
  Persona get personaInfo => personaById(_persona);

  set lang(String v) => _set(() => _lang = v, _lang != v);
  set unit(TempUnit v) => _set(() => _unit = v, _unit != v);
  set city(String v) => _set(() {
    _city = v;
    _wantedCity = null;
  }, _city != v || _wantedCity != null);
  set persona(String v) => _set(() => _persona = v, _persona != v);
  set appearance(Appearance v) => _set(() => _appearance = v, _appearance != v);

  ThemeMode get themeMode => switch (_appearance) {
    Appearance.light => ThemeMode.light,
    Appearance.dark => ThemeMode.dark,
    Appearance.system => ThemeMode.system,
  };

  /// Takes the server's city list. A city it doesn't serve can't stay
  /// selected — /ask and /warnings would refuse it — so the selection moves
  /// to the list's first city; a saved city the bundled list lacked is
  /// selected if the server has it.
  set cities(List<City> v) {
    if (v.isEmpty) return;
    final before = (_city, [for (final c in _cities) c.key]);
    _cities = List.unmodifiable(v);
    bool served(String? key) => key != null && v.any((c) => c.key == key);
    if (served(_wantedCity)) _city = _wantedCity!;
    _wantedCity = null;
    if (!served(_city)) _city = v.first.key;
    final after = (_city, [for (final c in _cities) c.key]);
    if (before.$1 != after.$1 || !listEquals(before.$2, after.$2)) notifyListeners();
  }

  void _set(VoidCallback apply, bool changed) {
    if (!changed) return;
    apply();
    notifyListeners();
  }

  /// What prefs_store.dart saves.
  Map<String, String> toSaved() => {
    'lang': _lang,
    'unit': _unit.name,
    'city': _wantedCity ?? _city,
    'persona': _persona,
    'appearance': _appearance.name,
  };

  /// Takes the settings from an earlier launch, except the [keep] keys (ones
  /// the user has changed since this launch began). A value this build
  /// doesn't know — a persona since removed, a hand-edited file — is skipped
  /// and that setting keeps its default; a city not in the current list waits
  /// for the server's list (see [cities]). One notification at most.
  void applySaved(Map<String, String> saved, {Set<String> keep = const {}}) {
    String? take(String key, bool Function(String) valid) {
      final v = saved[key];
      return v != null && !keep.contains(key) && valid(v) ? v : null;
    }

    final lang = take('lang', kLanguageLabels.containsKey);
    final unit = take('unit', (v) => TempUnit.values.any((u) => u.name == v));
    final city = take('city', (v) => v.isNotEmpty);
    final persona = take('persona', (v) => kPersonas.any((p) => p.id == v));
    final appearance = take('appearance', (v) => Appearance.values.any((a) => a.name == v));
    final before = toSaved();
    if (lang != null) _lang = lang;
    if (unit != null) _unit = TempUnit.values.byName(unit);
    if (city != null && _cities.any((c) => c.key == city)) {
      _city = city;
      _wantedCity = null;
    } else if (city != null) {
      _wantedCity = city;
    }
    if (persona != null) _persona = persona;
    if (appearance != null) _appearance = Appearance.values.byName(appearance);
    if (!mapEquals(before, toSaved())) notifyListeners();
  }

  String get unitSymbol => _unit == TempUnit.celsius ? 'C' : 'F';

  /// Just the converted number, for callers that style the unit separately.
  int temp(num celsius) => _unit == TempUnit.celsius ? celsius.round() : (celsius * 9 / 5 + 32).round();

  String tempLabel(num celsius) => '${temp(celsius)}°$unitSymbol';

  /// Subscribes the caller to changes.
  static UiPrefs of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<UiPrefsScope>()!.notifier!;

  /// For event handlers — no rebuild subscription.
  static UiPrefs read(BuildContext context) => context.getInheritedWidgetOfExactType<UiPrefsScope>()!.notifier!;
}

class UiPrefsScope extends InheritedNotifier<UiPrefs> {
  const UiPrefsScope({super.key, required UiPrefs prefs, required super.child}) : super(notifier: prefs);
}
