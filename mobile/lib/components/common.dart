// Building blocks that recur across web/src/pages/: the white rounded card,
// the settings section card, the mono "LIVE — …" divider label, the small
// mono chips, and the city picker the Topbar and composers share.
import 'package:flutter/material.dart';

import '../cities.dart';
import '../location.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';

/// `bg-surface-container-lowest rounded-2xl shadow-sm` — the default card.
class SurfaceCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color color;
  final VoidCallback? onTap;

  const SurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpace.md),
    this.radius = AppRadius.x2l,
    this.color = AppColors.surfaceContainerLowest,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final shape = BorderRadius.circular(radius);
    return DecoratedBox(
      decoration: BoxDecoration(borderRadius: shape, boxShadow: AppShadows.sm),
      child: Material(
        color: color,
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
    return SurfaceCard(
      radius: AppRadius.xl,
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 20, color: AppColors.primary),
            const SizedBox(width: AppSpace.sm),
            Expanded(child: Text(title, style: AppText.headlineSm)),
          ]),
          if (subtitle != null) ...[
            const SizedBox(height: AppSpace.xs),
            Text(subtitle!, style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant)),
          ],
          const SizedBox(height: AppSpace.md),
          ...children,
        ],
      ),
    );
  }
}

/// The h1 + lead paragraph the web pages open with (SettingsPage.tsx).
class PageHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  const PageHeader({super.key, required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: AppText.headlineLg.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: AppSpace.xs),
        Text(subtitle, style: AppText.bodyMd.copyWith(color: AppColors.onSurfaceVariant)),
      ],
    );
  }
}

/// `font-citation-mono uppercase tracking-wider` label with a trailing rule —
/// "⚡ LIVE — ANSWERS COME FROM /ASK ────".
class RuleLabel extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color color;
  const RuleLabel({super.key, required this.icon, required this.text, this.color = AppColors.primary});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, size: 14, color: color),
      const SizedBox(width: AppSpace.sm),
      Text(text.toUpperCase(), style: AppText.citationMono.copyWith(color: color, letterSpacing: 0.9)),
      const SizedBox(width: AppSpace.sm),
      Expanded(child: Container(height: 1, color: AppColors.outlineVariant.withValues(alpha: 0.5))),
    ]);
  }
}

/// Plain mono section label ("5-DAY OUTLOOK", "QUICK SITUATIONAL INQUIRIES").
class MonoLabel extends StatelessWidget {
  final String text;
  final Color color;
  const MonoLabel(this.text, {super.key, this.color = AppColors.onSurfaceVariant});

  @override
  Widget build(BuildContext context) =>
      Text(text.toUpperCase(), style: AppText.citationMono.copyWith(color: color));
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
    final primary = tone == ChipTone.primary;
    final fg = primary ? AppColors.primary : AppColors.onSurfaceVariant;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: primary ? AppColors.surfaceContainerHigh : AppColors.surfaceContainer,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 11, color: fg), const SizedBox(width: 3)],
        Flexible(
          child: Text(label, style: AppText.chipMono.copyWith(color: fg), overflow: TextOverflow.ellipsis),
        ),
      ]),
    );
  }
}

