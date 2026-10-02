// The onboarding screens' own look (pics/ Languages and Welcome mockups): a
// fixed blue palette in a light and a dark design — not the persona
// palettes, since nobody has picked a persona yet — and the painted
// panorama behind the welcome: skyline, village, a fisherman's boat on the
// sea, the sun on the horizon and a climbing airplane. A line-for-line port
// of mobile/lib/components/onboarding_scene.dart; keep the two in step.
import { alpha } from '../../theme/personaTheme';
import type { Painter } from './painters';

export interface OnbPalette {
  isDark: boolean;
  bgTop: string;
  bgBottom: string;
  ink: string;
  muted: string;
  accent: string;
  buttonTop: string;
  buttonBottom: string;
  sheet: string;
  sheetBorder: string;
  field: string;
  fieldBorder: string;
  selectedFill: string;
  selectedBorder: string;
  radio: string;
  guestFill: string;
  divider: string;
  // Scene.
  cloud: string;
  hill: string;
  hillNear: string;
  towerFar: string;
  towerNear: string;
  window: string;
  sea: string;
  seaDeep: string;
  glint: string;
  sand: string;
  land: string;
  landDeep: string;
  trunk: string;
  wall: string;
  roof: string;
  houseWindow: string;
  hull: string;
  rigging: string;
  sun: string;
  sunGlow: string;
  plane: string;
  trail: string;
  bird: string;
}

export const ONB_LIGHT: OnbPalette = {
  isDark: false,
  bgTop: '#DDEFFC',
  bgBottom: '#F3F9FE',
  ink: '#0C2148',
  muted: '#5D6B82',
  accent: '#1273EA',
  buttonTop: '#1E86F7',
  buttonBottom: '#0B67E6',
  sheet: '#F6FAFE',
  sheetBorder: '#FFFFFF',
  field: '#FAFCFF',
  fieldBorder: '#D2E1F2',
  selectedFill: '#E3F0FC',
  selectedBorder: '#8DC2F0',
  radio: '#9AA6B8',
  guestFill: '#E6F1FD',
  divider: '#D6E0EC',
  cloud: '#FFFFFF',
  hill: '#C3E1F5',
  hillNear: '#A7D3F0',
  towerFar: '#A3CFF2',
  towerNear: '#5DA6E9',
  window: '#E2F1FF',
  sea: '#52B6F0',
  seaDeep: '#1F86DD',
  glint: '#FFFFFF',
  sand: '#F2E2B4',
  land: '#6DBE4B',
  landDeep: '#3B9A3C',
  trunk: '#7A5A3A',
  wall: '#F7EBD2',
  roof: '#E2603A',
  houseWindow: '#4F8FD6',
  hull: '#1C3762',
  rigging: '#1C3762',
  sun: '#FFC83A',
  sunGlow: '#FFE08A',
  plane: '#2D8BEA',
  trail: '#FFFFFF',
  bird: '#3F86CF',
};

export const ONB_DARK: OnbPalette = {
  isDark: true,
  bgTop: '#0A1C40',
  bgBottom: '#071533',
  ink: '#FFFFFF',
  muted: '#B3C3DE',
  accent: '#3B9BFF',
  buttonTop: '#1C8EFF',
  buttonBottom: '#0A6CF0',
  sheet: '#0B1E45',
  sheetBorder: '#1B3667',
  field: '#0D2350',
  fieldBorder: '#2A4A80',
  selectedFill: '#0F2D63',
  selectedBorder: '#2B86F5',
  radio: '#8EA5CE',
  guestFill: '#12305F',
  divider: '#2A426E',
  cloud: '#16336C',
  hill: '#15346C',
  hillNear: '#112B5B',
  towerFar: '#1A3C78',
  towerNear: '#214C94',
  window: '#FFD267',
  sea: '#1B4E98',
  seaDeep: '#0D2A5C',
  glint: '#FFC85A',
  sand: '#2C4A5E',
  land: '#1F5B3C',
  landDeep: '#143F2B',
  trunk: '#2B2A2A',
  wall: '#4E5F86',
  roof: '#8E4A36',
  houseWindow: '#FFD267',
  hull: '#07142E',
  rigging: '#07142E',
  sun: '#F7BE3B',
  sunGlow: '#F39A2B',
  plane: '#55A8FF',
  trail: '#6FB6FF',
  bird: '#6E9BDD',
};

