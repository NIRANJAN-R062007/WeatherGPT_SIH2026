// The onboarding screens' own look (pics/ Languages and Welcome mockups):
// a fixed blue palette in a light and a dark design — not the persona
// palettes, since nobody has picked a persona yet — and the painted
// panorama behind the welcome: skyline, village, a fisherman's boat on the
// sea, the sun on the horizon and a climbing airplane. web/src/components/
// scenery/onboardingScene.ts is a line-for-line port; keep the two in step.
import 'dart:math' as math;

import 'package:flutter/material.dart';

class OnbPalette {
  final bool isDark;
  final Color bgTop;
  final Color bgBottom;
  final Color ink;
  final Color muted;
  final Color accent;
  final Color buttonTop;
  final Color buttonBottom;
  final Color sheet;
  final Color sheetBorder;
  final Color field;
  final Color fieldBorder;
  final Color selectedFill;
  final Color selectedBorder;
  final Color radio;
  final Color guestFill;
  final Color divider;

  // Scene.
  final Color cloud;
  final Color hill;
  final Color hillNear;
  final Color towerFar;
  final Color towerNear;
  final Color window;
  final Color sea;
  final Color seaDeep;
  final Color glint;
  final Color sand;
  final Color land;
  final Color landDeep;
  final Color trunk;
  final Color wall;
  final Color roof;
  final Color houseWindow;
  final Color hull;
  final Color rigging;
  final Color sun;
  final Color sunGlow;
  final Color plane;
  final Color trail;
  final Color bird;

  const OnbPalette({
    required this.isDark,
    required this.bgTop,
    required this.bgBottom,
    required this.ink,
    required this.muted,
    required this.accent,
    required this.buttonTop,
    required this.buttonBottom,
    required this.sheet,
    required this.sheetBorder,
    required this.field,
    required this.fieldBorder,
    required this.selectedFill,
    required this.selectedBorder,
    required this.radio,
    required this.guestFill,
    required this.divider,
    required this.cloud,
    required this.hill,
    required this.hillNear,
    required this.towerFar,
    required this.towerNear,
    required this.window,
    required this.sea,
    required this.seaDeep,
    required this.glint,
    required this.sand,
    required this.land,
    required this.landDeep,
    required this.trunk,
    required this.wall,
    required this.roof,
    required this.houseWindow,
    required this.hull,
    required this.rigging,
    required this.sun,
    required this.sunGlow,
    required this.plane,
    required this.trail,
    required this.bird,
  });

  /// The palette for the app's current light / dark mode.
  static OnbPalette of(BuildContext context) => Theme.of(context).brightness == Brightness.dark ? onbDark : onbLight;

  LinearGradient get background =>
      LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [bgTop, bgBottom]);

  LinearGradient get button =>
      LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [buttonTop, buttonBottom]);
}

const onbLight = OnbPalette(
  isDark: false,
  bgTop: Color(0xFFDDEFFC),
  bgBottom: Color(0xFFF3F9FE),
  ink: Color(0xFF0C2148),
  muted: Color(0xFF5D6B82),
  accent: Color(0xFF1273EA),
  buttonTop: Color(0xFF1E86F7),
  buttonBottom: Color(0xFF0B67E6),
  sheet: Color(0xFFF6FAFE),
  sheetBorder: Color(0xFFFFFFFF),
  field: Color(0xFFFAFCFF),
  fieldBorder: Color(0xFFD2E1F2),
  selectedFill: Color(0xFFE3F0FC),
  selectedBorder: Color(0xFF8DC2F0),
  radio: Color(0xFF9AA6B8),
  guestFill: Color(0xFFE6F1FD),
  divider: Color(0xFFD6E0EC),
  cloud: Color(0xFFFFFFFF),
  hill: Color(0xFFC3E1F5),
  hillNear: Color(0xFFA7D3F0),
  towerFar: Color(0xFFA3CFF2),
  towerNear: Color(0xFF5DA6E9),
  window: Color(0xFFE2F1FF),
  sea: Color(0xFF52B6F0),
  seaDeep: Color(0xFF1F86DD),
  glint: Color(0xFFFFFFFF),
  sand: Color(0xFFF2E2B4),
  land: Color(0xFF6DBE4B),
  landDeep: Color(0xFF3B9A3C),
  trunk: Color(0xFF7A5A3A),
  wall: Color(0xFFF7EBD2),
  roof: Color(0xFFE2603A),
  houseWindow: Color(0xFF4F8FD6),
  hull: Color(0xFF1C3762),
  rigging: Color(0xFF1C3762),
  sun: Color(0xFFFFC83A),
  sunGlow: Color(0xFFFFE08A),
  plane: Color(0xFF2D8BEA),
  trail: Color(0xFFFFFFFF),
  bird: Color(0xFF3F86CF),
);

