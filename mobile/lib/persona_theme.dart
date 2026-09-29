// Persona themes — the persona picked on the Persona page is the global
// theme selector: every page, the shell chrome, the painted scenery and the
// Material widgets (text fields, spinners, sheets, dialogs) read their
// colours from the active persona's [PersonaTheme]. One app, one widget
// tree; only the palette and the scene change. The palettes follow the
// pics/ persona mockups:
//   general       → blue / sky-blue, city skyline
//   farmer        → green, fields and crops
//   fisherman     → deep ocean blue, waves and boats
//   aviation      → purple + pink, airport and aircraft
//   city_official → teal / cyan, skyline, river and rain
//
// Wiring: main.dart rebuilds MaterialApp's theme from UiPrefs.persona via
// buildAppTheme(personaThemeFor(id)), which installs the PersonaTheme as a
// ThemeExtension — MaterialApp's AnimatedTheme then cross-fades every token
// through [PersonaTheme.lerp] when the persona changes. Widgets read it with
// `PersonaTheme.of(context)`.
//
// Dark mode: every persona also has a dark palette with the same field
// names (personaThemesDark, derived from the light one's hues — deep tinted
// night skies, lit windows, a moon instead of the sun). main.dart installs
// both and Settings > Appearance picks Light, Dark or the system setting.
// Persona-independent colours (errors, the LIVE/verified green, the sun,
// IMD warning colours) stay in AppColors / warning_colors.dart.
import 'package:flutter/material.dart';

/// Which painted landscape the persona's pages, headers and persona card use.
enum PersonaScene { city, fields, sea, airport, civic }

@immutable
class PersonaTheme extends ThemeExtension<PersonaTheme> {
  final Brightness brightness;
  final PersonaScene scene;

  /// The persona's badge in the top bar and brand spots (pics/ mockups:
  /// person, leaf, sailboat, plane, city hall).
  final IconData markIcon;

  /// Primary accent: buttons, selected states, links, active nav, icons.
  final Color primary;
  final Color onPrimary;

  /// A deeper shade of [primary] for pressed/strong text.
  final Color primaryContainer;

  /// Pale accent wash (pill buttons, highlighted chips) and the text on it.
  final Color primaryFixed;
  final Color onPrimaryFixed;

  /// Secondary accent — the second colour of gradients and highlights
  /// (sky-blue, lime, sea cyan, pink, cyan).
  final Color accent2;
  final Color accent2Soft;

  /// Page chrome: the sky gradient behind the top bar and the content sheet.
  final Color skyTop;
  final Color skyBottom;
  final Color sheet;
  final Color cloudPuff;

  /// Cards and their tinted fills.
  final Color card;
  final Color cardBorder;
  final Color tint;
  final Color tintStrong;

  /// Colour of card and chrome shadows (used at low alpha).
  final Color shadow;

  /// Text.
  final Color ink;
  final Color inkMuted;
  final Color onSurface;
  final Color onSurfaceVariant;
  final Color outline;
  final Color outlineVariant;

  /// Neutral panels (loading lines, chips, evidence panels).
  final Color surfaceContainerLowest;
  final Color surfaceContainerLow;
  final Color surfaceContainer;
  final Color surfaceContainerHigh;

  /// Bottom navigation.
  final Color navBar;
  final Color navIdle;

  /// Painted scenery: far and near silhouettes, lit windows / highlights,
  /// greenery, and two water (or haze) layers.
  final Color skylineFar;
  final Color skylineNear;
  final Color skylineWindow;
  final Color foliage;
  final Color foliageDeep;
  final Color water;
  final Color waterDeep;

  /// Weather glyph tints (the sun stays AppColors.sun on every persona).
  final Color cloudGlyph;
  final Color rainGlyph;
  final Color moonGlyph;

