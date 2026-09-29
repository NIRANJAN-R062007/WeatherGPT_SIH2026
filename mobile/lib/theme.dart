// Visual tokens. The Material 3 palette, type scale, spacing and radii started
// as verbatim copies of web/tailwind.config.js (the Stitch-exported palette
// web/src/index.css applies). Since the persona themes, every colour that
// changes with the selected persona — accents, sky, cards, text, scenery —
// comes from persona_theme.dart's PersonaTheme; AppColors keeps the
// persona-independent ones (error, the LIVE/verified green, the sun) and the
// web palette buildAppTheme falls back on. The fonts
// in assets/fonts/ are static-weight TTF instances of the self-hosted woff2
// files in web/public/fonts/ (Flutter can't load woff2, and FontWeight doesn't
// reliably drive a variable font's wght axis, hence one file per weight).
//
// Every colour a page uses lives here or in persona_theme.dart, by name — no
// raw hex in pages — so a dark palette can later be dropped in by giving each
// token a dark value.
import 'package:flutter/material.dart';

import 'persona_theme.dart';

/// web/tailwind.config.js `theme.extend.colors`.
abstract final class AppColors {
  static const primary = Color(0xFF1D6AE5); // mockup blue (web: 0xFF0057C2)
  static const onPrimary = Color(0xFFFFFFFF);
  static const primaryContainer = Color(0xFF006EF3);
  static const onPrimaryContainer = Color(0xFFFEFCFF);
  static const primaryFixed = Color(0xFFD9E2FF);
  static const primaryFixedDim = Color(0xFFAFC6FF);
  static const onPrimaryFixed = Color(0xFF001943);
  static const onPrimaryFixedVariant = Color(0xFF004299);
  static const inversePrimary = Color(0xFFAFC6FF);
  static const surfaceTint = Color(0xFF1D6AE5);

  static const secondary = Color(0xFF006A6A);
  static const onSecondary = Color(0xFFFFFFFF);
  static const secondaryContainer = Color(0xFF7AF5F5);
  static const onSecondaryContainer = Color(0xFF007070);
  static const secondaryFixed = Color(0xFF7AF5F5);
  static const secondaryFixedDim = Color(0xFF5BD9D8);
  static const onSecondaryFixed = Color(0xFF002020);
  static const onSecondaryFixedVariant = Color(0xFF004F4F);

  static const tertiary = Color(0xFF7D5400);
  static const onTertiary = Color(0xFFFFFFFF);
  static const tertiaryContainer = Color(0xFF9D6A00);
  static const onTertiaryContainer = Color(0xFFFFFBFF);
  static const tertiaryFixed = Color(0xFFFFDDB0);
  static const tertiaryFixedDim = Color(0xFFFFBA46);
  static const onTertiaryFixed = Color(0xFF281800);
  static const onTertiaryFixedVariant = Color(0xFF614000);

  static const error = Color(0xFFBA1A1A);
  static const onError = Color(0xFFFFFFFF);
  static const errorContainer = Color(0xFFFFDAD6);
  static const onErrorContainer = Color(0xFF93000A);

  static const background = Color(0xFFF9F9FF);
  static const onBackground = Color(0xFF041B3C);
  static const surface = Color(0xFFF9F9FF);
  static const surfaceBright = Color(0xFFF9F9FF);
  static const surfaceDim = Color(0xFFCADAFF);
  static const surfaceVariant = Color(0xFFD7E2FF);
  static const surfaceContainerLowest = Color(0xFFFFFFFF);
  static const surfaceContainerLow = Color(0xFFF1F3FF);
  static const surfaceContainer = Color(0xFFE8EDFF);
  static const surfaceContainerHigh = Color(0xFFE0E8FF);
  static const surfaceContainerHighest = Color(0xFFD7E2FF);
  static const onSurface = Color(0xFF041B3C);
  static const onSurfaceVariant = Color(0xFF414755);
  static const inverseSurface = Color(0xFF1D3052);
  static const inverseOnSurface = Color(0xFFEDF0FF);
  static const outline = Color(0xFF727786);
  static const outlineVariant = Color(0xFFC1C6D7);