const onbDark = OnbPalette(
  isDark: true,
  bgTop: Color(0xFF0A1C40),
  bgBottom: Color(0xFF071533),
  ink: Color(0xFFFFFFFF),
  muted: Color(0xFFB3C3DE),
  accent: Color(0xFF3B9BFF),
  buttonTop: Color(0xFF1C8EFF),
  buttonBottom: Color(0xFF0A6CF0),
  sheet: Color(0xFF0B1E45),
  sheetBorder: Color(0xFF1B3667),
  field: Color(0xFF0D2350),
  fieldBorder: Color(0xFF2A4A80),
  selectedFill: Color(0xFF0F2D63),
  selectedBorder: Color(0xFF2B86F5),
  radio: Color(0xFF8EA5CE),
  guestFill: Color(0xFF12305F),
  divider: Color(0xFF2A426E),
  cloud: Color(0xFF16336C),
  hill: Color(0xFF15346C),
  hillNear: Color(0xFF112B5B),
  towerFar: Color(0xFF1A3C78),
  towerNear: Color(0xFF214C94),
  window: Color(0xFFFFD267),
  sea: Color(0xFF1B4E98),
  seaDeep: Color(0xFF0D2A5C),
  glint: Color(0xFFFFC85A),
  sand: Color(0xFF2C4A5E),
  land: Color(0xFF1F5B3C),
  landDeep: Color(0xFF143F2B),
  trunk: Color(0xFF2B2A2A),
  wall: Color(0xFF4E5F86),
  roof: Color(0xFF8E4A36),
  houseWindow: Color(0xFFFFD267),
  hull: Color(0xFF07142E),
  rigging: Color(0xFF07142E),
  sun: Color(0xFFF7BE3B),
  sunGlow: Color(0xFFF39A2B),
  plane: Color(0xFF55A8FF),
  trail: Color(0xFF6FB6FF),
  bird: Color(0xFF6E9BDD),
);

/// Deterministic pseudo-random stream, so the art is the same every frame.
class _Rng {
  int _s;
  _Rng(this._s);
  double next() {
    _s = (_s * 1103515245 + 12345) & 0x7fffffff;
    return _s / 0x7fffffff;
  }
}

void _cloud(Canvas canvas, Offset c, double s, Color color) {
  final paint = Paint()..color = color;
  canvas.drawRRect(
    RRect.fromRectAndRadius(Rect.fromCenter(center: c, width: 92 * s, height: 26 * s), Radius.circular(13 * s)),
    paint,
  );
  canvas.drawCircle(c + Offset(-16 * s, -12 * s), 17 * s, paint);
  canvas.drawCircle(c + Offset(10 * s, -18 * s), 22 * s, paint);
  canvas.drawCircle(c + Offset(32 * s, -6 * s), 13 * s, paint);
}

void _birds(Canvas canvas, Offset at, double s, Color color) {
  final paint = Paint()
    ..color = color
    ..style = PaintingStyle.stroke
    ..strokeWidth = 1.5
    ..strokeCap = StrokeCap.round;
  for (final (dx, dy, k) in [(0.0, 0.0, 1.0), (16.0, 6.0, 0.75)]) {
    final o = at + Offset(dx * s, dy * s);
    final w = 7 * s * k;
    canvas.drawPath(
      Path()
        ..moveTo(o.dx - w, o.dy - w * 0.35)
        ..quadraticBezierTo(o.dx - w * 0.4, o.dy - w * 0.45, o.dx, o.dy + w * 0.12)
        ..quadraticBezierTo(o.dx + w * 0.4, o.dy - w * 0.45, o.dx + w, o.dy - w * 0.35),
      paint,
    );
  }
}

