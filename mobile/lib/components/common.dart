// Building blocks that recur across web/src/pages/: the white rounded card,
// the settings section card, the mono "LIVE — …" divider label, the small
// mono chips, and the city picker the Topbar and composers share.
import 'package:flutter/material.dart';

import '../cities.dart';
import '../location.dart';
import '../state/ui_prefs.dart';
import '../persona_theme.dart';
import '../theme.dart';
import '../i18n.dart';

/// `bg-surface-container-lowest rounded-2xl shadow-sm` — the default card.
class SurfaceCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? color;
  final VoidCallback? onTap;

  const SurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpace.md),
    this.radius = AppRadius.x2l,
    this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final shape = BorderRadius.circular(radius);
    return DecoratedBox(
      decoration: BoxDecoration(borderRadius: shape, boxShadow: AppShadows.sm),
      child: Material(
        color: color ?? PersonaTheme.of(context).surfaceContainerLowest,
        borderRadius: shape,
        clipBehavior: Clip.antiAlias,
        child: onTap == null
            ? Padding(padding: padding, child: child)
            : InkWell(onTap: onTap, child: Padding(padding: padding, child: child)),
      ),
    );
  }
}

/// SettingsPage.tsx's SectionCard: primary icon + headline-sm title.
class SectionCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final String? subtitle;
  final List<Widget> children;

  const SectionCard({
    super.key,
    required this.title,
    required this.icon,
    this.subtitle,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return SurfaceCard(
      radius: AppRadius.xl,
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 20, color: t.primary),
            const SizedBox(width: AppSpace.sm),
            Expanded(child: Text(tr(context, title), style: AppText.headlineSm)),
          ]),
          if (subtitle != null) ...[
            const SizedBox(height: AppSpace.xs),
            Text(tr(context, subtitle!), style: AppText.bodySm.copyWith(color: t.onSurfaceVariant)),
          ],
          const SizedBox(height: AppSpace.md),
          ...children,
        ],
      ),
    );
  }
}

/// The page title + lead line each page's sheet opens with.
class PageHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  const PageHeader({super.key, required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(tr(context, title), style: AppText.headlineLg.copyWith(color: t.ink, fontWeight: FontWeight.w700)),
        const SizedBox(height: AppSpace.xs),
        Text(tr(context, subtitle), style: AppText.bodyMd.copyWith(color: t.inkMuted)),
      ],
    );
  }
}

/// `font-citation-mono uppercase tracking-wider` label with a trailing rule —
/// "⚡ LIVE — ANSWERS COME FROM /ASK ────".
class RuleLabel extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color? color;
  const RuleLabel({super.key, required this.icon, required this.text, this.color});

  @override
  Widget build(BuildContext context) {
    final color = this.color ?? PersonaTheme.of(context).primary;
    final t = PersonaTheme.of(context);
    return Row(children: [
      Icon(icon, size: 14, color: color),
      const SizedBox(width: AppSpace.sm),
      // Wraps rather than overflows when a translation is longer than the row.
      Flexible(
        child: Text(
          tr(context, text).toUpperCase(),
          style: AppText.citationMono.copyWith(color: color, letterSpacing: 0.9),
        ),
      ),
      const SizedBox(width: AppSpace.sm),
      Expanded(child: Container(height: 1, color: t.outlineVariant.withValues(alpha: 0.5))),
    ]);
  }
}

/// Plain mono section label ("5-DAY OUTLOOK", "QUICK SITUATIONAL INQUIRIES").
class MonoLabel extends StatelessWidget {
  final String text;
  final Color? color;
  const MonoLabel(this.text, {super.key, this.color});

  @override
  Widget build(BuildContext context) => Text(
        tr(context, text).toUpperCase(),
        style: AppText.citationMono.copyWith(color: color ?? PersonaTheme.of(context).onSurfaceVariant),
      );
}

enum ChipTone { neutral, primary }

