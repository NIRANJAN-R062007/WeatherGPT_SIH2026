// The illustrated page chrome (pics/ mockups), painted per persona on a
// <canvas> — no image assets. A line-for-line port of mobile/lib/components/
// scenery.dart's CustomPainters, so both apps draw the same scenes:
//   city    → dense skyline with trees                (General Citizen)
//   fields  → hills, crop rows, leaves, farmhouse      (Farmer)
//   sea     → islands, swells, a trawler, gulls and
//             a lighthouse                             (Fisherman)
//   airport → terminal, control tower, runway          (Aviation)
//   civic   → skyline with the city hall, river        (City Official)
// Dark palettes paint the same scenes at night: lit windows, a moon.
import { alpha, FARM_ROOF, FARM_WALL, LAMP_GLOW, mix, type PersonaTheme } from '../../theme/personaTheme';

export type Painter = (ctx: CanvasRenderingContext2D, w: number, h: number) => void;

/** Deterministic pseudo-random stream (the same LCG as mobile), so the
 *  artwork is the same on every frame and every visit. Math.imul keeps the
 *  low 32 bits exact, which is all the 31-bit mask needs. */
class Rng {
  private s: number;
  constructor(seed: number) {
    this.s = seed;
  }
  next() {
    this.s = (Math.imul(this.s, 1103515245) + 12345) & 0x7fffffff;
    return this.s / 0x7fffffff;
  }
}

const isDark = (t: PersonaTheme) => t.brightness === 'dark';

function rect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  fill: string | CanvasGradient,
) {
  ctx.fillStyle = fill;
  ctx.fillRect(x, y, w, h);
}

function ltrb(ctx: CanvasRenderingContext2D, l: number, t: number, r: number, b: number, fill: string) {
  rect(ctx, l, t, r - l, b - t, fill);
}

function circle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, fill: string) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

function oval(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, fill: string) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
  ctx.fill();
}

