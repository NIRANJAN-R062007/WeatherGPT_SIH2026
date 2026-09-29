// The illustrated page chrome (pics/ mockups), painted per persona — no
// image assets. Each persona's PersonaTheme names a PersonaScene and the
// colours it's painted in:
//   city    → skyline with trees and a sun          (General Citizen)
//   fields  → hills, crop rows, trees and a tractor (Farmer)
//   sea     → islands, swells, a boat and gulls     (Fisherman)
//   airport → terminal, control tower, runway, jet  (Aviation)
//   civic   → skyline, bridge, river and rain       (City Official)
//
// PageFrame is what every page renders into: the city pill over the
// persona's scene at the top, then the rounded content sheet, with a
// scenery strip at its foot.
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import 'common.dart';

/// Deterministic pseudo-random stream, so the artwork is the same on every
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
  final PersonaTheme t;
  final int seed;
  final bool trees;
  final double opacity;
  const SkylinePainter(this.t, {this.seed = 7, this.trees = true, this.opacity = 1});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final treeBand = trees ? math.min(16.0, size.height * 0.22) : 0.0;
    final base = size.height - treeBand * 0.55;
    _towers(canvas, size, base, _Rng(seed), t.skylineFar, 0.35, 0.9, windows: false);
    _towers(canvas, size, base, _Rng(seed * 31 + 3), t.skylineNear, 0.2, 0.62, windows: true);
    if (trees) _hedge(canvas, size, treeBand);
  }

  void _towers(Canvas canvas, Size size, double base, _Rng r, Color color, double minH, double maxH,
      {required bool windows}) {
    final paint = Paint()..color = color.withValues(alpha: opacity);
    final lit = Paint()..color = t.skylineWindow.withValues(alpha: 0.75 * opacity);
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
    final light = Paint()..color = t.foliage.withValues(alpha: opacity);
    final deep = Paint()..color = t.foliageDeep.withValues(alpha: opacity);
    canvas.drawRect(Rect.fromLTWH(0, size.height - band * 0.45, size.width, band * 0.45), light);
    var x = -4.0;
    while (x < size.width + 8) {
      final rad = band * (0.35 + r.next() * 0.35);
      canvas.drawCircle(Offset(x, size.height - rad * 0.9), rad, r.next() > 0.55 ? deep : light);
      x += rad * (1.1 + r.next() * 0.9);
    }
  }

  @override
  bool shouldRepaint(SkylinePainter old) =>
      old.t != t || old.seed != seed || old.trees != trees || old.opacity != opacity;
}

/// Soft cloud puffs drifting across the sky band.
class CloudsPainter extends CustomPainter {
  final Color color;
  const CloudsPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color.withValues(alpha: 0.75);
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
  bool shouldRepaint(CloudsPainter old) => old.color != color;
}

/// Two layered swells filling the bottom of the box, optionally with
/// distant islands behind them and a foam line on the front swell.
class WavesPainter extends CustomPainter {
  final PersonaTheme t;
  final double opacity;
  final bool islands;
  final bool foam;
  const WavesPainter(this.t, {this.opacity = 1, this.islands = false, this.foam = false});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    if (islands) {
      final land = Paint()..color = t.foliage.withValues(alpha: 0.7 * opacity);
      final far = Paint()..color = t.skylineFar.withValues(alpha: opacity);
      canvas.drawOval(
          Rect.fromLTWH(size.width * 0.02, size.height * 0.18, size.width * 0.34, size.height * 0.4), far);
      canvas.drawOval(
          Rect.fromLTWH(size.width * 0.2, size.height * 0.24, size.width * 0.26, size.height * 0.3), land);
      canvas.drawOval(
          Rect.fromLTWH(size.width * 0.66, size.height * 0.22, size.width * 0.3, size.height * 0.34), far);
    }

