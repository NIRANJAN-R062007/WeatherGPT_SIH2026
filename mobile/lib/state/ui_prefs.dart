// App-wide UI preferences — the mobile twin of web/src/state/
// UiPrefsContext.tsx: language, temperature unit and the selected city, all
// shared so the Topbar's city picker and every page's /ask, /facts and
// /warnings calls stay in sync. Adds the persona flag, which web/'s Settings
// page shows but doesn't wire; here it reaches /ask's `persona` param.
// In-memory only, like web/.
import 'package:flutter/material.dart';

import '../cities.dart';
import '../theme.dart';

enum TempUnit { celsius, fahrenheit }

/// One of a persona card's four focus chips.
class PersonaFeature {
  final IconData icon;
  final String label;
  const PersonaFeature(this.icon, this.label);
}

/// Which painted scene sits behind a persona card (persona_page.dart).
enum PersonaScene { city, fields, sea, sky, river }

class Persona {
  final String id;
  final String label;
  final IconData icon;

  /// One line under the name — Settings' profile card and the compact list.
  final String tagline;

  /// What the framing does; persona.py's hint, paraphrased.
  final String blurb;
  final Color accent;
  final Color soft;
  final PersonaScene scene;

  /// What persona.py's hint actually frames — nothing it is told never to
  /// mention (soil, crops, sea state, visibility, runway data, safety
  /// verdicts), so a chip never promises data the answers can't carry.
  final List<PersonaFeature> features;

  const Persona(
    this.id,
    this.label,
    this.icon, {
    required this.tagline,
    required this.blurb,
    required this.accent,
    required this.soft,
    required this.scene,
    required this.features,
  });
}

/// Ids are services/orchestrator/persona.py's PERSONAS; blurbs paraphrase
/// its prompt hints, which only reframe the same facts.
const List<Persona> kPersonas = [
  Persona(
    'general',
    'General Citizen',
    Icons.person,
    tagline: 'Everyday weather, for your life.',
    blurb: 'Plain-language current conditions and forecast.',
    accent: AppColors.personaGeneral,
    soft: AppColors.personaGeneralSoft,
    scene: PersonaScene.city,
    features: [
      PersonaFeature(Icons.wb_sunny_outlined, 'Daily Forecast'),
      PersonaFeature(Icons.umbrella_outlined, 'Rain Chance'),
      PersonaFeature(Icons.air, 'Wind Updates'),
      PersonaFeature(Icons.warning_amber_rounded, 'IMD Warnings'),
    ],
  ),
  Persona(
    'farmer',
    'Farmer',
    Icons.spa,
    tagline: 'Better decisions for your crops.',
    blurb: 'Whether conditions suit field work like spraying or harvest.',
    accent: AppColors.personaFarmer,
    soft: AppColors.personaFarmerSoft,
    scene: PersonaScene.fields,
    features: [
      PersonaFeature(Icons.water_drop_outlined, 'Rainfall Forecast'),
      PersonaFeature(Icons.eco_outlined, 'Spraying Window'),
      PersonaFeature(Icons.agriculture_outlined, 'Harvest Timing'),
      PersonaFeature(Icons.wb_sunny_outlined, 'Heat & UV'),
    ],
  ),
  Persona(
    'fisherman',
    'Fisherman',
    Icons.sailing,
    tagline: 'Wind and rain framed around going out to sea.',
    blurb: 'Wind and rain framed around going out to sea.',
    accent: AppColors.personaFisherman,
    soft: AppColors.personaFishermanSoft,
    scene: PersonaScene.sea,
    features: [
      PersonaFeature(Icons.air, 'Wind Conditions'),
      PersonaFeature(Icons.grain, 'Rain Chance'),
      PersonaFeature(Icons.calendar_month_outlined, 'Calmest Day'),
      PersonaFeature(Icons.warning_amber_rounded, 'IMD Warnings'),
    ],
  ),
  Persona(
    'aviation',
    'Aviation',
    Icons.flight,
    tagline: 'Wind and weather that matter to flight ops.',
    blurb: 'Wind and visibility-relevant briefing language.',
    accent: AppColors.personaAviation,
    soft: AppColors.personaAviationSoft,
    scene: PersonaScene.sky,
    features: [
      PersonaFeature(Icons.air, 'Wind & Direction'),
      PersonaFeature(Icons.foggy, 'Fog & Haze'),
      PersonaFeature(Icons.thunderstorm_outlined, 'Storm Watch'),
      PersonaFeature(Icons.flight_takeoff, 'Ops Impacts'),
    ],
  ),
  Persona(
    'city_official',
    'City Official',
    Icons.account_balance,
    tagline: 'Safer cities, stronger communities.',
    blurb: 'Direct, operational public-safety framing.',
    accent: AppColors.personaCity,
    soft: AppColors.personaCitySoft,
    scene: PersonaScene.river,
    features: [
      PersonaFeature(Icons.flood_outlined, 'Waterlogging'),
      PersonaFeature(Icons.thermostat, 'Heat Exposure'),
      PersonaFeature(Icons.air, 'Wind Hazards'),
      PersonaFeature(Icons.groups_outlined, 'Operational Outlook'),
    ],
  ),
];

Persona personaById(String id) => kPersonas.firstWhere((p) => p.id == id, orElse: () => kPersonas.first);

class UiPrefs extends ChangeNotifier {
  String _lang = 'en';
  TempUnit _unit = TempUnit.celsius;
  String _city = 'chennai';
  String _persona = 'general';

  String get lang => _lang;
  TempUnit get unit => _unit;
  String get city => _city;
  String get persona => _persona;
  City get cityInfo => cityByKey(_city);
  Persona get personaInfo => personaById(_persona);

  set lang(String v) => _set(() => _lang = v, _lang != v);
  set unit(TempUnit v) => _set(() => _unit = v, _unit != v);
  set city(String v) => _set(() => _city = v, _city != v);
  set persona(String v) => _set(() => _persona = v, _persona != v);

  void _set(VoidCallback apply, bool changed) {
    if (!changed) return;
    apply();
    notifyListeners();
  }

  String get unitSymbol => _unit == TempUnit.celsius ? 'C' : 'F';

  /// Just the converted number, for callers that style the unit separately.
  int temp(num celsius) =>
      _unit == TempUnit.celsius ? celsius.round() : (celsius * 9 / 5 + 32).round();

  String tempLabel(num celsius) => '${temp(celsius)}°$unitSymbol';

  /// Subscribes the caller to changes.
  static UiPrefs of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<UiPrefsScope>()!.notifier!;

  /// For event handlers — no rebuild subscription.
  static UiPrefs read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<UiPrefsScope>()!.notifier!;
}

class UiPrefsScope extends InheritedNotifier<UiPrefs> {
  const UiPrefsScope({super.key, required UiPrefs prefs, required super.child})
      : super(notifier: prefs);
}