/** Deterministic pseudo-random stream — the same LCG as mobile. */
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

type Ctx = CanvasRenderingContext2D;

function circle(ctx: Ctx, x: number, y: number, r: number, fill: string | CanvasGradient) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

function poly(ctx: Ctx, pts: [number, number][], fill: string) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.closePath();
  ctx.fill();
}

function line(
  ctx: Ctx,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stroke: string | CanvasGradient,
  width: number,
) {
  ctx.strokeStyle = stroke;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function cloud(ctx: Ctx, cx: number, cy: number, s: number, color: string) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(cx - 46 * s, cy - 13 * s, 92 * s, 26 * s, 13 * s);
  ctx.fill();
  circle(ctx, cx - 16 * s, cy - 12 * s, 17 * s, color);
  circle(ctx, cx + 10 * s, cy - 18 * s, 22 * s, color);
  circle(ctx, cx + 32 * s, cy - 6 * s, 13 * s, color);
}

function birds(ctx: Ctx, x: number, y: number, s: number, color: string) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.lineCap = 'round';
  for (const [dx, dy, k] of [
    [0, 0, 1],
    [16, 6, 0.75],
  ]) {
    const ox = x + dx * s;
    const oy = y + dy * s;
    const w = 7 * s * k;
    ctx.beginPath();
    ctx.moveTo(ox - w, oy - w * 0.35);
    ctx.quadraticCurveTo(ox - w * 0.4, oy - w * 0.45, ox, oy + w * 0.12);
    ctx.quadraticCurveTo(ox + w * 0.4, oy - w * 0.45, ox + w, oy - w * 0.35);
    ctx.stroke();
  }
}

/** A half-set sun on the line `horizonY` with its glow. */
function sun(ctx: Ctx, cx: number, cy: number, r: number, horizonY: number, p: OnbPalette) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(cx - r * 3, cy - r * 3, r * 6, horizonY - (cy - r * 3));
  ctx.clip();
  const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 1.9);
  glow.addColorStop(0, alpha(p.sunGlow, p.isDark ? 0.45 : 0.55));
  glow.addColorStop(1, alpha(p.sunGlow, 0));
  circle(ctx, cx, cy, r * 1.9, glow);
  circle(ctx, cx, cy, r, p.sun);
  ctx.restore();
}

/** Short glints on the water under the sun. */
function glints(ctx: Ctx, cx: number, cy: number, r: number, p: OnbPalette) {
  for (let i = 0; i < 4; i++) {
    const y = cy + 4 + i * 4.5;
    const half = r * (0.9 - i * 0.18);
    line(ctx, cx - half, y, cx + half, y, alpha(p.glint, p.isDark ? 0.75 : 0.8), 1.6);
  }
}

function palm(ctx: Ctx, bx: number, by: number, h: number, p: OnbPalette, mirror = false) {
  const dir = mirror ? -1 : 1;
  const tx = bx + dir * h * 0.18;
  const ty = by - h;
  ctx.strokeStyle = p.trunk;
  ctx.lineWidth = Math.max(1.6, h * 0.07);
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(bx, by);
  ctx.quadraticCurveTo(bx + dir * h * 0.02, by - h * 0.6, tx, ty);
  ctx.stroke();
  ctx.fillStyle = p.landDeep;
  for (const a of [-2.7, -2.1, -1.2, -0.45, 0.1]) {
    const tipX = tx + Math.cos(a) * h * 0.5;
    const tipY = ty + Math.sin(a) * h * 0.32 + h * 0.12;
    const midX = tx + Math.cos(a) * h * 0.25;
    const midY = ty + Math.sin(a) * h * 0.3 - h * 0.04;
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.quadraticCurveTo(midX, midY - h * 0.06, tipX, tipY);
    ctx.quadraticCurveTo(midX, midY + h * 0.04, tx, ty);
    ctx.fill();
  }
}