    List<Offset> crest(double baseY, double amp, double phase) {
      const steps = 28;
      return [
        for (var i = 0; i <= steps; i++)
          Offset(size.width * i / steps, baseY + math.sin(i / steps * math.pi * 2.2 + phase) * amp),
      ];
    }

    Path fill(List<Offset> line) => Path()
      ..addPolygon([Offset(0, size.height), ...line, Offset(size.width, size.height)], true);

    final back = crest(size.height * 0.35, size.height * 0.12, 0.4);
    final front = crest(size.height * 0.62, size.height * 0.10, 2.1);
    canvas.drawPath(fill(back), Paint()..color = t.water.withValues(alpha: opacity));
    canvas.drawPath(fill(front), Paint()..color = t.waterDeep.withValues(alpha: opacity));
    if (foam) {
      canvas.drawPath(
        Path()..addPolygon(back, false),
        Paint()
          ..color = t.skylineWindow.withValues(alpha: 0.7 * opacity)
          ..strokeWidth = 1.6
          ..style = PaintingStyle.stroke,
      );
    }
  }

  @override
  bool shouldRepaint(WavesPainter old) =>
      old.t != t || old.opacity != opacity || old.islands != islands || old.foam != foam;
}

/// Rolling hills; with [crops], a near field of converging crop rows and a
/// line of trees along the far ridge.
class FieldsPainter extends CustomPainter {
  final PersonaTheme t;
  final bool crops;
  final double opacity;
  const FieldsPainter(this.t, {this.crops = true, this.opacity = 1});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final w = size.width, h = size.height;
    Path hill(double y0, double y1, double bulge) => Path()
      ..moveTo(0, h)
      ..lineTo(0, h * y0)
      ..quadraticBezierTo(w * 0.5, h * bulge, w, h * y1)
      ..lineTo(w, h)
      ..close();

    canvas.drawPath(hill(0.34, 0.18, 0.0), Paint()..color = t.skylineFar.withValues(alpha: opacity));
    if (crops) {
      // Trees along the far ridge.
      final r = _Rng(41);
      for (var i = 0; i < 7; i++) {
        final x = w * (0.3 + i * 0.1 + r.next() * 0.03);
        // On the far hill's curve (a quadratic with its control point at y = 0).
        final f = x / w;
        final ridge = h * ((1 - f) * (1 - f) * 0.34 + f * f * 0.18) + 2;
        final rad = h * (0.06 + r.next() * 0.04);
        canvas.drawRect(Rect.fromLTWH(x - 0.8, ridge - rad * 0.2, 1.6, rad * 1.2),
            Paint()..color = t.foliageDeep.withValues(alpha: opacity));
        canvas.drawCircle(Offset(x, ridge - rad), rad,
            Paint()..color = (i.isEven ? t.foliage : t.foliageDeep).withValues(alpha: opacity));
      }
    }
    final field = hill(0.62, 0.46, 0.38);
    canvas.drawPath(field, Paint()..color = t.skylineNear.withValues(alpha: opacity));
    if (!crops) return;
    canvas.save();
    canvas.clipPath(field);
    final dark = Paint()
      ..color = t.foliageDeep.withValues(alpha: 0.45 * opacity)
      ..strokeWidth = 1.6;
    final light = Paint()
      ..color = t.skylineWindow.withValues(alpha: 0.55 * opacity)
      ..strokeWidth = 1.2;
    const n = 14;
    for (var i = 0; i <= n; i++) {
      final f = i / n;
      final bottom = Offset(w * (f * 1.8 - 0.4), h);
      final top = Offset(w * (0.35 + f * 0.5), h * 0.4);
      canvas.drawLine(bottom, top, i.isEven ? dark : light);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(FieldsPainter old) => old.t != t || old.crops != crops || old.opacity != opacity;
}

/// A low terminal, a far city, the control tower and a runway on a pink
/// horizon glow.
class AirportPainter extends CustomPainter {
  final PersonaTheme t;
  final double opacity;
  const AirportPainter(this.t, {this.opacity = 1});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final w = size.width, h = size.height;
    Paint p(Color c, [double a = 1]) => Paint()..color = c.withValues(alpha: a * opacity);
    final horizon = h * 0.64;