  const PersonaTheme({
    this.brightness = Brightness.light,
    required this.scene,
    required this.markIcon,
    required this.primary,
    this.onPrimary = const Color(0xFFFFFFFF),
    required this.primaryContainer,
    required this.primaryFixed,
    required this.onPrimaryFixed,
    required this.accent2,
    required this.accent2Soft,
    required this.skyTop,
    required this.skyBottom,
    required this.sheet,
    this.cloudPuff = const Color(0xFFFFFFFF),
    this.card = const Color(0xFFFFFFFF),
    required this.cardBorder,
    required this.tint,
    required this.tintStrong,
    required this.shadow,
    required this.ink,
    required this.inkMuted,
    required this.onSurface,
    required this.onSurfaceVariant,
    required this.outline,
    required this.outlineVariant,
    this.surfaceContainerLowest = const Color(0xFFFFFFFF),
    required this.surfaceContainerLow,
    required this.surfaceContainer,
    required this.surfaceContainerHigh,
    this.navBar = const Color(0xFFFFFFFF),
    required this.navIdle,
    required this.skylineFar,
    required this.skylineNear,
    required this.skylineWindow,
    required this.foliage,
    required this.foliageDeep,
    required this.water,
    required this.waterDeep,
    required this.cloudGlyph,
    required this.rainGlyph,
    required this.moonGlyph,
  });

  /// The active persona's theme. Falls back to General Citizen outside a
  /// themed MaterialApp (e.g. a bare widget test).
  static PersonaTheme of(BuildContext context) =>
      Theme.of(context).extension<PersonaTheme>() ?? personaThemes['general']!;

  bool get isDark => brightness == Brightness.dark;