/// A half-set sun on the line [horizonY] with its glow.
void _sun(Canvas canvas, Offset c, double r, double horizonY, OnbPalette p) {
  canvas.save();
  canvas.clipRect(Rect.fromLTRB(c.dx - r * 3, c.dy - r * 3, c.dx + r * 3, horizonY));
  canvas.drawCircle(
    c,
    r * 1.9,
    Paint()
      ..shader = RadialGradient(
        colors: [
          p.sunGlow.withValues(alpha: p.isDark ? 0.45 : 0.55),
          p.sunGlow.withValues(alpha: 0),
        ],
      ).createShader(Rect.fromCircle(center: c, radius: r * 1.9)),
  );
  canvas.drawCircle(c, r, Paint()..color = p.sun);
  canvas.restore();
}

/// Short glints on the water under the sun.
void _glints(Canvas canvas, Offset c, double r, OnbPalette p) {
  final paint = Paint()
    ..color = p.glint.withValues(alpha: p.isDark ? 0.75 : 0.8)
    ..strokeWidth = 1.6
    ..strokeCap = StrokeCap.round;
  for (var i = 0; i < 4; i++) {
    final y = c.dy + 4 + i * 4.5;
    final half = r * (0.9 - i * 0.18);
    canvas.drawLine(Offset(c.dx - half, y), Offset(c.dx + half, y), paint);
  }
}

void _palm(Canvas canvas, Offset base, double h, OnbPalette p, {bool mirror = false}) {
  final dir = mirror ? -1.0 : 1.0;
  final top = base + Offset(dir * h * 0.18, -h);
  canvas.drawPath(
    Path()
      ..moveTo(base.dx, base.dy)
      ..quadraticBezierTo(base.dx + dir * h * 0.02, base.dy - h * 0.6, top.dx, top.dy),
    Paint()
      ..color = p.trunk
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(1.6, h * 0.07)
      ..strokeCap = StrokeCap.round,
  );
  final leaf = Paint()..color = p.landDeep;
  for (final a in [-2.7, -2.1, -1.2, -0.45, 0.1]) {
    final tip = top + Offset(math.cos(a) * h * 0.5, math.sin(a) * h * 0.32 + h * 0.12);
    final mid = top + Offset(math.cos(a) * h * 0.25, math.sin(a) * h * 0.3 - h * 0.04);
    canvas.drawPath(
      Path()
        ..moveTo(top.dx, top.dy)
        ..quadraticBezierTo(mid.dx, mid.dy - h * 0.06, tip.dx, tip.dy)
        ..quadraticBezierTo(mid.dx, mid.dy + h * 0.04, top.dx, top.dy),
      leaf,
    );
  }
}

/// The airplane's silhouette, nose pointing along +x, [len] long.
void _plane(Canvas canvas, Offset at, double len, double angle, Color color) {
  canvas.save();
  canvas.translate(at.dx, at.dy);
  canvas.rotate(angle);
  final l = len;
  final paint = Paint()..color = color;
  // Fuselage.
  canvas.drawRRect(
    RRect.fromRectAndRadius(Rect.fromLTWH(-l * 0.5, -l * 0.055, l, l * 0.11), Radius.circular(l * 0.055)),
    paint,
  );
  // Wings, swept back.
  canvas.drawPath(
    Path()
      ..moveTo(l * 0.1, 0)
      ..lineTo(-l * 0.16, -l * 0.42)
      ..lineTo(-l * 0.27, -l * 0.42)
      ..lineTo(-l * 0.12, 0)
      ..lineTo(-l * 0.27, l * 0.42)
      ..lineTo(-l * 0.16, l * 0.42)
      ..close(),
    paint,
  );
  // Tail.
  canvas.drawPath(
    Path()
      ..moveTo(-l * 0.36, 0)
      ..lineTo(-l * 0.5, -l * 0.17)
      ..lineTo(-l * 0.56, -l * 0.17)
      ..lineTo(-l * 0.48, 0)
      ..lineTo(-l * 0.56, l * 0.17)
      ..lineTo(-l * 0.5, l * 0.17)
      ..close(),
    paint,
  );
  canvas.restore();
}