/// AskAnswer.tsx's Chip: `px-2 py-0.5 rounded-full font-citation-mono text-[10px]`.
class TagChip extends StatelessWidget {
  final String label;
  final IconData? icon;
  final ChipTone tone;
  const TagChip(this.label, {super.key, this.icon, this.tone = ChipTone.neutral});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final primary = tone == ChipTone.primary;
    final fg = primary ? t.primary : t.onSurfaceVariant;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: primary ? t.surfaceContainerHigh : t.surfaceContainer,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 11, color: fg), const SizedBox(width: 3)],
        Flexible(
          child: Text(tr(context, label), style: AppText.chipMono.copyWith(color: fg), overflow: TextOverflow.ellipsis),
        ),
      ]),
    );
  }
}

/// Phase 7 B2: `warning.disclaimer` ("Simulated data — pending official feed
/// access"), shown on every warning card sourced from fixtures — mirrors
/// web's `bg-tertiary-fixed text-on-tertiary-fixed` banner with the
/// `science` icon in AlertsPage.tsx / AskAnswer.tsx. Takes the raw field so
/// callers stay null-tolerant with an older orchestrator that doesn't send it.
class DisclaimerBanner extends StatelessWidget {
  final String text;
  const DisclaimerBanner(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.tertiaryFixed,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Padding(
          padding: EdgeInsets.only(top: 2),
          child: Icon(Icons.science_outlined, size: 14, color: AppColors.onTertiaryFixed),
        ),
        const SizedBox(width: 6),
        Expanded(child: Text(tr(context, text), style: AppText.bodySm.copyWith(color: AppColors.onTertiaryFixed))),
      ]),
    );
  }
}

/// `w['disclaimer']` (or an older orchestrator's absent field) as a widget,
/// or null to omit it — callers that build gapped lists (e.g. `_gap`'s
/// null-aware spread) drop it cleanly instead of leaving an empty gap.
Widget? disclaimerBanner(Map<String, dynamic> w) {
  final d = w['disclaimer'];
  return d is String && d.isNotEmpty ? DisclaimerBanner(d) : null;
}

/// The LIVE / NOT LIVE provenance badge.
class LiveBadge extends StatelessWidget {
  final bool live;
  final String liveText;
  final String notLiveText;
  const LiveBadge({super.key, required this.live, this.liveText = 'LIVE', this.notLiveText = 'NOT LIVE'});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: live ? AppColors.secondaryContainer : t.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Text(
        tr(context, live ? liveText : notLiveText),
        style: AppText.citationMono.copyWith(
          color: live ? AppColors.onSecondaryContainer : t.onSurfaceVariant,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

/// Shown while a page is on saved replies (lib/response_cache.dart):
/// [message] says what couldn't be reached and when the copy was saved;
/// neutral, like a "no verdict" card, never an error colour or a green.
class SavedDataBanner extends StatelessWidget {
  final String message;
  final Map<String, Object?> messageArgs;
  final VoidCallback? onRetry;
  const SavedDataBanner({super.key, required this.message, this.messageArgs = const {}, this.onRetry});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: t.surfaceContainerLow,
        border: Border.all(color: t.outlineVariant),
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.cloud_off_outlined, size: 18, color: t.onSurfaceVariant),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  tr(context, 'Showing saved data'),
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.xs),
          Text(tr(context, message, messageArgs), style: AppText.bodyMd.copyWith(color: t.onSurfaceVariant)),
          if (onRetry != null) ...[
            const SizedBox(height: AppSpace.sm),
            PillButton(icon: Icons.refresh, label: 'Try again', onPressed: onRetry),
          ],
        ],
      ),
    );
  }
}