function line(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stroke: string,
  width: number,
  cap: CanvasLineCap = 'butt',
) {
  ctx.strokeStyle = stroke;
  ctx.lineWidth = width;
  ctx.lineCap = cap;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function polygon(ctx: CanvasRenderingContext2D, pts: [number, number][]) {
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.closePath();
}

// ---------------------------------------------------------------------------

/** Two layers of towers (a pale far one, a stronger near one with lit
 *  windows) and a hedge of rounded trees along the base. */
export function skyline(t: PersonaTheme, { seed = 7, trees = true, opacity = 1 } = {}): Painter {
  return (ctx, w, h) => {
    if (w <= 0 || h <= 0) return;
    const treeBand = trees ? Math.min(16, h * 0.22) : 0;
    const base = h - treeBand * 0.55;
    const towers = (r: Rng, color: string, minH: number, maxH: number, windows: boolean) => {
      const fill = alpha(color, opacity);
      const lit = alpha(t.skylineWindow, 0.75 * opacity);
      let x = -r.next() * 12;
      while (x < w) {
        const tw = 11 + r.next() * 20;
        const th = base * (minH + r.next() * (maxH - minH));
        const top = base - th;
        rect(ctx, x, top, tw, th, fill);
        const roll = r.next();
        if (roll > 0.82) {
          rect(ctx, x + tw / 2 - 0.75, top - th * 0.18, 1.5, th * 0.18, fill); // antenna
        } else if (roll > 0.64) {
          rect(ctx, x + tw * 0.2, top - 5, tw * 0.6, 5, fill); // stepped crown
        }
        if (windows && tw > 15 && th > 22) {
          for (let wy = top + 5; wy < base - 6; wy += 6) {
            for (let wx = x + 3; wx < x + tw - 4; wx += 5) rect(ctx, wx, wy, 2.2, 2.6, lit);
          }
        }
        x += tw + r.next() * 7 - 1;
      }
    };
    towers(new Rng(seed), t.skylineFar, 0.35, 0.9, false);
    towers(new Rng(seed * 31 + 3), t.skylineNear, 0.2, 0.62, true);
    if (trees) {
      const r = new Rng(seed + 101);
      const lightC = alpha(t.foliage, opacity);
      const deepC = alpha(t.foliageDeep, opacity);
      rect(ctx, 0, h - treeBand * 0.45, w, treeBand * 0.45, lightC);
      let x = -4;
      while (x < w + 8) {
        const rad = treeBand * (0.35 + r.next() * 0.35);
        circle(ctx, x, h - rad * 0.9, rad, r.next() > 0.55 ? deepC : lightC);
        x += rad * (1.1 + r.next() * 0.9);
      }
    }
  };
}

/** Soft cloud puffs drifting across the sky band. */
export function clouds(color: string): Painter {
  return (ctx, w, h) => {
    const fill = alpha(color, 0.75);
    const puff = (cx: number, cy: number, s: number) => {
      oval(ctx, cx - 23 * s, cy - 8 * s, 46 * s, 16 * s, fill);
      circle(ctx, cx - 8 * s, cy - 5 * s, 9 * s, fill);
      circle(ctx, cx + 6 * s, cy - 7 * s, 11 * s, fill);
    };
    puff(w * 0.12, h * 0.3, 1.0);
    puff(w * 0.62, h * 0.18, 0.8);
    puff(w * 0.92, h * 0.42, 1.1);
  };
}

/** Two layered swells filling the bottom of the box, optionally with
 *  distant islands behind them and a foam line on the front swell. */
export function waves(t: PersonaTheme, { opacity = 1, islands = false, foam = false } = {}): Painter {
  return (ctx, w, h) => {
    if (w <= 0 || h <= 0) return;
    if (islands) {
      const land = alpha(t.foliage, 0.7 * opacity);
      const far = alpha(t.skylineFar, opacity);
      oval(ctx, w * 0.02, h * 0.18, w * 0.34, h * 0.4, far);
      oval(ctx, w * 0.2, h * 0.24, w * 0.26, h * 0.3, land);
      oval(ctx, w * 0.66, h * 0.22, w * 0.3, h * 0.34, far);
    }
    const crest = (baseY: number, amp: number, phase: number) => {
      const steps = 28;
      const pts: [number, number][] = [];
      for (let i = 0; i <= steps; i++) {
        pts.push([(w * i) / steps, baseY + Math.sin((i / steps) * Math.PI * 2.2 + phase) * amp]);
      }
      return pts;
    };
    const fill = (pts: [number, number][], color: string) => {
      polygon(ctx, [[0, h], ...pts, [w, h]]);
      ctx.fillStyle = color;
      ctx.fill();
    };
    const back = crest(h * 0.35, h * 0.12, 0.4);
    const front = crest(h * 0.62, h * 0.1, 2.1);
    fill(back, alpha(t.water, opacity));
    fill(front, alpha(t.waterDeep, opacity));
    if (foam) {
      ctx.beginPath();
      back.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      ctx.strokeStyle = alpha(t.skylineWindow, 0.7 * opacity);
      ctx.lineWidth = 1.6;
      ctx.stroke();
    }
  };
}

/** Rolling hills; with crops, a near field of converging crop rows and a
 *  line of trees along the far ridge. */
export function fields(t: PersonaTheme, { crops = true, opacity = 1 } = {}): Painter {
  return (ctx, w, h) => {
    if (w <= 0 || h <= 0) return;
    const hill = (y0: number, y1: number, bulge: number) => {
      ctx.beginPath();
      ctx.moveTo(0, h);
      ctx.lineTo(0, h * y0);
      ctx.quadraticCurveTo(w * 0.5, h * bulge, w, h * y1);
      ctx.lineTo(w, h);
      ctx.closePath();
    };
    hill(0.34, 0.18, 0);
    ctx.fillStyle = alpha(t.skylineFar, opacity);
    ctx.fill();
    if (crops) {
      // Trees along the far ridge.
      const r = new Rng(41);
      for (let i = 0; i < 7; i++) {
        const x = w * (0.3 + i * 0.1 + r.next() * 0.03);
        // On the far hill's curve (a quadratic with its control point at y = 0).
        const f = x / w;
        const ridge = h * ((1 - f) * (1 - f) * 0.34 + f * f * 0.18) + 2;
        const rad = h * (0.06 + r.next() * 0.04);
        rect(ctx, x - 0.8, ridge - rad * 0.2, 1.6, rad * 1.2, alpha(t.foliageDeep, opacity));
        circle(ctx, x, ridge - rad, rad, alpha(i % 2 === 0 ? t.foliage : t.foliageDeep, opacity));
      }
    }
    hill(0.62, 0.46, 0.38);
    ctx.fillStyle = alpha(t.skylineNear, opacity);
    ctx.fill();
    if (!crops) return;
    ctx.save();
    hill(0.62, 0.46, 0.38);
    ctx.clip();
    const n = 14;
    for (let i = 0; i <= n; i++) {
      const f = i / n;
      const even = i % 2 === 0;
      line(
        ctx,
        w * (f * 1.8 - 0.4),
        h,
        w * (0.35 + f * 0.5),
        h * 0.4,
        even ? alpha(t.foliageDeep, 0.45 * opacity) : alpha(t.skylineWindow, 0.55 * opacity),
        even ? 1.6 : 1.2,
      );
    }
    ctx.restore();
  };
}

/** A low terminal, a far city, the control tower and a runway on a pink
 *  horizon glow. */
export function airport(t: PersonaTheme, { opacity = 1 } = {}): Painter {
  return (ctx, w, h) => {
    if (w <= 0 || h <= 0) return;
    const p = (c: string, a = 1) => alpha(c, a * opacity);
    const horizon = h * 0.64;

    // Horizon glow and far low-rise city.
    const glow = ctx.createLinearGradient(0, horizon - h * 0.2, 0, horizon);
    glow.addColorStop(0, alpha(t.foliage, 0));
    glow.addColorStop(1, alpha(t.foliage, 0.6 * opacity));
    rect(ctx, 0, horizon - h * 0.2, w, h * 0.2, glow);
    const r = new Rng(9);
    let x = 0;
    while (x < w) {
      const bw = 8 + r.next() * 16;
      const bh = h * (0.08 + r.next() * 0.22);
      rect(ctx, x, horizon - bh, bw, bh, p(t.skylineFar));
      x += bw + r.next() * 10;
    }

    // Ground and runway.
    rect(ctx, 0, horizon, w, h - horizon, p(t.water));
    const ry = h * 0.8;
    const rh = h * 0.11;
    rect(ctx, 0, ry, w, rh, p(t.waterDeep));
    for (let dx = 6; dx < w; dx += 18) rect(ctx, dx, ry + rh / 2 - 0.8, 9, 1.6, p(t.skylineWindow, 0.9));

    // Terminal with a curved roof and a strip of windows.
    const termTop = horizon - h * 0.16;
    ctx.fillStyle = p(t.skylineNear);
    ctx.beginPath();
    ctx.roundRect(w * 0.08, termTop, w * 0.52, horizon + 1 - termTop, [h * 0.12, h * 0.04, 0, 0]);
    ctx.fill();
    const lit = p(t.skylineWindow, 0.85);
    for (let wx = w * 0.12; wx < w * 0.57; wx += 6) rect(ctx, wx, termTop + h * 0.07, 3.2, h * 0.05, lit);

    // Control tower: shaft, flared cab, roof and mast.
    const tx = w * 0.8;
    const shaftW = Math.max(4, w * 0.025);
    const cabY = horizon - h * 0.52;
    ltrb(ctx, tx - shaftW / 2, cabY, tx + shaftW / 2, horizon + 1, p(t.skylineNear));
    const cabW = shaftW * 3.2;
    polygon(ctx, [
      [tx - cabW / 2, cabY - h * 0.12],
      [tx + cabW / 2, cabY - h * 0.12],
      [tx + cabW * 0.35, cabY],
      [tx - cabW * 0.35, cabY],
    ]);
    ctx.fillStyle = p(t.skylineNear);
    ctx.fill();
    ltrb(ctx, tx - cabW * 0.4, cabY - h * 0.1, tx + cabW * 0.4, cabY - h * 0.05, lit);
    ltrb(ctx, tx - cabW * 0.45, cabY - h * 0.15, tx + cabW * 0.45, cabY - h * 0.12, p(t.skylineNear));
    ltrb(ctx, tx - 0.6, cabY - h * 0.26, tx + 0.6, cabY - h * 0.15, p(t.skylineNear));
  };
}

/** Skyline over a river crossed by an arched bridge, trees on the bank. */
export function civic(t: PersonaTheme, { seed = 17, opacity = 1 } = {}): Painter {
  return (ctx, w, h) => {
    if (w <= 0 || h <= 0) return;
    const bank = h * 0.74;
    skyline(t, { seed, opacity })(ctx, w, bank);

    const p = (c: string, a = 1) => alpha(c, a * opacity);
    rect(ctx, 0, bank, w, h - bank, p(t.water));
    rect(ctx, 0, bank + (h - bank) * 0.55, w, (h - bank) * 0.45, p(t.waterDeep));
    const r = new Rng(seed + 7);
    for (let i = 0; i < 6; i++) {
      const gx = w * r.next();
      const gy = bank + (h - bank) * (0.25 + r.next() * 0.6);
      line(ctx, gx, gy, gx + 8 + r.next() * 8, gy, p(t.skylineWindow, 0.8), 1.2);
    }

    // Bridge: deck, one arch, hangers.
    const deck = bank - h * 0.04;
    const left = w * 0.52;
    const right = w * 0.96;
    const steel = p(t.primaryContainer, 0.55);
    line(ctx, left, deck, right, deck, steel, 2.2);
    ctx.beginPath();
    ctx.moveTo(left + (right - left) * 0.1, deck);
    ctx.quadraticCurveTo((left + right) / 2, deck - h * 0.34, right - (right - left) * 0.1, deck);
    ctx.strokeStyle = steel;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    for (let i = 1; i < 8; i++) {
      const f = i / 8;
      const hx = left + (right - left) * (0.1 + 0.8 * f);
      const hy = deck - h * 0.34 * 2 * f * (1 - f) * 0.98;
      line(ctx, hx, deck, hx, hy, steel, 0.8);
    }
    for (const px of [left + (right - left) * 0.1, right - (right - left) * 0.1]) {
      ltrb(ctx, px - 1.5, deck, px + 1.5, h, p(t.primaryContainer, 0.45));
    }
  };
}

/** Slanted rain streaks. */
export function rain(color: string): Painter {
  return (ctx, w, h) => {
    const r = new Rng(3);
    for (let i = 0; i < 22; i++) {
      const x = w * r.next();
      const y = h * r.next() * 0.8;
      const len = 6 + r.next() * 7;
      line(ctx, x, y, x - len * 0.35, y + len, color, 1.2, 'round');
    }
  };
}

/** A few gulls — little "v" strokes. */
export function birds(color: string): Painter {
  return (ctx, w, h) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.lineCap = 'round';
    for (const [fx, fy, s] of [
      [0.15, 0.55, 1.0],
      [0.45, 0.25, 0.8],
      [0.75, 0.6, 0.65],
    ]) {
      const cx = w * fx;
      const cy = h * fy;
      const wing = 6 * s;
      ctx.beginPath();
      ctx.moveTo(cx - wing, cy - wing * 0.5);
      ctx.quadraticCurveTo(cx - wing * 0.4, cy - wing * 0.7, cx, cy);
      ctx.quadraticCurveTo(cx + wing * 0.4, cy - wing * 0.7, cx + wing, cy - wing * 0.5);
      ctx.stroke();
    }
  };
}