/** The airplane's silhouette, nose pointing along +x, `l` long. */
function plane(ctx: Ctx, x: number, y: number, l: number, angle: number, color: string) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(-l * 0.5, -l * 0.055, l, l * 0.11, l * 0.055);
  ctx.fill();
  poly(
    ctx,
    [
      [l * 0.1, 0],
      [-l * 0.16, -l * 0.42],
      [-l * 0.27, -l * 0.42],
      [-l * 0.12, 0],
      [-l * 0.27, l * 0.42],
      [-l * 0.16, l * 0.42],
    ],
    color,
  );
  poly(
    ctx,
    [
      [-l * 0.36, 0],
      [-l * 0.5, -l * 0.17],
      [-l * 0.56, -l * 0.17],
      [-l * 0.48, 0],
      [-l * 0.56, l * 0.17],
      [-l * 0.5, l * 0.17],
    ],
    color,
  );
  ctx.restore();
}

function towers(
  ctx: Ctx,
  p: OnbPalette,
  right: number,
  base: number,
  minH: number,
  maxH: number,
  r: Rng,
  color: string,
  windows: boolean,
) {
  const lit = alpha(p.window, p.isDark ? 0.9 : 0.85);
  let x = -r.next() * 10;
  while (x < right) {
    const tw = 14 + r.next() * 18;
    const th = minH + r.next() * (maxH - minH);
    const top = base - th;
    ctx.fillStyle = color;
    ctx.fillRect(x, top, tw, th);
    if (r.next() > 0.7) ctx.fillRect(x + tw / 2 - 0.8, top - th * 0.14, 1.6, th * 0.14);
    if (windows) {
      ctx.fillStyle = lit;
      for (let wy = top + 5; wy < base - 8; wy += 6.5) {
        for (let wx = x + 3; wx < x + tw - 4; wx += 5) {
          if (!p.isDark || r.next() > 0.35) ctx.fillRect(wx, wy, 2.2, 3);
        }
      }
    }
    x += tw + r.next() * 5 - 1;
  }
}

function house(ctx: Ctx, p: OnbPalette, bx: number, by: number, s: number) {
  ctx.fillStyle = p.wall;
  ctx.fillRect(bx - s * 0.5, by - s * 0.42, s, s * 0.42);
  poly(
    ctx,
    [
      [bx - s * 0.6, by - s * 0.4],
      [bx - s * 0.36, by - s * 0.72],
      [bx + s * 0.36, by - s * 0.72],
      [bx + s * 0.6, by - s * 0.4],
    ],
    p.roof,
  );
  ctx.fillStyle = p.houseWindow;
  ctx.fillRect(bx - s * 0.36, by - s * 0.32, s * 0.16, s * 0.13);
  ctx.fillRect(bx + s * 0.2, by - s * 0.32, s * 0.16, s * 0.13);
  ctx.fillStyle = p.roof;
  ctx.fillRect(bx - s * 0.07, by - s * 0.27, s * 0.14, s * 0.27);
}

