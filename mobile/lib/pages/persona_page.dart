// Persona selection — the pics/ persona mockups: one illustrated card per
// persona (its own palette and painted scene, icon disc, name, tagline, four
// focus chips). Opened from Settings' "Change Persona" and Home's avatar.
// Picking a card sets UiPrefs.persona, which is both /ask's `persona` param
// and the app-wide theme: the whole app (this page included) cross-fades to
// that persona's PersonaTheme, then the page closes.
import 'package:flutter/material.dart';

import '../components/app_shell.dart';
import '../components/common.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import '../i18n.dart';

Future<void> openPersonaPicker(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const PersonaPage()));
}

class PersonaPage extends StatelessWidget {
  const PersonaPage({super.key});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
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
                    IconButton(
                      tooltip: tr(context, 'Back'),
                      icon: Icon(Icons.arrow_back_rounded, color: t.ink),
                      onPressed: () => Navigator.of(context).maybePop(),
                    ),
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
            Expanded(
              child: PageFrame(
                footer: SceneryFooter.soft,
                children: [
                  const PageHeader(
                    title: 'Choose your persona',
                    subtitle:
                        "Same trusted numbers, framed the way that's most useful for your role. "
                        'The whole app takes on the persona you pick.',
                  ),
                  const SizedBox(height: AppSpace.lg),
                  _YourPersona(persona: prefs.personaInfo),
                  const SizedBox(height: AppSpace.lg),
                  const SectionTitle('All personas'),
                  const SizedBox(height: AppSpace.sm),
                  for (final p in kPersonas) ...[
                    PersonaCard(
                      persona: p,
                      selected: prefs.persona == p.id,
                      onTap: () async {
                        final navigator = Navigator.of(context);
                        prefs.persona = p.id;
                        // Let the app-wide re-theme show before closing.
                        await Future<void>.delayed(const Duration(milliseconds: 320));
                        navigator.maybePop();
                      },
                    ),
                    const SizedBox(height: AppSpace.md),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One persona, drawn in its own theme whatever the active persona is.
class PersonaCard extends StatelessWidget {
  final Persona persona;
  final bool selected;
  final VoidCallback onTap;
  const PersonaCard({super.key, required this.persona, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = persona;
    final t = personaThemeFor(p.id, PersonaTheme.of(context).brightness);
    final radius = BorderRadius.circular(20);
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      button: true,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          borderRadius: radius,
          boxShadow: [
            BoxShadow(
              color: t.shadow.withValues(alpha: selected ? 0.22 : 0.08),
              blurRadius: selected ? 18 : 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Material(
          color: t.card,
          shape: RoundedRectangleBorder(
            borderRadius: radius,
            side: BorderSide(color: selected ? t.primary : t.primary.withValues(alpha: 0.3), width: selected ? 2 : 1),
          ),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            splashColor: t.primary.withValues(alpha: 0.12),
            highlightColor: t.tint,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ConstrainedBox(
                  // Grows with a long tagline or large text.
                  constraints: const BoxConstraints(minHeight: 118),
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [t.card, t.skyBottom, t.skyTop],
                              stops: const [0.2, 0.6, 1],
                            ),
                          ),
                        ),
                      ),
                      Positioned(
                        right: 0,
                        top: 0,
                        bottom: 0,
                        width: 190,
                        child: ShaderMask(
                          // Fade the scene in from the left so the text side stays clean.
                          shaderCallback: (rect) => const LinearGradient(
                            colors: [Color(0x00000000), Color(0xFF000000)],
                            stops: [0, 0.45],
                          ).createShader(rect),
                          blendMode: BlendMode.dstIn,
                          child: PersonaScenery(SceneSlot.card, theme: t),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(AppSpace.md, AppSpace.md, 120, AppSpace.md),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              width: 48,
                              height: 48,
                              decoration: BoxDecoration(gradient: t.accentGradient, shape: BoxShape.circle),
                              child: Icon(p.icon, size: 26, color: t.onPrimary),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    tr(context, p.label),
                                    style: AppText.headlineMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(tr(context, p.tagline), style: AppText.bodySm.copyWith(color: t.inkMuted)),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      Positioned(
                        top: 10,
                        right: 10,
                        child: Container(
                          decoration: BoxDecoration(color: t.card, shape: BoxShape.circle),
                          child: Icon(
                            selected ? Icons.check_circle : Icons.radio_button_unchecked,
                            size: 22,
                            color: selected ? t.primary : t.outline,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                  child: Column(
                    children: [
                      for (var row = 0; row < p.features.length; row += 2)
                        Padding(
                          padding: EdgeInsets.only(top: row == 0 ? 0 : AppSpace.sm),
                          child: Row(
                            children: [
                              Expanded(child: _FeatureChip(p.features[row], t)),
                              const SizedBox(width: AppSpace.sm),
                              Expanded(
                                child: row + 1 < p.features.length
                                    ? _FeatureChip(p.features[row + 1], t)
                                    : const SizedBox.shrink(),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  final PersonaFeature feature;
  final PersonaTheme t;
  const _FeatureChip(this.feature, this.t);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(AppRadius.xl)),
      child: Row(
        children: [
          Icon(feature.icon, size: 18, color: t.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              tr(context, feature.label),
              maxLines: 2,
              style: AppText.bodySm.copyWith(color: t.ink, height: 1.25),
            ),
          ),
        ],
      ),
    );
  }
}

/// "You're viewing the app as …" plus what that persona frames (the
/// pics/ "Your Persona" panel).
class _YourPersona extends StatelessWidget {
  final Persona persona;
  const _YourPersona({required this.persona});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return AppCard(
      wash: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              IconDisc(Icons.verified_user_outlined, size: 40, background: t.card),
              const SizedBox(width: 12),
              Expanded(
                child: Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(text: '${tr(context, "You're viewing the app as")}\n'),
                      TextSpan(
                        text: tr(context, persona.label),
                        style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                  style: AppText.bodyMd.copyWith(color: t.inkMuted),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            tr(context, 'What you get'),
            style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          for (final f in persona.features)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                children: [
                  Icon(Icons.check_rounded, size: 18, color: t.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(tr(context, f.label), style: AppText.bodyMd.copyWith(color: t.ink)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