  /// The solid-looking accent fill of buttons, the selected switch pill, the
  /// question bubble and persona discs (a slight primary → deeper-primary
  /// fall, as in the mockups).
  LinearGradient get accentGradient => LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, Color.lerp(primary, primaryContainer, 0.55)!],
  );

  /// The page background behind the top bar and sheet.
  LinearGradient get skyGradient => LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [skyTop, skyBottom],
    stops: const [0, 0.35],
  );

  List<BoxShadow> get cardShadow => [
    BoxShadow(
      color: shadow.withValues(alpha: isDark ? 0.35 : 0.08),
      blurRadius: 12,
      offset: const Offset(0, 3),
    ),
  ];

  @override
  PersonaTheme copyWith({PersonaScene? scene}) => PersonaTheme(
    brightness: brightness,
    scene: scene ?? this.scene,
    markIcon: markIcon,
    primary: primary,
    onPrimary: onPrimary,
    primaryContainer: primaryContainer,
    primaryFixed: primaryFixed,
    onPrimaryFixed: onPrimaryFixed,
    accent2: accent2,
    accent2Soft: accent2Soft,
    skyTop: skyTop,
    skyBottom: skyBottom,
    sheet: sheet,
    cloudPuff: cloudPuff,
    card: card,
    cardBorder: cardBorder,
    tint: tint,
    tintStrong: tintStrong,
    shadow: shadow,
    ink: ink,
    inkMuted: inkMuted,
    onSurface: onSurface,
    onSurfaceVariant: onSurfaceVariant,
    outline: outline,
    outlineVariant: outlineVariant,
    surfaceContainerLowest: surfaceContainerLowest,
    surfaceContainerLow: surfaceContainerLow,
    surfaceContainer: surfaceContainer,
    surfaceContainerHigh: surfaceContainerHigh,
    navBar: navBar,
    navIdle: navIdle,
    skylineFar: skylineFar,
    skylineNear: skylineNear,
    skylineWindow: skylineWindow,
    foliage: foliage,
    foliageDeep: foliageDeep,
    water: water,
    waterDeep: waterDeep,
    cloudGlyph: cloudGlyph,
    rainGlyph: rainGlyph,
    moonGlyph: moonGlyph,
  );

  /// Cross-fades every colour; the scene swaps at the midpoint.
  @override
  PersonaTheme lerp(covariant PersonaTheme? other, double t) {
    if (other == null) return this;
    Color c(Color a, Color b) => Color.lerp(a, b, t)!;
    return PersonaTheme(
      brightness: t < 0.5 ? brightness : other.brightness,
      scene: t < 0.5 ? scene : other.scene,
      markIcon: t < 0.5 ? markIcon : other.markIcon,
      primary: c(primary, other.primary),
      onPrimary: c(onPrimary, other.onPrimary),
      primaryContainer: c(primaryContainer, other.primaryContainer),
      primaryFixed: c(primaryFixed, other.primaryFixed),
      onPrimaryFixed: c(onPrimaryFixed, other.onPrimaryFixed),
      accent2: c(accent2, other.accent2),
      accent2Soft: c(accent2Soft, other.accent2Soft),
      skyTop: c(skyTop, other.skyTop),
      skyBottom: c(skyBottom, other.skyBottom),
      sheet: c(sheet, other.sheet),
      cloudPuff: c(cloudPuff, other.cloudPuff),
      card: c(card, other.card),
      cardBorder: c(cardBorder, other.cardBorder),
      tint: c(tint, other.tint),
      tintStrong: c(tintStrong, other.tintStrong),
      shadow: c(shadow, other.shadow),
      ink: c(ink, other.ink),
      inkMuted: c(inkMuted, other.inkMuted),
      onSurface: c(onSurface, other.onSurface),
      onSurfaceVariant: c(onSurfaceVariant, other.onSurfaceVariant),
      outline: c(outline, other.outline),
      outlineVariant: c(outlineVariant, other.outlineVariant),
      surfaceContainerLowest: c(surfaceContainerLowest, other.surfaceContainerLowest),
      surfaceContainerLow: c(surfaceContainerLow, other.surfaceContainerLow),
      surfaceContainer: c(surfaceContainer, other.surfaceContainer),
      surfaceContainerHigh: c(surfaceContainerHigh, other.surfaceContainerHigh),
      navBar: c(navBar, other.navBar),
      navIdle: c(navIdle, other.navIdle),
      skylineFar: c(skylineFar, other.skylineFar),
      skylineNear: c(skylineNear, other.skylineNear),
      skylineWindow: c(skylineWindow, other.skylineWindow),
      foliage: c(foliage, other.foliage),
      foliageDeep: c(foliageDeep, other.foliageDeep),
      water: c(water, other.water),
      waterDeep: c(waterDeep, other.waterDeep),
      cloudGlyph: c(cloudGlyph, other.cloudGlyph),
      rainGlyph: c(rainGlyph, other.rainGlyph),
      moonGlyph: c(moonGlyph, other.moonGlyph),
    );
  }
}

