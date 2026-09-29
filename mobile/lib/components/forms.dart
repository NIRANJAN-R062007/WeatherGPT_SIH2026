// Form pieces for the landing, sign-in and profile pages, in the active
// persona's colours: the sky-backed sub-page scaffold, the rounded text
// field, and the two button styles (accent gradient, outlined).
import 'package:flutter/material.dart';

import '../persona_theme.dart';
import '../theme.dart';
import 'app_shell.dart';
import 'common.dart';

/// Sky gradient, a back arrow + WeatherGPT bar, then [body].
class SubPageScaffold extends StatelessWidget {
  final Widget body;
  final bool showBack;
  const SubPageScaffold({super.key, required this.body, this.showBack = true});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Scaffold(
      backgroundColor: t.skyBottom,
      body: DecoratedBox(
        decoration: BoxDecoration(gradient: t.skyGradient),
        child: Column(
          children: [
            SafeArea(
              bottom: false,
              child: SizedBox(
                height: 56,
                child: Row(
                  children: [
                    if (showBack)
                      IconButton(
                        tooltip: 'Back',
                        icon: Icon(Icons.arrow_back_rounded, color: t.ink),
                        onPressed: () => Navigator.of(context).maybePop(),
                      )
                    else
                      const SizedBox(width: AppSpace.md),
                    const BrandMark(),
                    const SizedBox(width: AppSpace.sm),
                    Text(
                      'WeatherGPT',
                      style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(child: body),
          ],
        ),
      ),
    );
  }
}

/// A labelled, rounded input on a white card with a persona-tinted border.
class AppTextField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final String? hint;
  final TextInputType? keyboardType;
  final TextInputAction textInputAction;
  final bool obscure;
  final Widget? suffix;
  final Iterable<String>? autofillHints;
  final FormFieldValidator<String>? validator;
  final ValueChanged<String>? onSubmitted;
  final TextCapitalization capitalization;
  final bool enabled;

  const AppTextField({
    super.key,
    required this.controller,
    required this.label,
    required this.icon,
    this.hint,
    this.keyboardType,
    this.textInputAction = TextInputAction.next,
    this.obscure = false,
    this.suffix,
    this.autofillHints,
    this.validator,
    this.onSubmitted,
    this.capitalization = TextCapitalization.none,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    OutlineInputBorder border(Color c, [double w = 1]) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(AppRadius.card),
      borderSide: BorderSide(color: c, width: w),
    );
    return TextFormField(
      controller: controller,
      enabled: enabled,
      obscureText: obscure,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      textCapitalization: capitalization,
      autofillHints: autofillHints,
      validator: validator,
      onFieldSubmitted: onSubmitted,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      style: AppText.bodyMd.copyWith(color: t.ink),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        isDense: false,
        filled: true,
        fillColor: t.card,
        labelStyle: AppText.bodyMd.copyWith(color: t.inkMuted),
        floatingLabelStyle: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w600),
        hintStyle: AppText.bodyMd.copyWith(color: t.outline),
        prefixIcon: Icon(icon, size: 20, color: t.primary),
        suffixIcon: suffix,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
        border: border(t.cardBorder),
        enabledBorder: border(t.cardBorder),
        focusedBorder: border(t.primary, 1.6),
        errorBorder: border(AppColors.error),
        focusedErrorBorder: border(AppColors.error, 1.6),
        errorStyle: AppText.bodySm.copyWith(color: AppColors.error),
        errorMaxLines: 2,
      ),
    );
  }
}

/// Full-width accent-gradient button; shows a spinner while [loading].
class GradientButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool loading;
  const GradientButton({super.key, required this.label, this.icon, this.onPressed, this.loading = false});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final radius = BorderRadius.circular(AppRadius.card);
    final enabled = onPressed != null && !loading;
    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      excludeSemantics: true,
      child: Opacity(
        opacity: onPressed == null ? 0.6 : 1,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: t.accentGradient,
            borderRadius: radius,
            boxShadow: [
              BoxShadow(color: t.primary.withValues(alpha: 0.28), blurRadius: 14, offset: const Offset(0, 5)),
            ],
          ),
          child: Material(
            color: Colors.transparent,
            borderRadius: radius,
            child: InkWell(
              borderRadius: radius,
              onTap: enabled ? onPressed : null,
              child: SizedBox(
                height: 52,
                child: Center(
                  child: loading
                      ? InlineSpinner(size: 22, color: t.onPrimary, track: t.onPrimary.withValues(alpha: 0.35))
                      : Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Flexible(
                              child: Text(
                                label,
                                overflow: TextOverflow.ellipsis,
                                style: AppText.labelMd.copyWith(
                                  color: t.onPrimary,
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            if (icon != null) ...[const SizedBox(width: 8), Icon(icon, size: 18, color: t.onPrimary)],
                          ],
                        ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Full-width white button with an accent outline (secondary action), or a
/// red one for [destructive] actions like signing out.
class OutlineActionButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool destructive;
  const OutlineActionButton({super.key, required this.label, this.icon, this.onPressed, this.destructive = false});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fg = destructive ? AppColors.error : t.primary;
    final radius = BorderRadius.circular(AppRadius.card);
    return Material(
      color: t.card,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: BorderSide(color: fg.withValues(alpha: 0.55), width: 1.4),
      ),
      child: InkWell(
        borderRadius: radius,
        onTap: onPressed,
        child: SizedBox(
          height: 52,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (icon != null) ...[Icon(icon, size: 19, color: fg), const SizedBox(width: 8)],
              Flexible(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.labelMd.copyWith(color: fg, fontSize: 15, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