/// The welcome panorama. Clouds flank the title in the upper part; the
/// scene fills the band below [OnboardingScenePainter.sceneTop].
class OnboardingScenePainter extends CustomPainter {
  final OnbPalette p;
  const OnboardingScenePainter(this.p);

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final w = size.width, h = size.height;
    final hz = h * 0.8; // horizon / waterline

    _cloud(canvas, Offset(w * 0.02, h * 0.42), 0.8, p.cloud.withValues(alpha: p.isDark ? 0.95 : 0.9));
    _cloud(canvas, Offset(w * 0.97, h * 0.38), 0.95, p.cloud.withValues(alpha: p.isDark ? 0.95 : 0.9));

    // Far hills behind the sea, and the sun setting between them.
    canvas.drawPath(
      Path()
        ..moveTo(w * 0.5, hz)
        ..quadraticBezierTo(w * 0.62, hz - h * 0.06, w * 0.74, hz - h * 0.025)
        ..quadraticBezierTo(w * 0.9, hz - h * 0.08, w, hz - h * 0.04)
        ..lineTo(w, hz)
        ..close(),
      Paint()..color = p.hill,
    );
    final sunC = Offset(w * 0.8, hz);
    final sunR = math.min(24.0, h * 0.07);
    _sun(canvas, sunC, sunR, hz, p);

    // Skyline over the left two-thirds.
    _towers(canvas, w * 0.7, hz, h * 0.07, h * 0.16, _Rng(17), p.towerFar, windows: false);
    _towers(canvas, w * 0.6, hz, h * 0.05, h * 0.11, _Rng(5), p.towerNear, windows: true);