  /// The sun in weather glyphs and the brand mark — the same on every
  /// persona. Every persona-dependent colour (accents, sky, cards, text,
  /// scenery) lives in persona_theme.dart instead.
  static const sun = Color(0xFFFFB21E);
  static const sunCore = Color(0xFFFFCB4F);

  /// Illustration accents that read the same on every persona: the
  /// farmhouse's walls and roof, the lighthouse lamp.
  static const farmWall = Color(0xFFF4E4C4);
  static const farmRoof = Color(0xFFC65A3C);
  static const lampGlow = Color(0xFFFFE08A);
}

/// web/tailwind.config.js `spacing` (space-xs .. space-xl, gutter-mobile).
abstract final class AppSpace {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;

  /// `gutter-mobile` / `margin-mobile`: the page side padding on phones.
  static const double gutter = 16;
}

/// web/tailwind.config.js `borderRadius`, plus Tailwind's stock `rounded-2xl`
/// (1rem) which the web pages use for their top-level cards.
abstract final class AppRadius {
  static const double sm = 4; // DEFAULT
  static const double md = 6; // rounded-md (Tailwind stock)
  static const double lg = 8;
  static const double xl = 12;
  static const double x2l = 16;

  /// The redesign's cards and the page sheet's top corners.
  static const double card = 16;
  static const double sheet = 28;
}

/// Tailwind v3's stock shadow-sm / shadow-md, and the custom
/// `shadow-[0_1px_8px_rgba(0,0,0,0.04)]` the Sidebar and Topbar share, plus
/// the persona-tinted card lift of the redesign (PersonaTheme.cardShadow).
abstract final class AppShadows {
  static const sm = [BoxShadow(color: Color(0x0D000000), blurRadius: 2, offset: Offset(0, 1))];
  static const md = [
    BoxShadow(color: Color(0x1A000000), blurRadius: 6, offset: Offset(0, 4), spreadRadius: -1),
    BoxShadow(color: Color(0x1A000000), blurRadius: 4, offset: Offset(0, 2), spreadRadius: -2),
  ];
  static const chrome = [BoxShadow(color: Color(0x0A000000), blurRadius: 8, offset: Offset(0, 1))];
}

abstract final class AppFonts {
  static const body = 'Inter';
  static const headline = 'PlusJakartaSans';
  static const mono = 'JetBrainsMono';
}

/// web/tailwind.config.js `fontSize` + `fontFamily`, one style per token.
/// Colour is deliberately left unset so text inherits it from the
/// surrounding DefaultTextStyle, the way a Tailwind `font-*` class does;
/// add it with copyWith at the call site. letterSpacing is converted from
/// em to logical pixels, and line-height to Flutter's font-size multiple
/// with even leading distribution (CSS half-leading).
abstract final class AppText {
  static const _even = TextLeadingDistribution.even;

