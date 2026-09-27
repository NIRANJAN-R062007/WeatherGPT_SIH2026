// App-wide UI preferences — the mobile twin of web/src/state/
// UiPrefsContext.tsx: language, temperature unit and the selected city, all
// shared so the Topbar's city picker and every page's /ask, /facts and
// /warnings calls stay in sync. Adds the persona flag, which web/'s Settings
// page shows but doesn't wire; here it reaches /ask's `persona` param.
// In-memory only, like web/.
import 'package:flutter/material.dart';

import '../cities.dart';

enum TempUnit { celsius, fahrenheit }

class Persona {
  final String id;
  final String label;
  final IconData icon;
  final String blurb;
  const Persona(this.id, this.label, this.icon, this.blurb);
}

/// Ids are services/orchestrator/persona.py's PERSONAS; blurbs paraphrase
/// its prompt hints, which only reframe the same facts.
const List<Persona> kPersonas = [
  Persona('general', 'General Citizen', Icons.person_outline, 'Plain-language current conditions and forecast.'),
  Persona('farmer', 'Farmer', Icons.agriculture_outlined, 'Whether conditions suit field work like spraying or harvest.'),
  Persona('fisherman', 'Fisherman', Icons.sailing_outlined, 'Wind and rain framed around going out to sea.'),
  Persona('aviation', 'Aviation', Icons.flight, 'Wind and visibility-relevant briefing language.'),
  Persona('city_official', 'City Official', Icons.apartment, 'Direct, operational public-safety framing.'),
];

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