    // Sea.
    canvas.drawRect(
      Rect.fromLTRB(0, hz, w, h),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [p.sea, p.seaDeep],
        ).createShader(Rect.fromLTRB(0, hz, w, h)),
    );
    _glints(canvas, sunC, sunR, p);

    // The bank on the left: a sand edge, then grass.
    final shore = Path()
      ..moveTo(0, hz - h * 0.05)
      ..quadraticBezierTo(w * 0.22, hz - h * 0.07, w * 0.42, hz + h * 0.01)
      ..quadraticBezierTo(w * 0.5, hz + h * 0.05, w * 0.36, hz + h * 0.1)
      ..quadraticBezierTo(w * 0.25, h, w * 0.1, h + 2)
      ..lineTo(0, h + 2)
      ..close();
    canvas.drawPath(shore, Paint()..color = p.sand);
    canvas.save();
    canvas.translate(-w * 0.02, -h * 0.008);
    canvas.drawPath(shore, Paint()..color = p.land);
    canvas.restore();

    // Trees along the bank: a hedge of round crowns and two palms.
    final r = _Rng(41);
    var x = -6.0;
    while (x < w * 0.34) {
      final y = hz - h * 0.05 * (1 - x / (w * 0.42)) - h * 0.01;
      final rad = 4 + r.next() * 5;
      canvas.drawCircle(Offset(x, y - rad * 0.3), rad, Paint()..color = r.next() > 0.5 ? p.landDeep : p.land);
      x += rad * (1.3 + r.next());
    }
    _palm(canvas, Offset(w * 0.05, hz - h * 0.05), h * 0.11, p);
    _palm(canvas, Offset(w * 0.36, hz - h * 0.012), h * 0.08, p, mirror: true);

    // The village house.
    _house(canvas, Offset(w * 0.2, hz - h * 0.03), math.min(32.0, w * 0.08));

    // A fisherman's boat on the water.
    _boat(canvas, Offset(w * 0.62, hz + h * 0.075), math.min(48.0, w * 0.12));

    // The airplane climbing up and to the right, trailing a contrail.
    final planeAt = Offset(w * 0.87, h * 0.69);
    const climb = -0.38;
    canvas.drawLine(
      Offset(w * 0.52, h * 0.77),
      planeAt - Offset(math.cos(climb) * 10, math.sin(climb) * 10),
      Paint()
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..shader = LinearGradient(
          colors: [
            p.trail.withValues(alpha: 0),
            p.trail.withValues(alpha: p.isDark ? 0.7 : 0.95),
          ],
        ).createShader(Rect.fromPoints(Offset(w * 0.52, h * 0.77), planeAt)),
    );
    _plane(canvas, planeAt, math.min(34.0, w * 0.085), climb, p.plane);

    _birds(canvas, Offset(w * 0.1, h * 0.62), 1, p.bird);
    _birds(canvas, Offset(w * 0.68, h * 0.73), 0.8, p.bird);
  }

  void _towers(
    Canvas canvas,
    double right,
    double base,
    double minH,
    double maxH,
    _Rng r,
    Color color, {
    required bool windows,
  }) {
    final paint = Paint()..color = color;
    final lit = Paint()..color = p.window.withValues(alpha: p.isDark ? 0.9 : 0.85);
    var x = -r.next() * 10;
    while (x < right) {
      final tw = 14 + r.next() * 18;
      final th = minH + r.next() * (maxH - minH);
      final top = base - th;
      canvas.drawRect(Rect.fromLTWH(x, top, tw, th), paint);
      if (r.next() > 0.7) canvas.drawRect(Rect.fromLTWH(x + tw / 2 - 0.8, top - th * 0.14, 1.6, th * 0.14), paint);
      if (windows) {
        for (var wy = top + 5; wy < base - 8; wy += 6.5) {
          for (var wx = x + 3; wx < x + tw - 4; wx += 5) {
            if (!p.isDark || r.next() > 0.35) canvas.drawRect(Rect.fromLTWH(wx, wy, 2.2, 3), lit);
          }
        }
      }
      x += tw + r.next() * 5 - 1;
    }
  }

  void _house(Canvas canvas, Offset base, double s) {
    final wallRect = Rect.fromLTWH(base.dx - s * 0.5, base.dy - s * 0.42, s, s * 0.42);
    canvas.drawRect(wallRect, Paint()..color = p.wall);
    canvas.drawPath(
      Path()
        ..moveTo(base.dx - s * 0.6, base.dy - s * 0.4)
        ..lineTo(base.dx - s * 0.36, base.dy - s * 0.72)
        ..lineTo(base.dx + s * 0.36, base.dy - s * 0.72)
        ..lineTo(base.dx + s * 0.6, base.dy - s * 0.4)
        ..close(),
      Paint()..color = p.roof,
    );
    final glass = Paint()..color = p.houseWindow;
    canvas.drawRect(Rect.fromLTWH(base.dx - s * 0.36, base.dy - s * 0.32, s * 0.16, s * 0.13), glass);
    canvas.drawRect(Rect.fromLTWH(base.dx + s * 0.2, base.dy - s * 0.32, s * 0.16, s * 0.13), glass);
    canvas.drawRect(Rect.fromLTWH(base.dx - s * 0.07, base.dy - s * 0.27, s * 0.14, s * 0.27), Paint()..color = p.roof);
  }

  /// A small fishing boat: hull, mast and sail, and the fisherman with a rod.
  void _boat(Canvas canvas, Offset c, double s) {
    final line = Paint()
      ..color = p.rigging
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..strokeCap = StrokeCap.round;
    // Mast and a small sail.
    canvas.drawLine(c + Offset(s * 0.12, -s * 0.1), c + Offset(s * 0.12, -s * 0.78), line);
    canvas.drawPath(
      Path()
        ..moveTo(c.dx + s * 0.15, c.dy - s * 0.74)
        ..lineTo(c.dx + s * 0.44, c.dy - s * 0.2)
        ..lineTo(c.dx + s * 0.15, c.dy - s * 0.2)
        ..close(),
      Paint()..color = p.isDark ? p.towerNear : Colors.white,
    );
    // The fisherman: head, body, and a rod with its line.
    final fisher = Paint()..color = p.hull;
    canvas.drawCircle(c + Offset(-s * 0.16, -s * 0.5), s * 0.065, fisher);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(c.dx - s * 0.23, c.dy - s * 0.43, s * 0.14, s * 0.3),
        Radius.circular(s * 0.04),
      ),
      fisher,
    );
    canvas.drawLine(c + Offset(-s * 0.12, -s * 0.36), c + Offset(-s * 0.62, -s * 0.78), line);
    canvas.drawLine(
      c + Offset(-s * 0.62, -s * 0.78),
      c + Offset(-s * 0.7, s * 0.05),
      Paint()
        ..color = p.rigging.withValues(alpha: 0.6)
        ..strokeWidth = 0.8,
    );
    // Hull.
    canvas.drawPath(
      Path()
        ..moveTo(c.dx - s * 0.5, c.dy - s * 0.14)
        ..lineTo(c.dx + s * 0.55, c.dy - s * 0.18)
        ..lineTo(c.dx + s * 0.36, c.dy + s * 0.08)
        ..lineTo(c.dx - s * 0.38, c.dy + s * 0.08)
        ..close(),
      Paint()..color = p.hull,
    );
    // Ripple under the hull.
    canvas.drawLine(
      c + Offset(-s * 0.48, s * 0.15),
      c + Offset(s * 0.46, s * 0.15),
      Paint()
        ..color = p.glint.withValues(alpha: 0.5)
        ..strokeWidth = 1.2
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(OnboardingScenePainter old) => old.p != p;
}