  static const metricDisplay = TextStyle(
    fontFamily: AppFonts.headline,
    fontSize: 56,
    height: 60 / 56,
    letterSpacing: -1.68,
    fontWeight: FontWeight.w700,
    leadingDistribution: _even,
  );
  static const headlineXl = TextStyle(
    fontFamily: AppFonts.headline,
    fontSize: 30, // headline-xl-mobile
    height: 38 / 30,
    letterSpacing: -0.3,
    fontWeight: FontWeight.w700,
    leadingDistribution: _even,
  );
  static const headlineLg = TextStyle(
    fontFamily: AppFonts.headline,
    fontSize: 24, // headline-lg-mobile
    height: 32 / 24,
    fontWeight: FontWeight.w600,
    leadingDistribution: _even,
  );
  static const headlineMd = TextStyle(
    fontFamily: AppFonts.headline,
    fontSize: 22,
    height: 28 / 22,
    fontWeight: FontWeight.w600,
    leadingDistribution: _even,
  );
  static const headlineSm = TextStyle(
    fontFamily: AppFonts.headline,
    fontSize: 18,
    height: 24 / 18,
    fontWeight: FontWeight.w600,
    leadingDistribution: _even,
  );
  static const bodyLg = TextStyle(
    fontFamily: AppFonts.body,
    fontSize: 16,
    height: 26 / 16,
    fontWeight: FontWeight.w400,
    leadingDistribution: _even,
  );
  static const bodyMd = TextStyle(
    fontFamily: AppFonts.body,
    fontSize: 14,
    height: 22 / 14,
    fontWeight: FontWeight.w400,
    leadingDistribution: _even,
  );
  static const bodySm = TextStyle(
    fontFamily: AppFonts.body,
    fontSize: 12,
    height: 18 / 12,
    fontWeight: FontWeight.w400,
    leadingDistribution: _even,
  );
  static const labelMd = TextStyle(
    fontFamily: AppFonts.body,
    fontSize: 13,
    height: 18 / 13,
    fontWeight: FontWeight.w500,
    leadingDistribution: _even,
  );
  static const citationMono = TextStyle(
    fontFamily: AppFonts.mono,
    fontSize: 11,
    height: 16 / 11,
    letterSpacing: 0.33,
    fontWeight: FontWeight.w500,
    leadingDistribution: _even,
  );

  /// The `font-citation-mono text-[10px]` chip text the web uses throughout.
  static const chipMono = TextStyle(
    fontFamily: AppFonts.mono,
    fontSize: 10,
    height: 14 / 10,
    letterSpacing: 0.3,
    fontWeight: FontWeight.w500,
    leadingDistribution: _even,
  );
}

/// Material slots, with the persona-dependent ones taken from [t].
ColorScheme appColorScheme(PersonaTheme t) => ColorScheme(
  brightness: t.brightness,
  primary: t.primary,
  onPrimary: t.onPrimary,
  primaryContainer: t.primaryContainer,
  onPrimaryContainer: t.onPrimary,
  primaryFixed: t.primaryFixed,
  primaryFixedDim: t.tintStrong,
  onPrimaryFixed: t.onPrimaryFixed,
  onPrimaryFixedVariant: t.primaryContainer,
  secondary: AppColors.secondary,
  onSecondary: AppColors.onSecondary,
  secondaryContainer: AppColors.secondaryContainer,
  onSecondaryContainer: AppColors.onSecondaryContainer,
  secondaryFixed: AppColors.secondaryFixed,
  secondaryFixedDim: AppColors.secondaryFixedDim,
  onSecondaryFixed: AppColors.onSecondaryFixed,
  onSecondaryFixedVariant: AppColors.onSecondaryFixedVariant,
  tertiary: AppColors.tertiary,
  onTertiary: AppColors.onTertiary,
  tertiaryContainer: AppColors.tertiaryContainer,
  onTertiaryContainer: AppColors.onTertiaryContainer,
  tertiaryFixed: AppColors.tertiaryFixed,
  tertiaryFixedDim: AppColors.tertiaryFixedDim,
  onTertiaryFixed: AppColors.onTertiaryFixed,
  onTertiaryFixedVariant: AppColors.onTertiaryFixedVariant,
  error: t.isDark ? const Color(0xFFFFB4AB) : AppColors.error,
  onError: t.isDark ? const Color(0xFF690005) : AppColors.onError,
  errorContainer: t.isDark ? const Color(0xFF93000A) : AppColors.errorContainer,
  onErrorContainer: t.isDark ? const Color(0xFFFFDAD6) : AppColors.onErrorContainer,
  surface: t.sheet,
  onSurface: t.onSurface,
  onSurfaceVariant: t.onSurfaceVariant,
  surfaceDim: t.tintStrong,
  surfaceBright: t.sheet,
  surfaceContainerLowest: t.surfaceContainerLowest,
  surfaceContainerLow: t.surfaceContainerLow,
  surfaceContainer: t.surfaceContainer,
  surfaceContainerHigh: t.surfaceContainerHigh,
  surfaceContainerHighest: t.tintStrong,
  outline: t.outline,
  outlineVariant: t.outlineVariant,
  inverseSurface: t.isDark ? t.ink : AppColors.inverseSurface,
  onInverseSurface: t.isDark ? t.sheet : AppColors.inverseOnSurface,
  inversePrimary: t.primaryFixed,
  surfaceTint: t.primary,
  shadow: const Color(0xFF000000),
  scrim: const Color(0xFF000000),
);