/// Light palettes, keyed by persona id (services/orchestrator/persona.py),
/// sampled from the pics/ persona mockups.
const Map<String, PersonaTheme> personaThemes = {
  // Blue / sky-blue, a dense city skyline — calm everyday weather.
  'general': PersonaTheme(
    scene: PersonaScene.city,
    markIcon: Icons.person,
    primary: Color(0xFF1E63D6),
    primaryContainer: Color(0xFF1450B5),
    primaryFixed: Color(0xFFDCE8FF),
    onPrimaryFixed: Color(0xFF0A2D6E),
    accent2: Color(0xFF4FA3F7),
    accent2Soft: Color(0xFFE3F1FE),
    skyTop: Color(0xFFC6DEFA),
    skyBottom: Color(0xFFEAF3FE),
    sheet: Color(0xFFF5F9FF),
    cardBorder: Color(0xFFD9E6F7),
    tint: Color(0xFFE7F0FE),
    tintStrong: Color(0xFFD2E3FC),
    shadow: Color(0xFF1E63D6),
    ink: Color(0xFF0F2548),
    inkMuted: Color(0xFF566783),
    onSurface: Color(0xFF0B1F3F),
    onSurfaceVariant: Color(0xFF3E4C63),
    outline: Color(0xFF6F7C92),
    outlineVariant: Color(0xFFC3CEDF),
    surfaceContainerLow: Color(0xFFF0F5FE),
    surfaceContainer: Color(0xFFE6EEFC),
    surfaceContainerHigh: Color(0xFFDCE7FA),
    navIdle: Color(0xFF6B7A93),
    skylineFar: Color(0xFFB3D0F3),
    skylineNear: Color(0xFF5E9BE6),
    skylineWindow: Color(0xFFE3EEFC),
    foliage: Color(0xFF7DC36B),
    foliageDeep: Color(0xFF4E9E55),
    water: Color(0xFFCFE2FA),
    waterDeep: Color(0xFFAFCDF3),
    cloudGlyph: Color(0xFF7EACEB),
    rainGlyph: Color(0xFF3F7FE0),
    moonGlyph: Color(0xFF5D6FC4),
  ),
  // Fresh green, fields, crop rows, leafy edges and a tractor.
  'farmer': PersonaTheme(
    scene: PersonaScene.fields,
    markIcon: Icons.eco,
    primary: Color(0xFF2E7D32),
    primaryContainer: Color(0xFF1B5E20),
    primaryFixed: Color(0xFFD6EED3),
    onPrimaryFixed: Color(0xFF0E3B13),
    accent2: Color(0xFF8BC34A),
    accent2Soft: Color(0xFFEEF7DC),
    skyTop: Color(0xFFD5EED0),
    skyBottom: Color(0xFFF0F8EC),
    sheet: Color(0xFFF6FBF3),
    cardBorder: Color(0xFFD4E9CF),
    tint: Color(0xFFE6F4E2),
    tintStrong: Color(0xFFCDE8C6),
    shadow: Color(0xFF2E7D32),
    ink: Color(0xFF15301B),
    inkMuted: Color(0xFF566E5B),
    onSurface: Color(0xFF10281A),
    onSurfaceVariant: Color(0xFF3D5343),
    outline: Color(0xFF6D8272),
    outlineVariant: Color(0xFFC0D5C2),
    surfaceContainerLow: Color(0xFFEFF7EC),
    surfaceContainer: Color(0xFFE3F1DE),
    surfaceContainerHigh: Color(0xFFD7EBD1),
    navIdle: Color(0xFF6A8270),
    skylineFar: Color(0xFFB5DBA3),
    skylineNear: Color(0xFF8CC152),
    skylineWindow: Color(0xFFE6F3B4),
    foliage: Color(0xFF5DAA45),
    foliageDeep: Color(0xFF2F7D32),
    water: Color(0xFFCDE8B0),
    waterDeep: Color(0xFFA5D27E),
    cloudGlyph: Color(0xFF86B3DD),
    rainGlyph: Color(0xFF3F7FE0),
    moonGlyph: Color(0xFF5D6FC4),
  ),
  // Ocean blue, bright swells, a trawler, gulls and a lighthouse.
  'fisherman': PersonaTheme(
    scene: PersonaScene.sea,
    markIcon: Icons.sailing,
    primary: Color(0xFF1565C0),
    primaryContainer: Color(0xFF0D47A1),
    primaryFixed: Color(0xFFD4E6FA),
    onPrimaryFixed: Color(0xFF062B5C),
    accent2: Color(0xFF29A8E0),
    accent2Soft: Color(0xFFDDF1FB),
    skyTop: Color(0xFFC3E1F8),
    skyBottom: Color(0xFFE7F3FC),
    sheet: Color(0xFFF3F9FE),
    cardBorder: Color(0xFFD0E4F5),
    tint: Color(0xFFE1EFFB),
    tintStrong: Color(0xFFC9E1F7),
    shadow: Color(0xFF1565C0),
    ink: Color(0xFF0B2342),
    inkMuted: Color(0xFF4E657F),
    onSurface: Color(0xFF081D38),
    onSurfaceVariant: Color(0xFF384C63),
    outline: Color(0xFF687B90),
    outlineVariant: Color(0xFFBDCFE1),
    surfaceContainerLow: Color(0xFFEDF5FC),
    surfaceContainer: Color(0xFFE0EDF9),
    surfaceContainerHigh: Color(0xFFD5E6F6),
    navIdle: Color(0xFF667C93),
    skylineFar: Color(0xFFA9CDEB),
    skylineNear: Color(0xFF7FB2DE),
    skylineWindow: Color(0xFFFFFFFF),
    foliage: Color(0xFF7FB89A),
    foliageDeep: Color(0xFF4F8F72),
    water: Color(0xFF55A8E8),
    waterDeep: Color(0xFF1766C2),
    cloudGlyph: Color(0xFF76A8E0),
    rainGlyph: Color(0xFF2F6FD0),
    moonGlyph: Color(0xFF4E63B8),
  ),
  // Purple + pink: lavender sky, pink clouds, tower, terminal and a jet.
  'aviation': PersonaTheme(
    scene: PersonaScene.airport,
    markIcon: Icons.flight,
    primary: Color(0xFF5B3CC4),
    primaryContainer: Color(0xFF452A9E),
    primaryFixed: Color(0xFFE5DCFA),
    onPrimaryFixed: Color(0xFF26135F),
    accent2: Color(0xFFE36BAE),
    accent2Soft: Color(0xFFFBE3F1),
    skyTop: Color(0xFFD8CAF6),
    skyBottom: Color(0xFFF6ECF9),
    sheet: Color(0xFFFAF6FE),
    cloudPuff: Color(0xFFFCE8F4),
    cardBorder: Color(0xFFE5DAF6),
    tint: Color(0xFFEFE8FC),
    tintStrong: Color(0xFFE0D3F8),
    shadow: Color(0xFF5B3CC4),
    ink: Color(0xFF21174A),
    inkMuted: Color(0xFF635D86),
    onSurface: Color(0xFF1C1340),
    onSurfaceVariant: Color(0xFF484266),
    outline: Color(0xFF7A7494),
    outlineVariant: Color(0xFFCCC4E0),
    surfaceContainerLow: Color(0xFFF5F0FE),
    surfaceContainer: Color(0xFFEDE6FC),
    surfaceContainerHigh: Color(0xFFE4DBF9),
    navIdle: Color(0xFF79739A),
    skylineFar: Color(0xFFD1C1F0),
    skylineNear: Color(0xFF9A82DC),
    skylineWindow: Color(0xFFF5EEFF),
    foliage: Color(0xFFF1B9DA),
    foliageDeep: Color(0xFFD3A0E6),
    water: Color(0xFFE9DCF8),
    waterDeep: Color(0xFFD6C2F2),
    cloudGlyph: Color(0xFF9C8CE3),
    rainGlyph: Color(0xFF6B55D6),
    moonGlyph: Color(0xFF6A4FC9),
  ),
  // Teal / cyan, a civic skyline with the city hall, trees, river and rain.
  'city_official': PersonaTheme(
    scene: PersonaScene.civic,
    markIcon: Icons.account_balance,
    primary: Color(0xFF0E7C86),
    primaryContainer: Color(0xFF085E66),
    primaryFixed: Color(0xFFCDEDEE),
    onPrimaryFixed: Color(0xFF033A3F),
    accent2: Color(0xFF26B5C9),
    accent2Soft: Color(0xFFDAF3F6),
    skyTop: Color(0xFFC5E9EB),
    skyBottom: Color(0xFFE8F6F6),
    sheet: Color(0xFFF3FAFA),
    cardBorder: Color(0xFFCFE8E8),
    tint: Color(0xFFE0F2F2),
    tintStrong: Color(0xFFC6E8E9),
    shadow: Color(0xFF0E7C86),
    ink: Color(0xFF0C2E32),
    inkMuted: Color(0xFF4F6E6F),
    onSurface: Color(0xFF09272B),
    onSurfaceVariant: Color(0xFF385356),
    outline: Color(0xFF678385),
    outlineVariant: Color(0xFFBAD5D6),
    surfaceContainerLow: Color(0xFFECF7F7),
    surfaceContainer: Color(0xFFDFF1F1),
    surfaceContainerHigh: Color(0xFFD3EBEB),
    navIdle: Color(0xFF65807F),
    skylineFar: Color(0xFFADD6DD),
    skylineNear: Color(0xFF5AA6B8),
    skylineWindow: Color(0xFFE1F4F6),
    foliage: Color(0xFF7CC17F),
    foliageDeep: Color(0xFF3F8F5A),
    water: Color(0xFFA6DAE3),
    waterDeep: Color(0xFF6ABCCB),
    cloudGlyph: Color(0xFF70B2C8),
    rainGlyph: Color(0xFF1E86B8),
    moonGlyph: Color(0xFF4D6BB5),
  ),
};