/** The city hall of the City Official mockups: steps, a colonnade under a
 *  pediment, and a domed drum with a cupola, in the persona's pale stone. */
export function capitol(t: PersonaTheme): Painter {
  return (ctx, w, h) => {
    const stone = isDark(t) ? t.skylineNear : mix(t.card, t.skylineFar, 0.25);
    const shade = t.skylineFar;
    const dome = isDark(t) ? t.primaryContainer : t.skylineNear;
    // Steps and body.
    rect(ctx, 0, h * 0.9, w, h * 0.1, shade);
    rect(ctx, w * 0.04, h * 0.84, w * 0.92, h * 0.06, stone);
    const bodyTop = h * 0.52;
    ltrb(ctx, w * 0.08, bodyTop, w * 0.92, h * 0.84, stone);
    // Colonnade.
    for (let i = 0; i < 7; i++) rect(ctx, w * (0.14 + i * 0.12), bodyTop + h * 0.06, w * 0.035, h * 0.24, shade);
    if (isDark(t)) {
      for (let i = 0; i < 6; i++) {
        rect(ctx, w * (0.19 + i * 0.12), bodyTop + h * 0.1, w * 0.04, h * 0.12, t.skylineWindow);
      }
    }
    // Pediment.
    polygon(ctx, [
      [w * 0.04, bodyTop],
      [w * 0.5, bodyTop - h * 0.14],
      [w * 0.96, bodyTop],
    ]);
    ctx.fillStyle = stone;
    ctx.fill();
    // Drum, dome, cupola, spire.
    ltrb(ctx, w * 0.32, h * 0.27, w * 0.68, bodyTop - h * 0.06, stone);
    ctx.fillStyle = dome;
    ctx.beginPath();
    ctx.moveTo(w * 0.5, h * 0.27);
    ctx.ellipse(w * 0.5, h * 0.27, w * 0.2, h * 0.19, 0, Math.PI, Math.PI * 2);
    ctx.closePath();
    ctx.fill();
    ltrb(ctx, w * 0.46, h * 0.02, w * 0.54, h * 0.1, stone);
    ltrb(ctx, w * 0.495, 0, w * 0.505, h * 0.03, dome);
  };
}

