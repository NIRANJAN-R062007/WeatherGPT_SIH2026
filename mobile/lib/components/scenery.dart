// The illustrated page chrome of the redesign (pics/ mockups): a pale sky
// with clouds, a city skyline with trees along its foot, and soft water
// waves. All painted — no image assets — from the AppColors mockup tokens,
// so dark mode only has to change those tokens.
//
// PageFrame is what every page renders into: the city pill and skyline at
// the top, then the rounded content sheet, with a scenery strip at its foot.
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../state/ui_prefs.dart';
import '../theme.dart';
import 'common.dart';

/// Deterministic pseudo-random stream, so the skyline is the same on every
/// frame and every launch.
class _Rng {
  int _s;
  _Rng(this._s);
  double next() {
    _s = (_s * 1103515245 + 12345) & 0x7fffffff;
    return _s / 0x7fffffff;
  }
}

/// Two layers of towers (a pale far one, a stronger near one with lit
/// windows) and a hedge of rounded trees along the base.
class SkylinePainter extends CustomPainter {
  final int seed;
  final bool trees;
  final double opacity;
  const SkylinePainter({this.seed = 7, this.trees = true, this.opacity = 1});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final treeBand = trees ? math.min(16.0, size.height * 0.22) : 0.0;
    final base = size.height - treeBand * 0.55;
    _towers(canvas, size, base, _Rng(seed), AppColors.skylineFar, 0.35, 0.9, windows: false);
    _towers(canvas, size, base, _Rng(seed * 31 + 3), AppColors.skylineNear, 0.2, 0.62, windows: true);
    if (trees) _hedge(canvas, size, treeBand);
  }

  void _towers(Canvas canvas, Size size, double base, _Rng r, Color color, double minH, double maxH,
      {required bool windows}) {
    final paint = Paint()..color = color.withValues(alpha: opacity);
    final lit = Paint()..color = AppColors.skylineWindow.withValues(alpha: 0.75 * opacity);
    final span = base;
    var x = -r.next() * 12;
    while (x < size.width) {
      final w = 11 + r.next() * 20;
      final h = span * (minH + r.next() * (maxH - minH));
      final top = base - h;
      canvas.drawRect(Rect.fromLTWH(x, top, w, h), paint);
      final roll = r.next();
      if (roll > 0.82) {
        // antenna
        canvas.drawRect(Rect.fromLTWH(x + w / 2 - 0.75, top - h * 0.18, 1.5, h * 0.18), paint);
      } else if (roll > 0.64) {
        // stepped crown
        canvas.drawRect(Rect.fromLTWH(x + w * 0.2, top - 5, w * 0.6, 5), paint);
      }
      if (windows && w > 15 && h > 22) {
        for (var wy = top + 5; wy < base - 6; wy += 6) {
          for (var wx = x + 3; wx < x + w - 4; wx += 5) {
            canvas.drawRect(Rect.fromLTWH(wx, wy, 2.2, 2.6), lit);
          }
        }
      }
      x += w + r.next() * 7 - 1;
    }
  }

  void _hedge(Canvas canvas, Size size, double band) {
    final r = _Rng(seed + 101);
    final light = Paint()..color = AppColors.foliage.withValues(alpha: opacity);
    final deep = Paint()..color = AppColors.foliageDeep.withValues(alpha: opacity);
    canvas.drawRect(Rect.fromLTWH(0, size.height - band * 0.45, size.width, band * 0.45), light);
    var x = -4.0;
    while (x < size.width + 8) {
      final rad = band * (0.35 + r.next() * 0.35);
      canvas.drawCircle(Offset(x, size.height - rad * 0.9), rad, r.next() > 0.55 ? deep : light);
      x += rad * (1.1 + r.next() * 0.9);
    }
  }

  @override
  bool shouldRepaint(SkylinePainter old) => old.seed != seed || old.trees != trees || old.opacity != opacity;
}

/// Soft cloud puffs drifting across the sky band.
class CloudsPainter extends CustomPainter {
  const CloudsPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = AppColors.cloudPuff.withValues(alpha: 0.75);
    void puff(double cx, double cy, double s) {
      canvas.drawOval(Rect.fromCenter(center: Offset(cx, cy), width: 46 * s, height: 16 * s), paint);
      canvas.drawCircle(Offset(cx - 8 * s, cy - 5 * s), 9 * s, paint);
      canvas.drawCircle(Offset(cx + 6 * s, cy - 7 * s), 11 * s, paint);
    }

    puff(size.width * 0.12, size.height * 0.30, 1.0);
    puff(size.width * 0.62, size.height * 0.18, 0.8);
    puff(size.width * 0.92, size.height * 0.42, 1.1);
  }

  @override
  bool shouldRepaint(CloudsPainter old) => false;
}

/// Two layered swells filling the bottom of the box.
class WavesPainter extends CustomPainter {
  final double opacity;
  const WavesPainter({this.opacity = 1});