/// Night twin of a light palette: the same hues on deep tinted surfaces,
/// light accents with dark text on them, dimmed scenery with lit windows.
PersonaTheme _darkOf(PersonaTheme l) {
  double hueOf(Color c) => HSLColor.fromColor(c).hue;
  final h = hueOf(l.primary);
  Color c(double sat, double light, [double? hue]) => HSLColor.fromAHSL(1, hue ?? h, sat, light).toColor();
  final hA = hueOf(l.accent2);
  return PersonaTheme(
    brightness: Brightness.dark,
    scene: l.scene,
    markIcon: l.markIcon,
    primary: c(0.78, 0.74),
    onPrimary: c(0.6, 0.12),
    primaryContainer: c(0.55, 0.56),
    primaryFixed: c(0.4, 0.25),
    onPrimaryFixed: c(0.6, 0.88),
    accent2: c(0.75, 0.72, hA),
    accent2Soft: c(0.35, 0.2, hA),
    skyTop: c(0.42, 0.15),
    skyBottom: c(0.4, 0.09),
    sheet: c(0.34, 0.11),
    cloudPuff: c(0.22, 0.3),
    card: c(0.28, 0.155),
    cardBorder: c(0.26, 0.24),
    tint: c(0.36, 0.19),
    tintStrong: c(0.4, 0.25),
    shadow: const Color(0xFF000000),
    ink: c(0.3, 0.92),
    inkMuted: c(0.16, 0.7),
    onSurface: c(0.25, 0.93),
    onSurfaceVariant: c(0.16, 0.78),
    outline: c(0.12, 0.55),
    outlineVariant: c(0.2, 0.28),
    surfaceContainerLowest: c(0.28, 0.155),
    surfaceContainerLow: c(0.3, 0.13),
    surfaceContainer: c(0.3, 0.17),
    surfaceContainerHigh: c(0.3, 0.21),
    navBar: c(0.32, 0.12),
    navIdle: c(0.14, 0.62),
    skylineFar: c(0.3, 0.2),
    skylineNear: c(0.36, 0.3),
    skylineWindow: const Color(0xFFFFD27A),
    foliage: c(0.32, 0.26, hueOf(l.foliage)),
    foliageDeep: c(0.32, 0.18, hueOf(l.foliageDeep)),
    water: c(0.42, 0.26, hueOf(l.water)),
    waterDeep: c(0.42, 0.18, hueOf(l.waterDeep)),
    cloudGlyph: c(0.55, 0.72, hueOf(l.cloudGlyph)),
    rainGlyph: c(0.8, 0.68, hueOf(l.rainGlyph)),
    moonGlyph: const Color(0xFFD9DEFF),
  );
}

/// Dark palettes, same keys as [personaThemes].
final Map<String, PersonaTheme> personaThemesDark = {for (final e in personaThemes.entries) e.key: _darkOf(e.value)};

/// The palette for a persona id; unknown ids get General Citizen's.
PersonaTheme personaThemeFor(String id, [Brightness brightness = Brightness.light]) {
  final map = brightness == Brightness.dark ? personaThemesDark : personaThemes;
  return map[id] ?? map['general']!;
}
