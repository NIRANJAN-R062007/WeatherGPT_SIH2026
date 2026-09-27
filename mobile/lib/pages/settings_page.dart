// Settings — web/src/pages/SettingsPage.tsx's Language, Units and Persona
// cards. Language reaches /ask, /facts, /warnings and voice; Persona reaches
// /ask's `persona` param (web/ shows the picker but doesn't send it). The
// web page's Account and Notifications cards are left out: there is no
// sign-in flow in this app, and proactive pushes need a push channel
// (POST /alerts/subscribe takes an FCM token or webhook) it doesn't have.
import 'package:flutter/material.dart';

import '../components/common.dart';
import '../config.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    return ListView(
      padding: const EdgeInsets.all(AppSpace.gutter),
      children: [
        const PageHeader(
          title: 'Settings',
          subtitle: 'These preferences change how WeatherGPT frames answers — never the underlying data.',
        ),
        const SizedBox(height: AppSpace.lg),
        SectionCard(
          title: 'Language',
          icon: Icons.translate,
          subtitle: 'Answers, warning text, voice input and playback all follow this language.',
          children: [
            Wrap(spacing: AppSpace.sm, runSpacing: AppSpace.sm, children: [
              for (final code in kSupportedLanguages)
                _LangPill(
                  label: kLanguageLabels[code] ?? code,
                  selected: prefs.lang == code,
                  onTap: () => prefs.lang = code,
                ),
            ]),
          ],
        ),
        const SizedBox(height: AppSpace.lg),
        SectionCard(
          title: 'Units',
          icon: Icons.straighten,
          subtitle: 'Applies to temperatures on Home and Forecast; narrated answers keep the service\'s units.',
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: AppColors.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  _Segment(
                    label: 'Celsius (°C)',
                    selected: prefs.unit == TempUnit.celsius,
                    onTap: () => prefs.unit = TempUnit.celsius,
                  ),
                  _Segment(
                    label: 'Fahrenheit (°F)',
                    selected: prefs.unit == TempUnit.fahrenheit,
                    onTap: () => prefs.unit = TempUnit.fahrenheit,
                  ),
                ]),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpace.lg),
        SectionCard(
          title: 'Persona',
          icon: Icons.tune,
          subtitle: 'Same trusted numbers, framed the way that\'s most useful for your role.',
          children: [
            for (final p in kPersonas) ...[
              _PersonaCard(persona: p, selected: prefs.persona == p.id, onTap: () => prefs.persona = p.id),
              const SizedBox(height: AppSpace.sm),
            ],
          ],
        ),
      ],
    );
  }
}

class _LangPill extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _LangPill({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: selected,
      button: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(999),
          boxShadow: selected ? AppShadows.sm : null,
        ),
        child: Material(
          color: selected ? AppColors.primary : AppColors.surfaceContainerLow,
          borderRadius: BorderRadius.circular(999),
          child: InkWell(
            borderRadius: BorderRadius.circular(999),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: AppSpace.sm),
              child: Text(
                label,
                style: AppText.labelMd.copyWith(
                  color: selected ? AppColors.onPrimary : AppColors.onSurfaceVariant,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Segment extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _Segment({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: selected,
      button: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(999),
          boxShadow: selected ? AppShadows.sm : null,
        ),
        child: Material(
          color: selected ? AppColors.surfaceContainerLowest : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
          child: InkWell(
            borderRadius: BorderRadius.circular(999),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 6),
              child: Text(
                label,
                style: AppText.labelMd.copyWith(
                  color: selected ? AppColors.onSurface : AppColors.onSurfaceVariant,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// `border border-outline-variant has-[:checked]:border-primary
/// has-[:checked]:bg-surface-container-low` radio card.
class _PersonaCard extends StatelessWidget {
  final Persona persona;
  final bool selected;
  final VoidCallback onTap;
  const _PersonaCard({required this.persona, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(AppRadius.lg);
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      button: true,
      child: Material(
        color: selected ? AppColors.surfaceContainerLow : Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: radius,
          side: BorderSide(color: selected ? AppColors.primary : AppColors.outlineVariant),
        ),
        child: InkWell(
          borderRadius: radius,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(
                selected ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                size: 20,
                color: selected ? AppColors.primary : AppColors.outline,
              ),
              const SizedBox(width: 12),
              Icon(persona.icon, size: 20, color: AppColors.onSurfaceVariant),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(persona.label, style: AppText.labelMd.copyWith(fontWeight: FontWeight.w600)),
                  Text(persona.blurb, style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant)),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