  @override
  void paint(Canvas canvas, Size size) {
    Path wave(double baseY, double amp, double phase) {
      final p = Path()..moveTo(0, size.height);
      p.lineTo(0, baseY);
      const steps = 24;
      for (var i = 0; i <= steps; i++) {
        final x = size.width * i / steps;
        final y = baseY + math.sin(i / steps * math.pi * 2.2 + phase) * amp;
        p.lineTo(x, y);
      }
      p
        ..lineTo(size.width, size.height)
        ..close();
      return p;
    }

    canvas.drawPath(
      wave(size.height * 0.35, size.height * 0.12, 0.4),
      Paint()..color = AppColors.water.withValues(alpha: opacity),
    );
    canvas.drawPath(
      wave(size.height * 0.62, size.height * 0.10, 2.1),
      Paint()..color = AppColors.waterDeep.withValues(alpha: opacity),
    );
  }

  @override
  bool shouldRepaint(WavesPainter old) => old.opacity != opacity;
}

enum SceneryFooter { none, skyline, waves }

/// The strip under the top bar: the city pill over clouds and a skyline.
class SceneryHeader extends StatelessWidget {
  static const double height = 112;
  const SceneryHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      child: Stack(children: [
        const Positioned.fill(child: CustomPaint(painter: CloudsPainter())),
        const Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          height: 70,
          child: CustomPaint(painter: SkylinePainter(seed: 11)),
        ),
        const Positioned(top: 4, left: 0, right: 0, child: Center(child: CityPill())),
      ]),
    );
  }
}

/// The white city chip: pin, "City, Region", chevron — opens the picker.
class CityPill extends StatelessWidget {
  const CityPill({super.key});

  @override
  Widget build(BuildContext context) {
    final city = UiPrefs.of(context).cityInfo;
    final shape = BorderRadius.circular(999);
    return DecoratedBox(
      decoration: BoxDecoration(borderRadius: shape, boxShadow: AppShadows.card),
      child: Material(
        color: AppColors.card,
        borderRadius: shape,
        child: InkWell(
          borderRadius: shape,
          onTap: () => showCityPicker(context),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 9, 12, 9),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.location_on, size: 18, color: AppColors.primary),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 220),
                child: Text(
                  '${city.name}, ${city.region}',
                  overflow: TextOverflow.ellipsis,
                  style: AppText.labelMd.copyWith(color: AppColors.ink, fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: 10),
              const Icon(Icons.keyboard_arrow_down, size: 18, color: AppColors.inkMuted),
            ]),
          ),
        ),
      ),
    );
  }
}

/// A page: scenery header, then the rounded sheet holding [children], with
/// the [footer] scenery pinned to the sheet's foot. Short pages still fill
/// the screen; long ones scroll header and all. [dock] sits under the scroll
/// (Chat's composer).
class PageFrame extends StatelessWidget {
  final List<Widget> children;
  final Future<void> Function()? onRefresh;
  final SceneryFooter footer;
  final ScrollController? controller;
  final Widget? dock;

  const PageFrame({
    super.key,
    required this.children,
    this.onRefresh,
    this.footer = SceneryFooter.skyline,
    this.controller,
    this.dock,
  });

  static const double _footerHeight = 72;

  @override
  Widget build(BuildContext context) {
    Widget scroll = LayoutBuilder(
      builder: (context, constraints) {
        final minSheet = math.max(0.0, constraints.maxHeight - SceneryHeader.height);
        return ListView(
          controller: controller,
          padding: EdgeInsets.zero,
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            const SceneryHeader(),
            ConstrainedBox(
              constraints: BoxConstraints(minHeight: minSheet),
              child: DecoratedBox(
                decoration: const BoxDecoration(
                  color: AppColors.sheet,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.sheet)),
                  boxShadow: [BoxShadow(color: Color(0x0F1D6AE5), blurRadius: 16, offset: Offset(0, -2))],
                ),
                child: ClipRRect(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.sheet)),
                  child: Stack(children: [
                    Padding(
                      padding: EdgeInsets.fromLTRB(
                        AppSpace.gutter + 4,
                        AppSpace.lg,
                        AppSpace.gutter + 4,
                        footer == SceneryFooter.none ? AppSpace.lg : _footerHeight + AppSpace.md,
                      ),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
                    ),
                    if (footer != SceneryFooter.none)
                      Positioned(
                        left: 0,
                        right: 0,
                        bottom: 0,
                        height: _footerHeight,
                        child: IgnorePointer(
                          child: CustomPaint(
                            painter: footer == SceneryFooter.waves
                                ? const WavesPainter(opacity: 0.9)
                                : const SkylinePainter(seed: 23, opacity: 0.8),
                          ),
                        ),
                      ),
                  ]),
                ),
              ),
            ),
          ],
        );
      },
    );
    if (onRefresh != null) scroll = RefreshIndicator(onRefresh: onRefresh!, child: scroll);
    if (dock == null) return scroll;
    return Column(children: [Expanded(child: scroll), dock!]);
  }
}