/// `w-4 h-4 rounded-full border-2 border-outline-variant border-t-primary animate-spin`.
class InlineSpinner extends StatelessWidget {
  final double size;
  final Color? color;
  final Color? track;
  const InlineSpinner({super.key, this.size = 16, this.color, this.track});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return SizedBox.square(
      dimension: size,
      child: CircularProgressIndicator(
        strokeWidth: 2,
        color: color ?? t.primary,
        backgroundColor: track ?? t.outlineVariant,
      ),
    );
  }
}

/// `p-space-md rounded-xl bg-surface-container-low` loading line.
class LoadingPanel extends StatelessWidget {
  final String text;
  const LoadingPanel(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: t.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Row(children: [
        const InlineSpinner(),
        const SizedBox(width: AppSpace.sm),
        Expanded(child: Text(tr(context, text), style: AppText.bodyMd.copyWith(color: t.onSurfaceVariant))),
      ]),
    );
  }
}

/// `bg-error-container text-on-error-container` failure panel.
class ErrorPanel extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;

  /// Values for the `{name}` placeholders in [message] (an error's `args`).
  final Map<String, Object?> messageArgs;
  final VoidCallback? onRetry;
  const ErrorPanel({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.messageArgs = const {},
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.errorContainer,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 18, color: AppColors.onErrorContainer),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                tr(context, title),
                style: AppText.labelMd.copyWith(color: AppColors.onErrorContainer, fontWeight: FontWeight.w600),
              ),
            ),
          ]),
          const SizedBox(height: AppSpace.xs),
          Text(tr(context, message, messageArgs), style: AppText.bodyMd.copyWith(color: AppColors.onErrorContainer)),
          if (onRetry != null) ...[
            const SizedBox(height: AppSpace.sm),
            PillButton(icon: Icons.refresh, label: 'Try again', onPressed: onRetry),
          ],
        ],
      ),
    );
  }
}

/// HistoryPage.tsx's "Ask again": `rounded-lg bg-primary-fixed text-on-primary-fixed`.
class PillButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  const PillButton({super.key, required this.icon, required this.label, this.onPressed});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Material(
      color: t.primaryFixed,
      borderRadius: BorderRadius.circular(AppRadius.lg),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        onTap: onPressed,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 18, color: t.onPrimaryFixed),
            const SizedBox(width: 6),
            // A translation too long for the row wraps rather than overflowing.
            Flexible(
              child: Text(tr(context, label), style: AppText.labelMd.copyWith(color: t.onPrimaryFixed)),
            ),
          ]),
        ),
      ),
    );
  }
}

/// The composers' "IF UNSPECIFIED, ASSUME [city] · LANG XX" row. The city is
/// only a hint — /ask's NLU uses a city named in the question first.
class CityHintRow extends StatelessWidget {
  final String prefix;
  final IconData icon;
  final bool showLang;
  const CityHintRow({
    super.key,
    this.prefix = 'If unspecified, assume',
    this.icon = Icons.my_location,
    this.showLang = true,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final mono = AppText.citationMono.copyWith(color: t.onSurfaceVariant);
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 6,
      runSpacing: 4,
      children: [
        Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 14, color: t.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(tr(context, prefix).toUpperCase(), style: mono),
        ]),
        Material(
          color: t.surfaceContainerLow,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          child: InkWell(
            borderRadius: BorderRadius.circular(AppRadius.sm),
            onTap: () => showCityPicker(context),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(tr(context, prefs.cityInfo.name), style: AppText.labelMd),
                Icon(Icons.expand_more, size: 16, color: t.onSurfaceVariant),
              ]),
            ),
          ),
        ),
        if (showLang) Text('· LANG ${prefs.lang.toUpperCase()}', style: mono.copyWith(color: t.outline)),
      ],
    );
  }
}

/// Beyond this, "Use my location" warns that answers are for the city, not
/// where the user is: the demo cities are metros, so 50 km covers their
/// suburbs but not the next town.
const double kNearCityKm = 50;