/** A small fishing boat: hull, mast and sail, and the fisherman with a rod. */
function boat(ctx: Ctx, p: OnbPalette, cx: number, cy: number, s: number) {
  line(ctx, cx + s * 0.12, cy - s * 0.1, cx + s * 0.12, cy - s * 0.78, p.rigging, 1.4);
  poly(
    ctx,
    [
      [cx + s * 0.15, cy - s * 0.74],
      [cx + s * 0.44, cy - s * 0.2],
      [cx + s * 0.15, cy - s * 0.2],
    ],
    p.isDark ? p.towerNear : '#FFFFFF',
  );
  circle(ctx, cx - s * 0.16, cy - s * 0.5, s * 0.065, p.hull);
  ctx.fillStyle = p.hull;
  ctx.beginPath();
  ctx.roundRect(cx - s * 0.23, cy - s * 0.43, s * 0.14, s * 0.3, s * 0.04);
  ctx.fill();
  line(ctx, cx - s * 0.12, cy - s * 0.36, cx - s * 0.62, cy - s * 0.78, p.rigging, 1.4);
  line(ctx, cx - s * 0.62, cy - s * 0.78, cx - s * 0.7, cy + s * 0.05, alpha(p.rigging, 0.6), 0.8);
  poly(
    ctx,
    [
      [cx - s * 0.5, cy - s * 0.14],
      [cx + s * 0.55, cy - s * 0.18],
      [cx + s * 0.36, cy + s * 0.08],
      [cx - s * 0.38, cy + s * 0.08],
    ],
    p.hull,
  );
  line(ctx, cx - s * 0.48, cy + s * 0.15, cx + s * 0.46, cy + s * 0.15, alpha(p.glint, 0.5), 1.2);
}

/** The welcome panorama: clouds flank the title in the upper part, the
 *  scene fills the band down to the horizon and the sea below it. */
export const onboardingScene =
  (p: OnbPalette): Painter =>
  (ctx, w, h) => {
    const hz = h * 0.8;

    cloud(ctx, w * 0.02, h * 0.42, 0.8, alpha(p.cloud, p.isDark ? 0.95 : 0.9));
    cloud(ctx, w * 0.97, h * 0.38, 0.95, alpha(p.cloud, p.isDark ? 0.95 : 0.9));

    // Far hills behind the sea, and the sun setting between them.
    ctx.fillStyle = p.hill;
    ctx.beginPath();
    ctx.moveTo(w * 0.5, hz);
    ctx.quadraticCurveTo(w * 0.62, hz - h * 0.06, w * 0.74, hz - h * 0.025);
    ctx.quadraticCurveTo(w * 0.9, hz - h * 0.08, w, hz - h * 0.04);
    ctx.lineTo(w, hz);
    ctx.closePath();
    ctx.fill();
    const sunX = w * 0.8;
    const sunR = Math.min(24, h * 0.07);
    sun(ctx, sunX, hz, sunR, hz, p);

    // Skyline over the left two-thirds.
    towers(ctx, p, w * 0.7, hz, h * 0.07, h * 0.16, new Rng(17), p.towerFar, false);
    towers(ctx, p, w * 0.6, hz, h * 0.05, h * 0.11, new Rng(5), p.towerNear, true);

    // Sea.
    const sea = ctx.createLinearGradient(0, hz, 0, h);
    sea.addColorStop(0, p.sea);
    sea.addColorStop(1, p.seaDeep);
    ctx.fillStyle = sea;
    ctx.fillRect(0, hz, w, h - hz);
    glints(ctx, sunX, hz, sunR, p);

    // The bank on the left: a sand edge, then grass.
    const shore = () => {
      ctx.beginPath();
      ctx.moveTo(0, hz - h * 0.05);
      ctx.quadraticCurveTo(w * 0.22, hz - h * 0.07, w * 0.42, hz + h * 0.01);
      ctx.quadraticCurveTo(w * 0.5, hz + h * 0.05, w * 0.36, hz + h * 0.1);
      ctx.quadraticCurveTo(w * 0.25, h, w * 0.1, h + 2);
      ctx.lineTo(0, h + 2);
      ctx.closePath();
    };
    ctx.fillStyle = p.sand;
    shore();
    ctx.fill();
    ctx.save();
    ctx.translate(-w * 0.02, -h * 0.008);
    ctx.fillStyle = p.land;
    shore();
    ctx.fill();
    ctx.restore();

    // Trees along the bank: a hedge of round crowns and two palms.
    const r = new Rng(41);
    let x = -6;
    while (x < w * 0.34) {
      const y = hz - h * 0.05 * (1 - x / (w * 0.42)) - h * 0.01;
      const rad = 4 + r.next() * 5;
      circle(ctx, x, y - rad * 0.3, rad, r.next() > 0.5 ? p.landDeep : p.land);
      x += rad * (1.3 + r.next());
    }
    palm(ctx, w * 0.05, hz - h * 0.05, h * 0.11, p);
    palm(ctx, w * 0.36, hz - h * 0.012, h * 0.08, p, true);

    house(ctx, p, w * 0.2, hz - h * 0.03, Math.min(32, w * 0.08));
    boat(ctx, p, w * 0.62, hz + h * 0.075, Math.min(48, w * 0.12));

    // The airplane climbing up and to the right, trailing a contrail.
    const px = w * 0.87;
    const py = h * 0.69;
    const climb = -0.38;
    const trail = ctx.createLinearGradient(w * 0.52, h * 0.77, px, py);
    trail.addColorStop(0, alpha(p.trail, 0));
    trail.addColorStop(1, alpha(p.trail, p.isDark ? 0.7 : 0.95));
    line(ctx, w * 0.52, h * 0.77, px - Math.cos(climb) * 10, py - Math.sin(climb) * 10, trail, 2);
    plane(ctx, px, py, Math.min(34, w * 0.085), climb, p.plane);

    birds(ctx, w * 0.1, h * 0.62, 1, p.bird);
    birds(ctx, w * 0.68, h * 0.73, 0.8, p.bird);
  };