/// The Languages page: clouds in the upper corners.
class OnboardingCloudsPainter extends CustomPainter {
  final OnbPalette p;
  const OnboardingCloudsPainter(this.p);

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final c = p.cloud.withValues(alpha: p.isDark ? 0.9 : 0.85);
    _cloud(canvas, Offset(w * 0.06, h * 0.42), 0.85, c);
    _cloud(canvas, Offset(w * 0.96, h * 0.3), 0.9, c);
    _cloud(canvas, Offset(w * 1.0, h * 0.88), 0.75, c);
  }

  @override
  bool shouldRepaint(OnboardingCloudsPainter old) => old.p != p;
}

/// The Languages page's foot: soft hills, the sea, the sun on the horizon
/// and two birds (palms on the dark design).
class OnboardingFooterPainter extends CustomPainter {
  final OnbPalette p;
  const OnboardingFooterPainter(this.p);

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final w = size.width, h = size.height;
    final hz = h * 0.66;
    canvas.drawPath(
      Path()
        ..moveTo(0, hz - h * 0.18)
        ..quadraticBezierTo(w * 0.14, hz - h * 0.36, w * 0.3, hz - h * 0.16)
        ..quadraticBezierTo(w * 0.46, hz - h * 0.3, w * 0.62, hz - h * 0.12)
        ..quadraticBezierTo(w * 0.8, hz - h * 0.3, w, hz - h * 0.2)
        ..lineTo(w, hz)
        ..lineTo(0, hz)
        ..close(),
      Paint()..color = p.hill.withValues(alpha: p.isDark ? 1 : 0.85),
    );
    final sunC = Offset(w * 0.8, hz);
    final sunR = math.min(34.0, h * 0.26);
    _sun(canvas, sunC, sunR, hz, p);
    canvas.drawPath(
      Path()
        ..moveTo(0, hz - h * 0.06)
        ..quadraticBezierTo(w * 0.22, hz - h * 0.2, w * 0.45, hz - h * 0.04)
        ..lineTo(w * 0.45, hz)
        ..lineTo(0, hz)
        ..close(),
      Paint()..color = p.hillNear,
    );
    canvas.drawRect(
      Rect.fromLTRB(0, hz, w, h),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            p.sea.withValues(alpha: p.isDark ? 0.9 : 0.55),
            p.seaDeep.withValues(alpha: p.isDark ? 0.9 : 0.4),
          ],
        ).createShader(Rect.fromLTRB(0, hz, w, h)),
    );
    _glints(canvas, sunC, sunR, p);
    if (p.isDark) {
      _palm(canvas, Offset(w * 0.06, hz - h * 0.04), h * 0.3, p);
      _palm(canvas, Offset(w * 0.95, hz - h * 0.08), h * 0.34, p, mirror: true);
    }
    _birds(canvas, Offset(w * 0.6, h * 0.18), 1, p.bird);
    _birds(canvas, Offset(w * 0.86, h * 0.08), 0.8, p.bird);
  }

  @override
  bool shouldRepaint(OnboardingFooterPainter old) => old.p != p;
}