/// Topbar.tsx's city dropdown as a bottom sheet, listing the cities the
/// server answers for (UiPrefs.cities), plus a "use my location" row: the
/// nearest of those cities — /ask and /warnings take a city, not
/// coordinates. A note says which city was picked and how far it is from
/// the user. [locate] is for tests.
Future<void> showCityPicker(BuildContext context, {Locator locate = currentPosition}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _CityPickerSheet(locate: locate),
  );
}

/// "Madurai, Tamil Nadu" in the app language; just the name when the
/// server's entry has no region.
String cityAndRegion(BuildContext context, City city) =>
    city.region.isEmpty ? tr(context, city.name) : '${tr(context, city.name)}, ${tr(context, city.region)}';

/// What "Use my location" tells the user about the city it picked.
String nearestCityNote(BuildContext context, City city, double km) {
  final args = {'city': tr(context, city.name), 'km': km < 1 ? '1' : km.round().toString()};
  return km <= kNearCityKm
      ? tr(context, 'Using {city}, about {km} km from you.', args)
      : tr(
          context,
          '{city} is the nearest city WeatherGPT covers, about {km} km from you. '
          'Answers are for {city}, not your exact location.',
          args,
        );
}

class _CityPickerSheet extends StatefulWidget {
  final Locator locate;
  const _CityPickerSheet({required this.locate});

  @override
  State<_CityPickerSheet> createState() => _CityPickerSheetState();
}

class _CityPickerSheetState extends State<_CityPickerSheet> {
  bool _locating = false;
  String? _locateError;

  Future<void> _useMyLocation() async {
    setState(() {
      _locating = true;
      _locateError = null;
    });
    try {
      final here = await widget.locate();
      if (!mounted) return;
      final prefs = UiPrefs.read(context);
      final (:city, :km) = nearestCity(here.lat, here.lon, prefs.cities);
      prefs.city = city.key;
      final note = nearestCityNote(context, city, km);
      final messenger = ScaffoldMessenger.of(context);
      Navigator.of(context).pop();
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(note),
            duration: Duration(seconds: km <= kNearCityKm ? 4 : 10),
            showCloseIcon: true,
          ),
        );
    } catch (e) {
      if (mounted) setState(() => _locateError = '$e');
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    return SafeArea(
      top: false,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(AppSpace.sm, 0, AppSpace.sm, AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, AppSpace.sm),
              child: Text(tr(context, 'Choose a city'), style: AppText.headlineSm),
            ),
            _CityRow(
              icon: Icons.my_location,
              label: tr(context, 'Use my location'),
              detail: tr(context, _locateError ?? 'Nearest supported city'),
              trailing: _locating ? const InlineSpinner() : null,
              onTap: _locating ? null : _useMyLocation,
            ),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpace.xs, horizontal: 12),
              child: Divider(),
            ),
            for (final City c in prefs.cities)
              _CityRow(
                icon: c.key == prefs.city ? Icons.radio_button_checked : Icons.location_on_outlined,
                label: cityAndRegion(context, c),
                active: c.key == prefs.city,
                onTap: () {
                  prefs.city = c.key;
                  Navigator.of(context).pop();
                },
              ),
          ],
        ),
      ),
    );
  }
}

class _CityRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? detail;
  final bool active;
  final Widget? trailing;
  final VoidCallback? onTap;
  const _CityRow({
    required this.icon,
    required this.label,
    this.detail,
    this.active = false,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fg = active ? t.primary : t.onSurface;
    return Material(
      color: active ? t.primaryContainer.withValues(alpha: 0.1) : Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.lg),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          child: Row(children: [
            Icon(icon, size: 18, color: active ? t.primary : t.onSurfaceVariant),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(
                  label,
                  style: AppText.labelMd.copyWith(
                    color: fg,
                    fontWeight: active ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
                if (detail != null)
                  Text(detail!, style: AppText.bodySm.copyWith(color: t.onSurfaceVariant)),
              ]),
            ),
            ?trailing,
          ]),
        ),
      ),
    );
  }
}
