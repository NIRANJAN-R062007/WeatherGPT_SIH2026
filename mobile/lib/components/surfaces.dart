// The redesign's recurring pieces (pics/ mockups): the white bordered card,
// the section title, the tinted icon disc, and the icon + text + chevron
// row that Quick Questions, Suggested Questions, alert lists and Settings
// rows all share. Every colour comes from the active persona's
// PersonaTheme, so these re-tint with the persona.
import 'package:flutter/material.dart';

import '../persona_theme.dart';
import '../theme.dart';

/// White card with a hairline persona-tinted border and a soft tinted lift.
/// [wash] fades the card from white into the persona tint (weather cards).
class AppCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final Color? borderColor;
  final double borderWidth;
  final bool wash;
  final VoidCallback? onTap;

  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpace.md),
    this.color,
    this.borderColor,
    this.borderWidth = 1,
    this.wash = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final radius = BorderRadius.circular(AppRadius.card);
    final body = Padding(padding: padding, child: child);
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: radius,
        boxShadow: t.cardShadow,
        gradient: wash
            ? LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [color ?? t.card, t.tint, t.accent2Soft],
                stops: const [0.35, 0.85, 1],
              )
            : null,
      ),
      child: Material(
        color: wash ? Colors.transparent : (color ?? t.card),
        shape: RoundedRectangleBorder(
          borderRadius: radius,
          side: BorderSide(color: borderColor ?? t.cardBorder, width: borderWidth),
        ),
        clipBehavior: Clip.antiAlias,
        child: onTap == null ? body : InkWell(onTap: onTap, child: body),
      ),
    );
  }
}

/// "Quick Questions", "Active Alerts" — with an optional trailing link.
class SectionTitle extends StatelessWidget {
  final String text;
  final String? action;
  final VoidCallback? onAction;
  const SectionTitle(this.text, {super.key, this.action, this.onAction});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            text,
            style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
          ),
        ),
        if (action != null)
          InkWell(
            borderRadius: BorderRadius.circular(AppRadius.lg),
            onTap: onAction,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              child: Text(
                action!,
                style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w600),
              ),
            ),
          ),
      ],
    );
  }
}

/// A round tinted disc holding one icon. Solid discs without an explicit
/// [color] fill with the persona's accent gradient.
class IconDisc extends StatelessWidget {
  final IconData icon;
  final Color? color;
  final Color? background;
  final double size;
  final bool solid;

  const IconDisc(this.icon, {super.key, this.color, this.background, this.size = 40, this.solid = false});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fg = color ?? t.primary;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: solid ? fg : (background ?? t.tint),
        gradient: solid && color == null ? t.accentGradient : null,
        shape: BoxShape.circle,
      ),
      child: Icon(icon, size: size * 0.52, color: solid ? t.onPrimary : fg),
    );
  }
}

/// Icon disc, title (+ optional subtitle lines), chevron. [leading] replaces
/// the disc when a row needs a custom glyph.
class ActionRow extends StatelessWidget {
  final IconData? icon;
  final Widget? leading;
  final Color? iconColor;

  /// A bare accent glyph instead of the tinted disc (the Settings rows).
  final bool plainIcon;
  final String title;
  final String? subtitle;
  final String? detail;
  final VoidCallback? onTap;
  final bool enabled;
  final Widget? trailing;

  const ActionRow({
    super.key,
    this.icon,
    this.leading,
    this.iconColor,
    this.plainIcon = false,
    required this.title,
    this.subtitle,
    this.detail,
    this.onTap,
    this.enabled = true,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Opacity(
      opacity: enabled ? 1 : 0.6,
      child: AppCard(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        onTap: enabled ? onTap : null,
        child: Row(
          children: [
            leading ??
                (plainIcon
                    ? SizedBox(width: 32, child: Icon(icon ?? Icons.circle, size: 24, color: iconColor ?? t.primary))
                    : null) ??
                IconDisc(
                  icon ?? Icons.circle,
                  color: iconColor ?? t.primary,
                  background: iconColor?.withValues(alpha: 0.1) ?? t.tint,
                ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppText.labelMd.copyWith(
                      color: t.ink,
                      fontWeight: subtitle == null ? FontWeight.w500 : FontWeight.w600,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 1),
                    Text(subtitle!, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                  ],
                  if (detail != null) Text(detail!, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                ],
              ),
            ),
            const SizedBox(width: AppSpace.sm),
            trailing ?? Icon(Icons.chevron_right, size: 20, color: t.inkMuted),
          ],
        ),
      ),
    );
  }
}

/// The "i" / shield banner at the foot of Forecast and Alerts.
class InfoBanner extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? body;
  final VoidCallback? onTap;
  const InfoBanner({super.key, required this.icon, required this.title, this.body, this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final radius = BorderRadius.circular(AppRadius.card);
    return Material(
      color: t.tint,
      borderRadius: radius,
      child: InkWell(
        borderRadius: radius,
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              IconDisc(icon, solid: true, size: 32),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                    ),
                    if (body != null) Text(body!, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                  ],
                ),
              ),
              if (onTap != null) Icon(Icons.chevron_right, size: 20, color: t.primary),
            ],
          ),
        ),
      ),
    );
  }
}