/** A striped lighthouse with its lamp room. */
export function lighthouse(t: PersonaTheme): Painter {
  return (ctx, w, h) => {
    const body = isDark(t) ? t.skylineNear : t.card;
    const band = t.primaryContainer;
    const top = h * 0.24;
    const tower = () =>
      polygon(ctx, [
        [w * 0.3, top],
        [w * 0.7, top],
        [w * 0.82, h],
        [w * 0.18, h],
      ]);
    tower();
    ctx.fillStyle = body;
    ctx.fill();
    ctx.save();
    tower();
    ctx.clip();
    for (const y of [0.4, 0.62, 0.84]) rect(ctx, 0, h * y, w, h * 0.09, band);
    ctx.restore();
    // Gallery, lamp room and roof.
    ltrb(ctx, w * 0.2, top - h * 0.03, w * 0.8, top + h * 0.01, band);
    if (isDark(t)) circle(ctx, w * 0.5, top - h * 0.1, w * 0.5, alpha(LAMP_GLOW, 0.25));
    ltrb(ctx, w * 0.34, top - h * 0.14, w * 0.66, top - h * 0.03, LAMP_GLOW);
    polygon(ctx, [
      [w * 0.28, top - h * 0.14],
      [w * 0.5, top - h * 0.24],
      [w * 0.72, top - h * 0.14],
    ]);
    ctx.fillStyle = band;
    ctx.fill();
  };
}

