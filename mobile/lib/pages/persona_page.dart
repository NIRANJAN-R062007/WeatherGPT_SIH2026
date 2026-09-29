// Persona selection — the pics/ persona mockups: one illustrated card per
// persona (accent-tinted scene, icon disc, name, tagline, four focus chips).
// Opened from Settings' "Change Persona" and Home's avatar; picking a card
// sets UiPrefs.persona (sent as /ask's `persona`) and closes the page.
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../components/app_shell.dart';
import '../components/scenery.dart';
import '../components/common.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';

Future<void> openPersonaPicker(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const PersonaPage()));
}

class PersonaPage extends StatelessWidget {
  const PersonaPage({super.key});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    return Scaffold(
      backgroundColor: AppColors.skyBottom,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.skyTop, AppColors.skyBottom],
            stops: [0, 0.35],
          ),
        ),
        child: Column(children: [
          SafeArea(
            bottom: false,
            child: SizedBox(
              height: 56,
              child: Row(children: [
                IconButton(
                  tooltip: 'Back',
                  icon: const Icon(Icons.arrow_back_rounded, color: AppColors.ink),
                  onPressed: () => Navigator.of(context).maybePop(),
                ),
                const BrandMark(),
                const SizedBox(width: AppSpace.sm),
                Text('WeatherGPT', style: AppText.headlineSm.copyWith(color: AppColors.ink, fontWeight: FontWeight.w700)),
              ]),
            ),
          ),
          Expanded(
            child: PageFrame(
              footer: SceneryFooter.waves,
              children: [
                const PageHeader(
                  title: 'Choose your persona',
                  subtitle: "Same trusted numbers, framed the way that's most useful for your role.",
                ),
                const SizedBox(height: AppSpace.lg),
                for (final p in kPersonas) ...[
                  PersonaCard(
                    persona: p,
                    selected: prefs.persona == p.id,
                    onTap: () {
                      prefs.persona = p.id;
                      Navigator.of(context).maybePop();
                    },
                  ),
                  const SizedBox(height: AppSpace.md),
                ],
              ],
            ),
          ),
        ]),
      ),
    );
  }
}

class PersonaCard extends StatelessWidget {
  final Persona persona;
  final bool selected;
  final VoidCallback onTap;
  const PersonaCard({super.key, required this.persona, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = persona;
    final radius = BorderRadius.circular(20);
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      button: true,
      child: DecoratedBox(
        decoration: BoxDecoration(borderRadius: radius, boxShadow: AppShadows.card),
        child: Material(
          color: AppColors.card,
          shape: RoundedRectangleBorder(
            borderRadius: radius,
            side: BorderSide(
              color: selected ? p.accent : p.accent.withValues(alpha: 0.3),
              width: selected ? 2 : 1,
            ),
          ),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              SizedBox(
                height: 118,
                child: Stack(children: [
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [p.soft, AppColors.card],
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    right: 0,
                    top: 0,
                    bottom: 0,
                    width: 170,
                    child: _Scene(persona: p),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(AppSpace.md, AppSpace.md, 120, AppSpace.md),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(color: p.accent, shape: BoxShape.circle),
                        child: Icon(p.icon, size: 26, color: AppColors.onPrimary),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(
                            p.label,
                            style: AppText.headlineMd.copyWith(color: AppColors.ink, fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 2),
                          Text(p.tagline, style: AppText.bodySm.copyWith(color: AppColors.inkMuted)),
                        ]),
                      ),
                    ]),
                  ),
                  Positioned(
                    top: 10,
                    right: 10,
                    child: Container(
                      decoration: const BoxDecoration(color: AppColors.card, shape: BoxShape.circle),
                      child: Icon(
                        selected ? Icons.check_circle : Icons.radio_button_unchecked,
                        size: 22,
                        color: selected ? p.accent : AppColors.outline,
                      ),
                    ),
                  ),
                ]),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: Column(children: [
                  for (var row = 0; row < p.features.length; row += 2)
                    Padding(
                      padding: EdgeInsets.only(top: row == 0 ? 0 : AppSpace.sm),
                      child: Row(children: [
                        Expanded(child: _FeatureChip(p.features[row], p)),
                        const SizedBox(width: AppSpace.sm),
                        Expanded(
                          child: row + 1 < p.features.length
                              ? _FeatureChip(p.features[row + 1], p)
                              : const SizedBox.shrink(),
                        ),
                      ]),
                    ),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  final PersonaFeature feature;
  final Persona persona;
  const _FeatureChip(this.feature, this.persona);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: persona.soft,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Row(children: [
        Icon(feature.icon, size: 18, color: persona.accent),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            feature.label,
            maxLines: 2,
            style: AppText.bodySm.copyWith(color: AppColors.ink, height: 1.25),
          ),
        ),
      ]),
    );
  }
}

