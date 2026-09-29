// Settings — the pics/ mockup: the persona profile card with "Change
// Persona", then one row per preference (Language, Units, Location,
// Appearance, About), each opening a picker sheet. Language reaches /ask,
// /facts, /warnings and voice; Persona reaches /ask's `persona` param.
// Appearance is light-only until dark mode lands. There is no Account or
// Notifications row: the app has no sign-in flow, and proactive pushes need
// a push channel (POST /alerts/subscribe takes an FCM token or webhook) it
// doesn't have.
import 'package:flutter/material.dart';

import '../components/common.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../config.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import 'persona_page.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final city = prefs.cityInfo;
    final rows = <Widget>[
      ActionRow(
        icon: Icons.language,
        title: 'Language',
        subtitle: kLanguageLabels[prefs.lang] ?? prefs.lang,
        onTap: () => _pick<String>(
          context,
          title: 'Language',
          note: 'Answers, warning text, voice input and playback all follow this language.',
          options: [for (final code in kSupportedLanguages) _Option(code, kLanguageLabels[code] ?? code)],
          selected: prefs.lang,
          onPick: (v) => prefs.lang = v,
        ),
      ),
      ActionRow(
        icon: Icons.device_thermostat,
        title: 'Units',
        subtitle: prefs.unit == TempUnit.celsius ? 'Celsius (°C)' : 'Fahrenheit (°F)',
        onTap: () => _pick<TempUnit>(
          context,
          title: 'Units',
          note: "Applies to temperatures on Home and Forecast; narrated answers keep the service's units.",
          options: const [
            _Option(TempUnit.celsius, 'Celsius (°C)'),
            _Option(TempUnit.fahrenheit, 'Fahrenheit (°F)'),
          ],
          selected: prefs.unit,
          onPick: (v) => prefs.unit = v,
        ),
      ),
      ActionRow(
        icon: Icons.location_on_outlined,
        title: 'Location',
        subtitle: '${city.name}, ${city.region}',
        onTap: () => showCityPicker(context),
      ),
      ActionRow(
        icon: Icons.light_mode_outlined,
        title: 'Appearance',
        subtitle: 'Light Mode',
        onTap: () => _pick<String>(
          context,
          title: 'Appearance',
          options: const [
            _Option('light', 'Light Mode'),
            _Option('dark', 'Dark Mode', enabled: false, detail: 'Coming soon'),
          ],
          selected: 'light',
          onPick: (_) {},
        ),
      ),
      ActionRow(
        icon: Icons.info_outline,
        title: 'About',
        subtitle: 'WeatherGPT v$kAppVersion',
        onTap: () => showAboutDialog(
          context: context,
          applicationName: 'WeatherGPT',
          applicationVersion: 'v$kAppVersion',
          applicationIcon: const IconDisc(Icons.cloud, solid: true),
          children: [
            Text(
              'Grounded weather answers in English, हिन्दी, தமிழ், తెలుగు and मराठी. Every number '
              'is checked against the source data before you see it.',
              style: AppText.bodyMd.copyWith(color: AppColors.inkMuted),
            ),
          ],
        ),
      ),
    ];

    return PageFrame(
      children: [
        const PageHeader(title: 'Settings', subtitle: 'Manage your preferences and experience.'),
        const SizedBox(height: AppSpace.lg),
        _ProfileCard(persona: prefs.personaInfo),
        const SizedBox(height: AppSpace.lg),
        for (final row in rows) ...[row, const SizedBox(height: AppSpace.sm)],
      ],
    );
  }
}

class _ProfileCard extends StatelessWidget {
  final Persona persona;
  const _ProfileCard({required this.persona});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      color: AppColors.tint,
      borderColor: AppColors.tintStrong,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          IconDisc(persona.icon, color: persona.accent, solid: true, size: 52),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(
                persona.label,
                style: AppText.headlineSm.copyWith(color: AppColors.ink, fontWeight: FontWeight.w700),
              ),
              Text(persona.tagline, style: AppText.bodySm.copyWith(color: AppColors.inkMuted)),
            ]),
          ),
        ]),
        const SizedBox(height: 12),
        Align(
          alignment: Alignment.centerRight,
          child: Material(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(AppRadius.lg),
            child: InkWell(
              borderRadius: BorderRadius.circular(AppRadius.lg),
              onTap: () => openPersonaPicker(context),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                child: Text(
                  'Change Persona',
                  style: AppText.labelMd.copyWith(color: AppColors.primary, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

class _Option<T> {
  final T value;
  final String label;
  final bool enabled;
  final String? detail;
  const _Option(this.value, this.label, {this.enabled = true, this.detail});
}

Future<void> _pick<T>(
  BuildContext context, {
  required String title,
  String? note,
  required List<_Option<T>> options,
  required T selected,
  required ValueChanged<T> onPick,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (sheetContext) => SafeArea(
      top: false,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(AppSpace.md, 0, AppSpace.md, AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(title, style: AppText.headlineSm.copyWith(color: AppColors.ink)),
          if (note != null) ...[
            const SizedBox(height: 2),
            Text(note, style: AppText.bodySm.copyWith(color: AppColors.inkMuted)),
          ],
          const SizedBox(height: AppSpace.md),
          for (final o in options) ...[
            _OptionTile(
              label: o.label,
              detail: o.detail,
              selected: o.value == selected,
              enabled: o.enabled,
              onTap: () {
                onPick(o.value);
                Navigator.of(sheetContext).pop();
              },
            ),
            const SizedBox(height: AppSpace.sm),
          ],
        ]),
      ),
    ),
  );
}

class _OptionTile extends StatelessWidget {
  final String label;
  final String? detail;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;
  const _OptionTile({
    required this.label,
    required this.selected,
    required this.enabled,
    required this.onTap,
    this.detail,
  });

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(AppRadius.xl);
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      button: true,
      enabled: enabled,
      child: Opacity(
        opacity: enabled ? 1 : 0.5,
        child: Material(
          color: selected ? AppColors.tint : AppColors.card,
          shape: RoundedRectangleBorder(
            borderRadius: radius,
            side: BorderSide(color: selected ? AppColors.primary : AppColors.cardBorder),
          ),
          child: InkWell(
            borderRadius: radius,
            onTap: enabled ? onTap : null,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 12),
              child: Row(children: [
                Expanded(
                  child: Text(
                    label,
                    style: AppText.labelMd.copyWith(
                      color: AppColors.ink,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                ),
                if (detail != null) Text(detail!, style: AppText.bodySm.copyWith(color: AppColors.inkMuted)),
                if (selected) const Icon(Icons.check_circle, size: 20, color: AppColors.primary),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