    // Horizon glow and far low-rise city.
    canvas.drawRect(Rect.fromLTWH(0, horizon - h * 0.2, w, h * 0.2),
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [t.foliage.withValues(alpha: 0), t.foliage.withValues(alpha: 0.6 * opacity)],
          ).createShader(Rect.fromLTWH(0, horizon - h * 0.2, w, h * 0.2)));
    final r = _Rng(9);
    var x = 0.0;
    while (x < w) {
      final bw = 8 + r.next() * 16;
      final bh = h * (0.08 + r.next() * 0.22);
      canvas.drawRect(Rect.fromLTWH(x, horizon - bh, bw, bh), p(t.skylineFar));
      x += bw + r.next() * 10;
    }

    // Ground and runway.
    canvas.drawRect(Rect.fromLTWH(0, horizon, w, h - horizon), p(t.water));
    final runway = Rect.fromLTWH(0, h * 0.8, w, h * 0.11);
    canvas.drawRect(runway, p(t.waterDeep));
    final dash = p(t.skylineWindow, 0.9);
    for (var dx = 6.0; dx < w; dx += 18) {
      canvas.drawRect(Rect.fromLTWH(dx, runway.center.dy - 0.8, 9, 1.6), dash);
    }

    // Terminal with a curved roof and a strip of windows.
    final termTop = horizon - h * 0.16;
    final term = RRect.fromRectAndCorners(
      Rect.fromLTRB(w * 0.08, termTop, w * 0.6, horizon + 1),
      topLeft: Radius.circular(h * 0.12),
      topRight: Radius.circular(h * 0.04),
    );
    canvas.drawRRect(term, p(t.skylineNear));
    final lit = p(t.skylineWindow, 0.85);
    for (var wx = w * 0.12; wx < w * 0.57; wx += 6) {
      canvas.drawRect(Rect.fromLTWH(wx, termTop + h * 0.07, 3.2, h * 0.05), lit);
    }

    // Control tower: shaft, flared cab, roof and mast.
    final tx = w * 0.8;
    final shaftW = math.max(4.0, w * 0.025);
    final cabY = horizon - h * 0.52;
    canvas.drawRect(Rect.fromLTRB(tx - shaftW / 2, cabY, tx + shaftW / 2, horizon + 1), p(t.skylineNear));
    final cabW = shaftW * 3.2;
    final cab = Path()
      ..moveTo(tx - cabW / 2, cabY - h * 0.12)
      ..lineTo(tx + cabW / 2, cabY - h * 0.12)
      ..lineTo(tx + cabW * 0.35, cabY)
      ..lineTo(tx - cabW * 0.35, cabY)
      ..close();
    canvas.drawPath(cab, p(t.skylineNear));
    canvas.drawRect(Rect.fromLTRB(tx - cabW * 0.4, cabY - h * 0.1, tx + cabW * 0.4, cabY - h * 0.05), lit);
    canvas.drawRect(Rect.fromLTRB(tx - cabW * 0.45, cabY - h * 0.15, tx + cabW * 0.45, cabY - h * 0.12),
        p(t.skylineNear));
    canvas.drawRect(Rect.fromLTRB(tx - 0.6, cabY - h * 0.26, tx + 0.6, cabY - h * 0.15), p(t.skylineNear));
  }

  @override
  bool shouldRepaint(AirportPainter old) => old.t != t || old.opacity != opacity;
}

/// Skyline over a river crossed by an arched bridge, trees on the bank.
class CivicPainter extends CustomPainter {
  final PersonaTheme t;
  final int seed;
  final double opacity;
  const CivicPainter(this.t, {this.seed = 17, this.opacity = 1});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final w = size.width, h = size.height;
    final bank = h * 0.74;
    SkylinePainter(t, seed: seed, opacity: opacity).paint(canvas, Size(w, bank));