/// The painted vignette on the right of a persona card.
class _Scene extends StatelessWidget {
  final Persona persona;
  const _Scene({required this.persona});

  @override
  Widget build(BuildContext context) {
    final accent = persona.accent;
    final Widget ground = switch (persona.scene) {
      PersonaScene.city => const CustomPaint(painter: SkylinePainter(seed: 5)),
      PersonaScene.river => const CustomPaint(painter: SkylinePainter(seed: 17)),
      PersonaScene.fields => const CustomPaint(painter: _FieldsPainter()),
      PersonaScene.sea => const CustomPaint(painter: WavesPainter()),
      PersonaScene.sky => const CustomPaint(painter: CloudsPainter()),
    };
    return ShaderMask(
      // Fade the scene in from the left so the text side stays clean.
      shaderCallback: (rect) => const LinearGradient(
        colors: [Color(0x00000000), Color(0xFF000000)],
        stops: [0, 0.45],
      ).createShader(rect),
      blendMode: BlendMode.dstIn,
      child: Stack(children: [
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          height: persona.scene == PersonaScene.sky ? 118 : 64,
          child: ground,
        ),
        if (persona.scene == PersonaScene.city)
          const Positioned(right: 56, top: 26, child: Icon(Icons.circle, size: 22, color: AppColors.sunCore)),
        if (persona.scene == PersonaScene.river)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            height: 14,
            child: ColoredBox(color: AppColors.waterDeep.withValues(alpha: 0.9)),
          ),
        if (persona.scene == PersonaScene.sea)
          Positioned(right: 34, bottom: 22, child: Icon(Icons.directions_boat_filled, size: 40, color: accent)),
        if (persona.scene == PersonaScene.sky)
          Positioned(
            right: 18,
            top: 22,
            child: Transform.rotate(
              angle: math.pi / 4,
              child: Icon(Icons.flight, size: 54, color: accent.withValues(alpha: 0.85)),
            ),
          ),
        if (persona.scene == PersonaScene.fields)
          Positioned(right: 30, bottom: 22, child: Icon(Icons.agriculture, size: 34, color: accent)),
      ]),
    );
  }
}

/// Rolling green hills with crop rows.
class _FieldsPainter extends CustomPainter {
  const _FieldsPainter();

  @override
  void paint(Canvas canvas, Size size) {
    Path hill(double y0, double y1, double bulge) => Path()
      ..moveTo(0, size.height)
      ..lineTo(0, size.height * y0)
      ..quadraticBezierTo(size.width * 0.5, size.height * bulge, size.width, size.height * y1)
      ..lineTo(size.width, size.height)
      ..close();

    canvas.drawPath(hill(0.35, 0.15, -0.05), Paint()..color = AppColors.foliage.withValues(alpha: 0.55));
    canvas.drawPath(hill(0.7, 0.45, 0.3), Paint()..color = AppColors.foliage);
    final rows = Paint()
      ..color = AppColors.foliageDeep.withValues(alpha: 0.6)
      ..strokeWidth = 1.5;
    for (var i = 0; i < 7; i++) {
      final x = size.width * (0.1 + i * 0.14);
      canvas.drawLine(Offset(x, size.height), Offset(x + size.width * 0.12, size.height * 0.62), rows);
    }
  }

  @override
  bool shouldRepaint(_FieldsPainter old) => false;
}
