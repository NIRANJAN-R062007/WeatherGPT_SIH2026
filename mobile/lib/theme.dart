// Visual tokens mirrored from the web frontend so both clients read as one
// product: colours, type scale, spacing and radii are copied verbatim from
// web/tailwind.config.js (the Stitch-exported Material 3 palette that
// web/src/index.css applies), and the fonts in assets/fonts/ are static-weight
// TTF instances of the same self-hosted woff2 files in web/public/fonts/
// (Flutter can't load woff2, and FontWeight doesn't reliably drive a variable
// font's wght axis, hence one file per weight). Keep these literal — if a
// token changes on the web side, change it here too.
import 'package:flutter/material.dart';

/// web/tailwind.config.js `theme.extend.colors`.
abstract final class AppColors {
  static const primary = Color(0xFF0057C2);
  static const onPrimary = Color(0xFFFFFFFF);
  static const primaryContainer = Color(0xFF006EF3);
  static const onPrimaryContainer = Color(0xFFFEFCFF);
  static const primaryFixed = Color(0xFFD9E2FF);
  static const primaryFixedDim = Color(0xFFAFC6FF);
  static const onPrimaryFixed = Color(0xFF001943);
  static const onPrimaryFixedVariant = Color(0xFF004299);
  static const inversePrimary = Color(0xFFAFC6FF);
  static const surfaceTint = Color(0xFF0059C7);

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
}

/// Tailwind v3's stock shadow-sm / shadow-md, and the custom
/// `shadow-[0_1px_8px_rgba(0,0,0,0.04)]` the Sidebar and Topbar share.
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

const ColorScheme kAppColorScheme = ColorScheme(
  brightness: Brightness.light,
  primary: AppColors.primary,
  onPrimary: AppColors.onPrimary,
  primaryContainer: AppColors.primaryContainer,
  onPrimaryContainer: AppColors.onPrimaryContainer,
  primaryFixed: AppColors.primaryFixed,
  primaryFixedDim: AppColors.primaryFixedDim,
  onPrimaryFixed: AppColors.onPrimaryFixed,
  onPrimaryFixedVariant: AppColors.onPrimaryFixedVariant,
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
  error: AppColors.error,
  onError: AppColors.onError,
  errorContainer: AppColors.errorContainer,
  onErrorContainer: AppColors.onErrorContainer,
  surface: AppColors.surface,
  onSurface: AppColors.onSurface,
  onSurfaceVariant: AppColors.onSurfaceVariant,
  surfaceDim: AppColors.surfaceDim,
  surfaceBright: AppColors.surfaceBright,
  surfaceContainerLowest: AppColors.surfaceContainerLowest,
  surfaceContainerLow: AppColors.surfaceContainerLow,
  surfaceContainer: AppColors.surfaceContainer,
  surfaceContainerHigh: AppColors.surfaceContainerHigh,
  surfaceContainerHighest: AppColors.surfaceContainerHighest,
  outline: AppColors.outline,
  outlineVariant: AppColors.outlineVariant,
  inverseSurface: AppColors.inverseSurface,
  onInverseSurface: AppColors.inverseOnSurface,
  inversePrimary: AppColors.inversePrimary,
  surfaceTint: AppColors.surfaceTint,
  shadow: Color(0xFF000000),
  scrim: Color(0xFF000000),
);

/// Light only, like web/ (it defines no dark palette).
ThemeData buildAppTheme() {
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
  ).apply(bodyColor: AppColors.onSurface, displayColor: AppColors.onSurface);

  return ThemeData(
    useMaterial3: true,
    colorScheme: kAppColorScheme,
    textTheme: textTheme,
    primaryTextTheme: textTheme.apply(
      bodyColor: AppColors.onPrimary,
      displayColor: AppColors.onPrimary,
    ),
    scaffoldBackgroundColor: AppColors.surface,
    canvasColor: AppColors.surface,
    dividerTheme: const DividerThemeData(color: AppColors.outlineVariant, thickness: 1, space: 1),
    drawerTheme: const DrawerThemeData(
      backgroundColor: AppColors.surfaceContainerLowest,
      surfaceTintColor: Colors.transparent,
      width: 256, // Sidebar's w-64
      shape: RoundedRectangleBorder(),
      endShape: RoundedRectangleBorder(),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.surfaceContainerLowest,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      dragHandleColor: AppColors.outlineVariant,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.x2l)),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.inverseSurface,
      contentTextStyle: AppText.bodyMd.copyWith(color: AppColors.inverseOnSurface),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadius.xl)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      isDense: true,
      border: InputBorder.none,
      hintStyle: AppText.bodyMd.copyWith(color: AppColors.outline),
    ),
    textSelectionTheme: const TextSelectionThemeData(cursorColor: AppColors.primary),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.primary,
      circularTrackColor: AppColors.outlineVariant,
    ),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: AppColors.inverseSurface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      textStyle: AppText.bodySm.copyWith(color: AppColors.inverseOnSurface),
    ),
  );
}