    Paint p(Color c, [double a = 1]) => Paint()..color = c.withValues(alpha: a * opacity);
    canvas.drawRect(Rect.fromLTWH(0, bank, w, h - bank), p(t.water));
    canvas.drawRect(Rect.fromLTWH(0, bank + (h - bank) * 0.55, w, (h - bank) * 0.45), p(t.waterDeep));
    final glint = p(t.skylineWindow, 0.8)..strokeWidth = 1.2;
    final r = _Rng(seed + 7);
    for (var i = 0; i < 6; i++) {
      final gx = w * r.next();
      final gy = bank + (h - bank) * (0.25 + r.next() * 0.6);
      canvas.drawLine(Offset(gx, gy), Offset(gx + 8 + r.next() * 8, gy), glint);
    }

    // Bridge: deck, one arch, hangers.
    final deck = bank - h * 0.04;
    final left = w * 0.52, right = w * 0.96;
    final steel = p(t.primaryContainer, 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6;
    canvas.drawLine(Offset(left, deck), Offset(right, deck), steel..strokeWidth = 2.2);
    final arch = Path()
      ..moveTo(left + (right - left) * 0.1, deck)
      ..quadraticBezierTo((left + right) / 2, deck - h * 0.34, right - (right - left) * 0.1, deck);
    canvas.drawPath(arch, steel..strokeWidth = 1.6);
    for (var i = 1; i < 8; i++) {
      final f = i / 8;
      final hx = left + (right - left) * (0.1 + 0.8 * f);
      final hy = deck - h * 0.34 * 2 * f * (1 - f) * 0.98;
      canvas.drawLine(Offset(hx, deck), Offset(hx, hy), steel..strokeWidth = 0.8);
    }
    for (final px in [left + (right - left) * 0.1, right - (right - left) * 0.1]) {
      canvas.drawRect(Rect.fromLTRB(px - 1.5, deck, px + 1.5, h), p(t.primaryContainer, 0.45));
    }
  }

  @override
  bool shouldRepaint(CivicPainter old) => old.t != t || old.seed != seed || old.opacity != opacity;
}

/// Slanted rain streaks.
class RainPainter extends CustomPainter {
  final Color color;
  const RainPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.2
      ..strokeCap = StrokeCap.round;
    final r = _Rng(3);
    for (var i = 0; i < 22; i++) {
      final x = size.width * r.next();
      final y = size.height * r.next() * 0.8;
      final len = 6 + r.next() * 7;
      canvas.drawLine(Offset(x, y), Offset(x - len * 0.35, y + len), paint);
    }
  }

  @override
  bool shouldRepaint(RainPainter old) => old.color != color;
}

/// A few gulls — little "v" strokes.
class BirdsPainter extends CustomPainter {
  final Color color;
  const BirdsPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    for (final (fx, fy, s) in [(0.15, 0.55, 1.0), (0.45, 0.25, 0.8), (0.75, 0.6, 0.65)]) {
      final c = Offset(size.width * fx, size.height * fy);
      final wing = 6.0 * s;
      canvas.drawPath(
        Path()
          ..moveTo(c.dx - wing, c.dy - wing * 0.5)
          ..quadraticBezierTo(c.dx - wing * 0.4, c.dy - wing * 0.7, c.dx, c.dy)
          ..quadraticBezierTo(c.dx + wing * 0.4, c.dy - wing * 0.7, c.dx + wing, c.dy - wing * 0.5),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(BirdsPainter old) => old.color != color;
}

/// Where a scene is drawn: the page header band, the sheet's foot (a full
/// landscape or its quieter [soft] form), or a persona card's vignette.
enum SceneSlot { header, footer, soft, card }

/// The sun: a warm disc with a soft glow.
class _Sun extends StatelessWidget {
  final double size;
  const _Sun({this.size = 24});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: AppColors.sunCore,
        boxShadow: [BoxShadow(color: AppColors.sun.withValues(alpha: 0.45), blurRadius: size * 0.7, spreadRadius: 2)],
      ),
    );
  }
}