/// The app theme for one persona palette (light only for now). [t] is also
/// installed as a ThemeExtension, so `PersonaTheme.of(context)` reads it and
/// MaterialApp's theme animation cross-fades it on a persona change.
ThemeData buildAppTheme([PersonaTheme? persona]) {
  final t = persona ?? personaThemeFor('general');
  // Maps the web tokens onto Material's slots so stock widgets (TextField,
  // SnackBar, buttons) pick up the same type scale. Pages mostly use AppText
  // directly. No ThemeData.fontFamily: it would overwrite the headline and
  // mono families below with Inter.
  final textTheme = const TextTheme(
    displayLarge: AppText.metricDisplay,
    displayMedium: AppText.headlineXl,
    displaySmall: AppText.headlineXl,
    headlineLarge: AppText.headlineLg,
    headlineMedium: AppText.headlineLg,
    headlineSmall: AppText.headlineMd,
    titleLarge: AppText.headlineMd,
    titleMedium: AppText.headlineSm,
    titleSmall: AppText.labelMd,
    bodyLarge: AppText.bodyLg,
    bodyMedium: AppText.bodyMd,
    bodySmall: AppText.bodySm,
    labelLarge: AppText.labelMd,
    labelMedium: AppText.citationMono,
    labelSmall: AppText.chipMono,
  ).apply(bodyColor: t.onSurface, displayColor: t.onSurface);

  return ThemeData(
    useMaterial3: true,
    colorScheme: appColorScheme(t),
    extensions: [t],
    textTheme: textTheme,
    primaryTextTheme: textTheme.apply(bodyColor: t.onPrimary, displayColor: t.onPrimary),
    scaffoldBackgroundColor: t.sheet,
    canvasColor: t.sheet,
    dividerTheme: DividerThemeData(color: t.outlineVariant, thickness: 1, space: 1),
    dialogTheme: DialogThemeData(backgroundColor: t.card, surfaceTintColor: Colors.transparent),
    drawerTheme: DrawerThemeData(
      backgroundColor: t.sheet,
      surfaceTintColor: Colors.transparent,
      width: 256, // Sidebar's w-64
      shape: const RoundedRectangleBorder(),
      endShape: const RoundedRectangleBorder(),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: t.sheet,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      dragHandleColor: t.outlineVariant,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.x2l))),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: t.isDark ? t.ink : AppColors.inverseSurface,
      contentTextStyle: AppText.bodyMd.copyWith(color: t.isDark ? t.sheet : AppColors.inverseOnSurface),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadius.xl)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      isDense: true,
      border: InputBorder.none,
      hintStyle: AppText.bodyMd.copyWith(color: t.outline),
    ),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: t.primary,
      selectionColor: t.primary.withValues(alpha: 0.25),
      selectionHandleColor: t.primary,
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: t.primary, circularTrackColor: t.outlineVariant),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(foregroundColor: t.primary)),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: t.isDark ? t.ink : AppColors.inverseSurface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      textStyle: AppText.bodySm.copyWith(color: t.isDark ? t.sheet : AppColors.inverseOnSurface),
    ),
  );
}