/** A farmhouse: warm walls, a red roof, a door and a window. */
export function farmhouse(t: PersonaTheme): Painter {
  return (ctx, w, h) => {
    const wall = isDark(t) ? mix(FARM_WALL, t.sheet, 0.55) : FARM_WALL;
    const roof = isDark(t) ? mix(FARM_ROOF, t.sheet, 0.4) : FARM_ROOF;
    const dark = isDark(t) ? LAMP_GLOW : t.foliageDeep;
    ltrb(ctx, w * 0.12, h * 0.45, w * 0.88, h, wall);
    polygon(ctx, [
      [0, h * 0.5],
      [w * 0.5, h * 0.05],
      [w, h * 0.5],
    ]);
    ctx.fillStyle = roof;
    ctx.fill();
    ltrb(ctx, w * 0.42, h * 0.66, w * 0.58, h, dark);
    ltrb(ctx, w * 0.2, h * 0.58, w * 0.34, h * 0.72, dark);
    ltrb(ctx, w * 0.66, h * 0.58, w * 0.8, h * 0.72, dark);
  };
}

/** Broad crop leaves growing in from a lower corner (the Farmer mockups'
 *  leafy frame). `mirror` grows them from the right. */
export function leaves(t: PersonaTheme, { mirror = false } = {}): Painter {
  return (ctx, w, h) => {
    ctx.save();
    if (mirror) {
      ctx.translate(w, 0);
      ctx.scale(-1, 1);
    }
    const leaf = (bx: number, by: number, angle: number, len: number, color: string) => {
      ctx.save();
      ctx.translate(bx, by);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(len * 0.35, -len * 0.28, len, 0);
      ctx.quadraticCurveTo(len * 0.35, len * 0.28, 0, 0);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      line(ctx, 0, 0, len * 0.9, 0, alpha(t.skylineWindow, 0.5), 1);
      ctx.restore();
    };
    ctx.beginPath();
    ctx.moveTo(w * 0.18, h);
    ctx.quadraticCurveTo(w * 0.22, h * 0.5, w * 0.34, h * 0.12);
    ctx.strokeStyle = t.foliageDeep;
    ctx.lineWidth = 2.2;
    ctx.stroke();
    leaf(w * 0.2, h * 0.78, -2.5, w * 0.62, t.foliageDeep);
    leaf(w * 0.22, h * 0.6, -0.55, w * 0.7, t.foliage);
    leaf(w * 0.27, h * 0.36, -2.2, w * 0.5, t.foliage);
    leaf(w * 0.31, h * 0.2, -0.9, w * 0.5, t.foliageDeep);
    ctx.restore();
  };
}