/** The Languages page: clouds in the upper corners. */
export const onboardingClouds =
  (p: OnbPalette): Painter =>
  (ctx, w, h) => {
    const c = alpha(p.cloud, p.isDark ? 0.9 : 0.85);
    cloud(ctx, w * 0.06, h * 0.42, 0.85, c);
    cloud(ctx, w * 0.96, h * 0.3, 0.9, c);
    cloud(ctx, w * 1.0, h * 0.88, 0.75, c);
  };

/** The Languages page's foot: soft hills, the sea, the sun on the horizon
 *  and two birds (palms on the dark design). */
export const onboardingFooter =
  (p: OnbPalette): Painter =>
  (ctx, w, h) => {
    const hz = h * 0.66;
    ctx.fillStyle = alpha(p.hill, p.isDark ? 1 : 0.85);
    ctx.beginPath();
    ctx.moveTo(0, hz - h * 0.18);
    ctx.quadraticCurveTo(w * 0.14, hz - h * 0.36, w * 0.3, hz - h * 0.16);
    ctx.quadraticCurveTo(w * 0.46, hz - h * 0.3, w * 0.62, hz - h * 0.12);
    ctx.quadraticCurveTo(w * 0.8, hz - h * 0.3, w, hz - h * 0.2);
    ctx.lineTo(w, hz);
    ctx.lineTo(0, hz);
    ctx.closePath();
    ctx.fill();
    const sunX = w * 0.8;
    const sunR = Math.min(34, h * 0.26);
    sun(ctx, sunX, hz, sunR, hz, p);
    ctx.fillStyle = p.hillNear;
    ctx.beginPath();
    ctx.moveTo(0, hz - h * 0.06);
    ctx.quadraticCurveTo(w * 0.22, hz - h * 0.2, w * 0.45, hz - h * 0.04);
    ctx.lineTo(w * 0.45, hz);
    ctx.lineTo(0, hz);
    ctx.closePath();
    ctx.fill();
    const sea = ctx.createLinearGradient(0, hz, 0, h);
    sea.addColorStop(0, alpha(p.sea, p.isDark ? 0.9 : 0.55));
    sea.addColorStop(1, alpha(p.seaDeep, p.isDark ? 0.9 : 0.4));
    ctx.fillStyle = sea;
    ctx.fillRect(0, hz, w, h - hz);
    glints(ctx, sunX, hz, sunR, p);
    if (p.isDark) {
      palm(ctx, w * 0.06, hz - h * 0.04, h * 0.3, p);
      palm(ctx, w * 0.95, hz - h * 0.08, h * 0.34, p, true);
    }
    birds(ctx, w * 0.6, h * 0.18, 1, p.bird);
    birds(ctx, w * 0.86, h * 0.08, 0.8, p.bird);
  };
