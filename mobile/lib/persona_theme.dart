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
// Dark mode: only light palettes exist today. A dark palette is one more
// PersonaTheme per persona with the same field names (brightness: dark);
// personaThemeFor gains a Brightness argument and nothing else changes.
// Persona-independent colours (errors, the LIVE/verified green, the sun,
// IMD warning colours) stay in AppColors / warning_colors.dart.
import 'package:flutter/material.dart';

/// Which painted landscape the persona's pages, headers and persona card use.
enum PersonaScene { city, fields, sea, airport, civic }

@immutable
class PersonaTheme extends ThemeExtension<PersonaTheme> {
  final Brightness brightness;
  final PersonaScene scene;

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

  /// Primary → secondary accent: send button, selected switch pill, the
  /// question bubble, the persona avatar.
  LinearGradient get accentGradient => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [primary, Color.lerp(primary, accent2, 0.6)!],
      );

  /// The page background behind the top bar and sheet.
  LinearGradient get skyGradient => LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [skyTop, skyBottom],
        stops: const [0, 0.35],
      );

  List<BoxShadow> get cardShadow => [BoxShadow(color: shadow.withValues(alpha: 0.08), blurRadius: 12, offset: const Offset(0, 3))];

  @override
  PersonaTheme copyWith({PersonaScene? scene}) => PersonaTheme(
        brightness: brightness,
        scene: scene ?? this.scene,
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

/// Light palettes, keyed by persona id (services/orchestrator/persona.py).
const Map<String, PersonaTheme> personaThemes = {
  // Blue / sky-blue, city skyline — the calm everyday look.
  'general': PersonaTheme(
    scene: PersonaScene.city,
    primary: Color(0xFF1D6AE5),
    primaryContainer: Color(0xFF0B4DB8),
    primaryFixed: Color(0xFFD9E6FF),
    onPrimaryFixed: Color(0xFF0A2D6E),
    accent2: Color(0xFF3AA8F5),
    accent2Soft: Color(0xFFE1F2FE),
    skyTop: Color(0xFFCBDFFB),
    skyBottom: Color(0xFFE9F1FE),
    sheet: Color(0xFFF6F9FF),
    cardBorder: Color(0xFFDCE7F8),
    tint: Color(0xFFE8F1FF),
    tintStrong: Color(0xFFD3E4FF),
    shadow: Color(0xFF1D6AE5),
    ink: Color(0xFF10264A),
    inkMuted: Color(0xFF5A6A86),
    onSurface: Color(0xFF041B3C),
    onSurfaceVariant: Color(0xFF414755),
    outline: Color(0xFF727786),
    outlineVariant: Color(0xFFC1C6D7),
    surfaceContainerLow: Color(0xFFF1F3FF),
    surfaceContainer: Color(0xFFE8EDFF),
    surfaceContainerHigh: Color(0xFFE0E8FF),
    navIdle: Color(0xFF6E7C95),
    skylineFar: Color(0xFFC3D8F5),
    skylineNear: Color(0xFF94BBEE),
    skylineWindow: Color(0xFFE6EFFD),
    foliage: Color(0xFF93C48F),
    foliageDeep: Color(0xFF63A56E),
    water: Color(0xFFD2E3FA),
    waterDeep: Color(0xFFB9D2F5),
    cloudGlyph: Color(0xFF7EACEB),
    rainGlyph: Color(0xFF3F7FE0),
    moonGlyph: Color(0xFF5D6FC4),
  ),
  // Fresh green, fields and crop rows.
  'farmer': PersonaTheme(
    scene: PersonaScene.fields,
    primary: Color(0xFF2E8B45),
    primaryContainer: Color(0xFF1D6B32),
    primaryFixed: Color(0xFFD5EFD9),
    onPrimaryFixed: Color(0xFF0F3D1C),
    accent2: Color(0xFF8CC63F),
    accent2Soft: Color(0xFFEEF7DF),
    skyTop: Color(0xFFD3EDD6),
    skyBottom: Color(0xFFEEF8EC),
    sheet: Color(0xFFF7FBF4),
    cardBorder: Color(0xFFD8EBD5),
    tint: Color(0xFFE7F5E6),
    tintStrong: Color(0xFFCFEACF),
    shadow: Color(0xFF2E8B45),
    ink: Color(0xFF16301E),
    inkMuted: Color(0xFF587062),
    onSurface: Color(0xFF12291A),
    onSurfaceVariant: Color(0xFF3F5446),
    outline: Color(0xFF6F8474),
    outlineVariant: Color(0xFFC2D5C4),
    surfaceContainerLow: Color(0xFFF0F8EE),
    surfaceContainer: Color(0xFFE5F2E2),
    surfaceContainerHigh: Color(0xFFDAECD7),
    navIdle: Color(0xFF6E8574),
    skylineFar: Color(0xFFBFE0B5),
    skylineNear: Color(0xFF86C466),
    skylineWindow: Color(0xFFE6F3C4),
    foliage: Color(0xFF63AE52),
    foliageDeep: Color(0xFF3E8A3E),
    water: Color(0xFFCBE7B5),
    waterDeep: Color(0xFFA8D58A),
    cloudGlyph: Color(0xFF86B3DD),
    rainGlyph: Color(0xFF3F7FE0),
    moonGlyph: Color(0xFF5D6FC4),
  ),
  // Deep ocean blue, waves and boats.
  'fisherman': PersonaTheme(
    scene: PersonaScene.sea,
    primary: Color(0xFF0F5BB5),
    primaryContainer: Color(0xFF0A3F85),
    primaryFixed: Color(0xFFD3E4F8),
    onPrimaryFixed: Color(0xFF062A57),
    accent2: Color(0xFF1FA7CF),
    accent2Soft: Color(0xFFDDF2F9),
    skyTop: Color(0xFFBEDCF5),
    skyBottom: Color(0xFFE4F2FC),
    sheet: Color(0xFFF4F9FE),
    cardBorder: Color(0xFFD2E5F5),
    tint: Color(0xFFE3F0FB),
    tintStrong: Color(0xFFCCE2F6),
    shadow: Color(0xFF0F5BB5),
    ink: Color(0xFF0B2340),
    inkMuted: Color(0xFF50667F),
    onSurface: Color(0xFF081D36),
    onSurfaceVariant: Color(0xFF3A4D63),
    outline: Color(0xFF6A7C90),
    outlineVariant: Color(0xFFBFD0E0),
    surfaceContainerLow: Color(0xFFEEF5FC),
    surfaceContainer: Color(0xFFE2EEF9),
    surfaceContainerHigh: Color(0xFFD7E7F6),
    navIdle: Color(0xFF687D93),
    skylineFar: Color(0xFFB9D5EE),
    skylineNear: Color(0xFF8DB9DF),
    skylineWindow: Color(0xFFFFFFFF),
    foliage: Color(0xFF8CBF9A),
    foliageDeep: Color(0xFF5E9E78),
    water: Color(0xFF8CC2EE),
    waterDeep: Color(0xFF2F78CE),
    cloudGlyph: Color(0xFF76A8E0),
    rainGlyph: Color(0xFF2F6FD0),
    moonGlyph: Color(0xFF4E63B8),
  ),
  // Purple + pink, airport, tower and aircraft.
  'aviation': PersonaTheme(
    scene: PersonaScene.airport,
    primary: Color(0xFF6D4BD8),
    primaryContainer: Color(0xFF4E2FB0),
    primaryFixed: Color(0xFFE4DCFB),
    onPrimaryFixed: Color(0xFF2A1670),
    accent2: Color(0xFFE0569B),
    accent2Soft: Color(0xFFFCE4F0),
    skyTop: Color(0xFFDCD3FA),
    skyBottom: Color(0xFFF7EDF9),
    sheet: Color(0xFFFBF8FF),
    cardBorder: Color(0xFFE6DDF7),
    tint: Color(0xFFF0EAFD),
    tintStrong: Color(0xFFE1D5FA),
    shadow: Color(0xFF6D4BD8),
    ink: Color(0xFF23184A),
    inkMuted: Color(0xFF66608A),
    onSurface: Color(0xFF1E1542),
    onSurfaceVariant: Color(0xFF4B4568),
    outline: Color(0xFF7D7796),
    outlineVariant: Color(0xFFCDC6E0),
    surfaceContainerLow: Color(0xFFF6F2FE),
    surfaceContainer: Color(0xFFEEE8FC),
    surfaceContainerHigh: Color(0xFFE6DEFA),
    navIdle: Color(0xFF7B7596),
    skylineFar: Color(0xFFDCCFF5),
    skylineNear: Color(0xFFAA95E2),
    skylineWindow: Color(0xFFF6F0FF),
    foliage: Color(0xFFF3C0DC),
    foliageDeep: Color(0xFFD9A3E8),
    water: Color(0xFFEDE1FA),
    waterDeep: Color(0xFFDCC9F5),
    cloudGlyph: Color(0xFF9C8CE3),
    rainGlyph: Color(0xFF6B55D6),
    moonGlyph: Color(0xFF6A4FC9),
  ),
  // Teal / cyan, civic skyline, river and rain — the monitoring look.
  'city_official': PersonaTheme(
    scene: PersonaScene.civic,
    primary: Color(0xFF0B8585),
    primaryContainer: Color(0xFF066363),
    primaryFixed: Color(0xFFCDEFEE),
    onPrimaryFixed: Color(0xFF033B3B),
    accent2: Color(0xFF22B8CF),
    accent2Soft: Color(0xFFDBF4F8),
    skyTop: Color(0xFFC4E8E9),
    skyBottom: Color(0xFFE6F5F5),
    sheet: Color(0xFFF4FBFB),
    cardBorder: Color(0xFFD2EAEA),
    tint: Color(0xFFE2F4F3),
    tintStrong: Color(0xFFC9EBEA),
    shadow: Color(0xFF0B8585),
    ink: Color(0xFF0D2F33),
    inkMuted: Color(0xFF51706F),
    onSurface: Color(0xFF0A272B),
    onSurfaceVariant: Color(0xFF3A5557),
    outline: Color(0xFF6A8586),
    outlineVariant: Color(0xFFBCD7D7),
    surfaceContainerLow: Color(0xFFEDF8F7),
    surfaceContainer: Color(0xFFE1F2F1),
    surfaceContainerHigh: Color(0xFFD5ECEB),
    navIdle: Color(0xFF67827F),
    skylineFar: Color(0xFFB6DCE0),
    skylineNear: Color(0xFF68B3BC),
    skylineWindow: Color(0xFFE3F5F6),
    foliage: Color(0xFF7FC08A),
    foliageDeep: Color(0xFF4E9A62),
    water: Color(0xFFA8DCE4),
    waterDeep: Color(0xFF6FC0CF),
    cloudGlyph: Color(0xFF70B2C8),
    rainGlyph: Color(0xFF1E86B8),
    moonGlyph: Color(0xFF4D6BB5),
  ),
};

/// The palette for a persona id; unknown ids get General Citizen's.
PersonaTheme personaThemeFor(String id) => personaThemes[id] ?? personaThemes['general']!;