/// A jet climbing to the upper right, trailing a pink contrail.
class _Jet extends StatelessWidget {
  final PersonaTheme t;
  final double size;
  const _Jet(this.t, {this.size = 30});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size * 2.2,
      height: size,
      child: Stack(clipBehavior: Clip.none, children: [
        Positioned(
          left: 0,
          bottom: size * 0.3,
          child: Transform.rotate(
            angle: -0.32,
            alignment: Alignment.centerRight,
            child: Container(
              width: size * 1.35,
              height: 2.2,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(2),
                gradient: LinearGradient(colors: [t.accent2.withValues(alpha: 0), t.accent2.withValues(alpha: 0.7)]),
              ),
            ),
          ),
        ),
        Positioned(
          right: 0,
          top: 0,
          child: Transform.rotate(angle: math.pi / 2.6, child: Icon(Icons.flight, size: size, color: t.primary)),
        ),
      ]),
    );
  }
}

/// The active persona's painted scene for one [slot]. [theme] overrides the
/// active persona (the persona cards each show their own).
class PersonaScenery extends StatelessWidget {
  final SceneSlot slot;
  final PersonaTheme? theme;
  const PersonaScenery(this.slot, {super.key, this.theme});

  @override
  Widget build(BuildContext context) {
    final t = theme ?? PersonaTheme.of(context);
    return switch (slot) {
      SceneSlot.header => _header(t),
      SceneSlot.card => _card(t),
      SceneSlot.footer || SceneSlot.soft => CustomPaint(painter: _footerPainter(t, slot == SceneSlot.soft)),
    };
  }

  static Widget _band(double height, CustomPainter painter) =>
      Positioned(left: 0, right: 0, bottom: 0, height: height, child: CustomPaint(painter: painter));

  Widget _header(PersonaTheme t) {
    final clouds = Positioned.fill(child: CustomPaint(painter: CloudsPainter(t.cloudPuff)));
    return Stack(children: switch (t.scene) {
      PersonaScene.city => [
          clouds,
          const Positioned(right: 26, top: 42, child: _Sun()),
          _band(70, SkylinePainter(t, seed: 11)),
        ],
      PersonaScene.fields => [
          clouds,
          const Positioned(right: 30, top: 40, child: _Sun()),
          _band(66, FieldsPainter(t)),
          Positioned(right: 64, bottom: 8, child: Icon(Icons.agriculture, size: 22, color: t.primaryContainer)),
        ],
      PersonaScene.sea => [
          clouds,
          Positioned(left: 18, top: 44, width: 52, height: 20, child: CustomPaint(painter: BirdsPainter(t.ink.withValues(alpha: 0.45)))),
          _band(58, WavesPainter(t, islands: true, foam: true)),
          Positioned(right: 36, bottom: 16, child: Icon(Icons.sailing, size: 30, color: t.primaryContainer)),
        ],
      PersonaScene.airport => [
          clouds,
          Positioned(right: 16, top: 42, child: _Jet(t, size: 28)),
          _band(62, AirportPainter(t)),
        ],
      PersonaScene.civic => [
          clouds,
          Positioned(right: 0, top: 30, width: 140, height: 50, child: CustomPaint(painter: RainPainter(t.rainGlyph.withValues(alpha: 0.35)))),
          _band(74, CivicPainter(t, seed: 11)),
        ],
    });
  }