/** A fishing trawler: hull, wheelhouse with windows, masts and rigging. */
export function trawler(t: PersonaTheme): Painter {
  return (ctx, w, h) => {
    const hullTop = h * 0.62;
    const cabin = isDark(t) ? t.skylineNear : t.card;
    const rig = isDark(t) ? t.inkMuted : t.primaryContainer;
    // Masts and rigging.
    line(ctx, w * 0.38, hullTop, w * 0.38, 0, rig, 1.8);
    line(ctx, w * 0.72, hullTop, w * 0.72, h * 0.22, rig, 1.8);
    line(ctx, w * 0.38, h * 0.02, w * 0.04, hullTop, rig, 1);
    line(ctx, w * 0.38, h * 0.02, w * 0.72, h * 0.22, rig, 1);
    line(ctx, w * 0.72, h * 0.22, w * 0.98, hullTop - h * 0.04, rig, 1);
    // Wheelhouse.
    ltrb(ctx, w * 0.44, h * 0.38, w * 0.8, hullTop + 1, cabin);
    ltrb(ctx, w * 0.5, h * 0.3, w * 0.74, h * 0.4, cabin);
    const glass = isDark(t) ? LAMP_GLOW : t.primary;
    for (let i = 0; i < 3; i++) rect(ctx, w * (0.49 + i * 0.1), h * 0.44, w * 0.06, h * 0.07, glass);
    // Hull with a pale waterline stripe.
    polygon(ctx, [
      [0, hullTop],
      [w, hullTop - h * 0.06],
      [w * 0.86, h],
      [w * 0.1, h],
    ]);
    ctx.fillStyle = t.primaryContainer;
    ctx.fill();
    line(ctx, w * 0.04, hullTop + h * 0.1, w * 0.96, hullTop + h * 0.04, alpha(t.skylineWindow, 0.8), 1.6);
  };
}