/// The LIVE / NOT LIVE provenance badge.
class LiveBadge extends StatelessWidget {
  final bool live;
  final String liveText;
  final String notLiveText;
  const LiveBadge({super.key, required this.live, this.liveText = 'LIVE', this.notLiveText = 'NOT LIVE'});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: live ? AppColors.secondaryContainer : AppColors.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Text(
        live ? liveText : notLiveText,
        style: AppText.citationMono.copyWith(
          color: live ? AppColors.onSecondaryContainer : AppColors.onSurfaceVariant,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

/// `w-4 h-4 rounded-full border-2 border-outline-variant border-t-primary animate-spin`.
class InlineSpinner extends StatelessWidget {
  final double size;
  final Color color;
  final Color? track;
  const InlineSpinner({super.key, this.size = 16, this.color = AppColors.primary, this.track});

  @override
  Widget build(BuildContext context) => SizedBox.square(
        dimension: size,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          color: color,
          backgroundColor: track ?? AppColors.outlineVariant,
        ),
      );
}

/// `p-space-md rounded-xl bg-surface-container-low` loading line.
class LoadingPanel extends StatelessWidget {
  final String text;
  const LoadingPanel(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Row(children: [
        const InlineSpinner(),
        const SizedBox(width: AppSpace.sm),
        Expanded(child: Text(text, style: AppText.bodyMd.copyWith(color: AppColors.onSurfaceVariant))),
      ]),
    );
  }
}

/// `bg-error-container text-on-error-container` failure panel.
class ErrorPanel extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final VoidCallback? onRetry;
  const ErrorPanel({super.key, required this.icon, required this.title, required this.message, this.onRetry});

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
                title,
                style: AppText.labelMd.copyWith(color: AppColors.onErrorContainer, fontWeight: FontWeight.w600),
              ),
            ),
          ]),
          const SizedBox(height: AppSpace.xs),
          Text(message, style: AppText.bodyMd.copyWith(color: AppColors.onErrorContainer)),
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
    return Material(
      color: AppColors.primaryFixed,
      borderRadius: BorderRadius.circular(AppRadius.lg),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        onTap: onPressed,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 18, color: AppColors.onPrimaryFixed),
            const SizedBox(width: 6),
            Text(label, style: AppText.labelMd.copyWith(color: AppColors.onPrimaryFixed)),
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
    final prefs = UiPrefs.of(context);
    final mono = AppText.citationMono.copyWith(color: AppColors.onSurfaceVariant);
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 6,
      runSpacing: 4,
      children: [
        Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 14, color: AppColors.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(prefix.toUpperCase(), style: mono),
        ]),
        Material(
          color: AppColors.surfaceContainerLow,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          child: InkWell(
            borderRadius: BorderRadius.circular(AppRadius.sm),
            onTap: () => showCityPicker(context),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(prefs.cityInfo.name, style: AppText.labelMd),
                const Icon(Icons.expand_more, size: 16, color: AppColors.onSurfaceVariant),
              ]),
            ),
          ),
        ),
        if (showLang) Text('· LANG ${prefs.lang.toUpperCase()}', style: mono.copyWith(color: AppColors.outline)),
      ],
    );
  }
}

/// Topbar.tsx's city dropdown as a bottom sheet, plus a "use my location"
/// row (location.dart: nearest of the registered cities — /ask and
/// /warnings take a city, not coordinates).
Future<void> showCityPicker(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => const _CityPickerSheet(),
  );
}

class _CityPickerSheet extends StatefulWidget {
  const _CityPickerSheet();

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
      final city = await locateNearestCity();
      if (!mounted) return;
      UiPrefs.read(context).city = city.key;
      Navigator.of(context).pop();
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
              child: Text('Choose a city', style: AppText.headlineSm),
            ),
            _CityRow(
              icon: Icons.my_location,
              label: 'Use my location',
              detail: _locateError ?? 'Nearest supported city',
              trailing: _locating ? const InlineSpinner() : null,
              onTap: _locating ? null : _useMyLocation,
            ),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpace.xs, horizontal: 12),
              child: Divider(),
            ),
            for (final City c in kCities)
              _CityRow(
                icon: c.key == prefs.city ? Icons.radio_button_checked : Icons.location_on_outlined,
                label: '${c.name}, ${c.region}',
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
    final fg = active ? AppColors.primary : AppColors.onSurface;
    return Material(
      color: active ? AppColors.primaryContainer.withValues(alpha: 0.1) : Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.lg),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          child: Row(children: [
            Icon(icon, size: 18, color: active ? AppColors.primary : AppColors.onSurfaceVariant),
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
                  Text(detail!, style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant)),
              ]),
            ),
            ?trailing,
          ]),
        ),
      ),
    );
  }
}