  Widget _card(PersonaTheme t) {
    return Stack(children: switch (t.scene) {
      PersonaScene.city => [
          const Positioned(right: 56, top: 26, child: _Sun(size: 22)),
          _band(64, SkylinePainter(t, seed: 5)),
        ],
      PersonaScene.fields => [
          const Positioned(right: 64, top: 22, child: _Sun(size: 20)),
          _band(72, FieldsPainter(t)),
          Positioned(right: 26, bottom: 14, child: Icon(Icons.agriculture, size: 30, color: t.primaryContainer)),
        ],
      PersonaScene.sea => [
          Positioned(left: 30, top: 18, width: 60, height: 22, child: CustomPaint(painter: BirdsPainter(t.ink.withValues(alpha: 0.45)))),
          _band(60, WavesPainter(t, foam: true)),
          Positioned(right: 30, bottom: 20, child: Icon(Icons.directions_boat_filled, size: 38, color: t.primaryContainer)),
        ],
      PersonaScene.airport => [
          _band(60, AirportPainter(t)),
          Positioned(right: 46, top: 30, child: _Jet(t, size: 34)),
        ],
      PersonaScene.civic => [
          Positioned(right: 0, top: 6, width: 120, height: 40, child: CustomPaint(painter: RainPainter(t.rainGlyph.withValues(alpha: 0.35)))),
          _band(80, CivicPainter(t, seed: 17)),
        ],
    });
  }

  static CustomPainter _footerPainter(PersonaTheme t, bool soft) {
    if (soft) {
      return switch (t.scene) {
        PersonaScene.fields => FieldsPainter(t, crops: false, opacity: 0.8),
        _ => WavesPainter(t, opacity: 0.9),
      };
    }
    return switch (t.scene) {
      PersonaScene.city => SkylinePainter(t, seed: 23, opacity: 0.8),
      PersonaScene.fields => FieldsPainter(t, opacity: 0.85),
      PersonaScene.sea => WavesPainter(t, opacity: 0.9, islands: true, foam: true),
      PersonaScene.airport => AirportPainter(t, opacity: 0.8),
      PersonaScene.civic => CivicPainter(t, seed: 23, opacity: 0.8),
    };
  }
}

/// Which scenery strip sits at the foot of a page's sheet: the persona's
/// full landscape, its quieter form (swells / soft hills), or nothing.
enum SceneryFooter { none, landscape, soft }

/// The strip under the top bar: the city pill over the persona's scene.
class SceneryHeader extends StatelessWidget {
  static const double height = 112;
  const SceneryHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: height,
      child: Stack(children: [
        Positioned.fill(child: PersonaScenery(SceneSlot.header)),
        Positioned(top: 4, left: 0, right: 0, child: Center(child: CityPill())),
      ]),
    );
  }
}

/// The white city chip: pin, "City, Region", chevron — opens the picker.
class CityPill extends StatelessWidget {
  const CityPill({super.key});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final city = UiPrefs.of(context).cityInfo;
    final shape = BorderRadius.circular(999);
    return DecoratedBox(
      decoration: BoxDecoration(borderRadius: shape, boxShadow: t.cardShadow),
      child: Material(
        color: t.card,
        borderRadius: shape,
        child: InkWell(
          borderRadius: shape,
          onTap: () => showCityPicker(context),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 9, 12, 9),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.location_on, size: 18, color: t.primary),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 220),
                child: Text(
                  '${city.name}, ${city.region}',
                  overflow: TextOverflow.ellipsis,
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: 10),
              Icon(Icons.keyboard_arrow_down, size: 18, color: t.inkMuted),
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
    this.footer = SceneryFooter.landscape,
    this.controller,
    this.dock,
  });

  static const double _footerHeight = 72;

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
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
                decoration: BoxDecoration(
                  color: t.sheet,
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.sheet)),
                  boxShadow: [
                    BoxShadow(color: t.shadow.withValues(alpha: 0.06), blurRadius: 16, offset: const Offset(0, -2)),
                  ],
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
                          child: PersonaScenery(footer == SceneryFooter.soft ? SceneSlot.soft : SceneSlot.footer),
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
