// Persona themes — the persona picked on the Persona page is the global
// theme selector: every page, the shell chrome, the painted scenery and the
// form controls read their colours from the active persona's PersonaTheme.
// Same palettes as mobile/lib/persona_theme.dart (sampled from the pics/
// persona mockups):
//   general       → blue / sky-blue, city skyline
//   farmer        → green, fields and crops
//   fisherman     → deep ocean blue, waves and boats
//   aviation      → purple + pink, airport and aircraft
//   city_official → teal / cyan, skyline, river and rain
//
// Wiring: UiPrefsContext calls applyTheme(), which writes every token as a
// CSS custom property on <html>; tailwind.config.js maps the colour names
// the pages use (primary, surface-container-low, ink, tint, …) onto those
// properties, so a persona or appearance change re-themes the whole app
// without touching a component. The painted scenery reads the palette
// object directly (components/scenery/).
//
// Dark mode: every persona also has a dark palette with the same field
// names, derived from the light one's hues by darkOf() — deep tinted night
// skies, lit windows, a moon instead of the sun. Persona-independent
// colours (the LIVE/verified green, the sun, IMD warning colours) stay
// literal in tailwind.config.js.

export type PersonaScene = 'city' | 'fields' | 'sea' | 'airport' | 'civic';
export type Brightness = 'light' | 'dark';

export interface PersonaTheme {
  brightness: Brightness;
  scene: PersonaScene;
  /** The persona's badge in the top bar and brand spots (Material Symbols
   *  name): person, leaf, sailboat, plane, city hall. */
  markIcon: string;

  /** Primary accent: buttons, selected states, links, active nav, icons. */
  primary: string;
  onPrimary: string;
  /** A deeper shade of primary for pressed/strong text. */
  primaryContainer: string;
  /** Pale accent wash (pill buttons, highlighted chips) and the text on it. */
  primaryFixed: string;
  onPrimaryFixed: string;
  /** Secondary accent — the second colour of gradients and highlights. */
  accent2: string;
  accent2Soft: string;

  /** Page chrome: the sky gradient behind the top bar and the content sheet. */
  skyTop: string;
  skyBottom: string;
  sheet: string;
  cloudPuff: string;

  /** Cards and their tinted fills. */
  card: string;
  cardBorder: string;
  tint: string;
  tintStrong: string;
  /** Colour of card and chrome shadows (used at low alpha). */
  shadow: string;

  /** Text. */
  ink: string;
  inkMuted: string;
  onSurface: string;
  onSurfaceVariant: string;
  outline: string;
  outlineVariant: string;

  /** Neutral panels (loading lines, chips, evidence panels). */
  surfaceContainerLowest: string;
  surfaceContainerLow: string;
  surfaceContainer: string;
  surfaceContainerHigh: string;

  /** Bottom navigation. */
  navBar: string;
  navIdle: string;

  /** Painted scenery: far and near silhouettes, lit windows / highlights,
   *  greenery, and two water (or haze) layers. */
  skylineFar: string;
  skylineNear: string;
  skylineWindow: string;
  foliage: string;
  foliageDeep: string;
  water: string;
  waterDeep: string;

  /** Weather glyph tints (the sun stays SUN on every persona). */
  cloudGlyph: string;
  rainGlyph: string;
  moonGlyph: string;
}

/** Persona-independent illustration colours (mobile AppColors). */
export const SUN = '#FFB21E';
export const SUN_CORE = '#FFCB4F';
export const FARM_WALL = '#F4E4C4';
export const FARM_ROOF = '#C65A3C';
export const LAMP_GLOW = '#FFE08A';

type LightSpec = Omit<
  PersonaTheme,
  'brightness' | 'onPrimary' | 'cloudPuff' | 'card' | 'surfaceContainerLowest' | 'navBar'
> &
  Partial<Pick<PersonaTheme, 'cloudPuff'>>;

function light(spec: LightSpec): PersonaTheme {
  return {
    brightness: 'light',
    onPrimary: '#FFFFFF',
    cloudPuff: '#FFFFFF',
    card: '#FFFFFF',
    surfaceContainerLowest: '#FFFFFF',
    navBar: '#FFFFFF',
    ...spec,
  };
}

/** Light palettes, keyed by persona id (services/orchestrator/persona.py). */
export const PERSONA_THEMES: Record<string, PersonaTheme> = {
  // Blue / sky-blue, a dense city skyline — calm everyday weather.
  general: light({
    scene: 'city',
    markIcon: 'person',
    primary: '#1E63D6',
    primaryContainer: '#1450B5',
    primaryFixed: '#DCE8FF',
    onPrimaryFixed: '#0A2D6E',
    accent2: '#4FA3F7',
    accent2Soft: '#E3F1FE',
    skyTop: '#C6DEFA',
    skyBottom: '#EAF3FE',
    sheet: '#F5F9FF',
    cardBorder: '#D9E6F7',
    tint: '#E7F0FE',
    tintStrong: '#D2E3FC',
    shadow: '#1E63D6',
    ink: '#0F2548',
    inkMuted: '#566783',
    onSurface: '#0B1F3F',
    onSurfaceVariant: '#3E4C63',
    outline: '#6F7C92',
    outlineVariant: '#C3CEDF',
    surfaceContainerLow: '#F0F5FE',
    surfaceContainer: '#E6EEFC',
    surfaceContainerHigh: '#DCE7FA',
    navIdle: '#6B7A93',
    skylineFar: '#B3D0F3',
    skylineNear: '#5E9BE6',
    skylineWindow: '#E3EEFC',
    foliage: '#7DC36B',
    foliageDeep: '#4E9E55',
    water: '#CFE2FA',
    waterDeep: '#AFCDF3',
    cloudGlyph: '#7EACEB',
    rainGlyph: '#3F7FE0',
    moonGlyph: '#5D6FC4',
  }),
  // Fresh green, fields, crop rows, leafy edges and a tractor.
  farmer: light({
    scene: 'fields',
    markIcon: 'eco',
    primary: '#2E7D32',
    primaryContainer: '#1B5E20',
    primaryFixed: '#D6EED3',
    onPrimaryFixed: '#0E3B13',
    accent2: '#8BC34A',
    accent2Soft: '#EEF7DC',
    skyTop: '#D5EED0',
    skyBottom: '#F0F8EC',
    sheet: '#F6FBF3',
    cardBorder: '#D4E9CF',
    tint: '#E6F4E2',
    tintStrong: '#CDE8C6',
    shadow: '#2E7D32',
    ink: '#15301B',
    inkMuted: '#566E5B',
    onSurface: '#10281A',
    onSurfaceVariant: '#3D5343',
    outline: '#6D8272',
    outlineVariant: '#C0D5C2',
    surfaceContainerLow: '#EFF7EC',
    surfaceContainer: '#E3F1DE',
    surfaceContainerHigh: '#D7EBD1',
    navIdle: '#6A8270',
    skylineFar: '#B5DBA3',
    skylineNear: '#8CC152',
    skylineWindow: '#E6F3B4',
    foliage: '#5DAA45',
    foliageDeep: '#2F7D32',
    water: '#CDE8B0',
    waterDeep: '#A5D27E',
    cloudGlyph: '#86B3DD',
    rainGlyph: '#3F7FE0',
    moonGlyph: '#5D6FC4',
  }),
  // Ocean blue, bright swells, a trawler, gulls and a lighthouse.
  fisherman: light({
    scene: 'sea',
    markIcon: 'sailing',
    primary: '#1565C0',
    primaryContainer: '#0D47A1',
    primaryFixed: '#D4E6FA',
    onPrimaryFixed: '#062B5C',
    accent2: '#29A8E0',
    accent2Soft: '#DDF1FB',
    skyTop: '#C3E1F8',
    skyBottom: '#E7F3FC',
    sheet: '#F3F9FE',
    cardBorder: '#D0E4F5',
    tint: '#E1EFFB',
    tintStrong: '#C9E1F7',
    shadow: '#1565C0',
    ink: '#0B2342',
    inkMuted: '#4E657F',
    onSurface: '#081D38',
    onSurfaceVariant: '#384C63',
    outline: '#687B90',
    outlineVariant: '#BDCFE1',
    surfaceContainerLow: '#EDF5FC',
    surfaceContainer: '#E0EDF9',
    surfaceContainerHigh: '#D5E6F6',
    navIdle: '#667C93',
    skylineFar: '#A9CDEB',
    skylineNear: '#7FB2DE',
    skylineWindow: '#FFFFFF',
    foliage: '#7FB89A',
    foliageDeep: '#4F8F72',
    water: '#55A8E8',
    waterDeep: '#1766C2',
    cloudGlyph: '#76A8E0',
    rainGlyph: '#2F6FD0',
    moonGlyph: '#4E63B8',
  }),
  // Purple + pink: lavender sky, pink clouds, tower, terminal and a jet.
  aviation: light({
    scene: 'airport',
    markIcon: 'flight',
    primary: '#5B3CC4',
    primaryContainer: '#452A9E',
    primaryFixed: '#E5DCFA',
    onPrimaryFixed: '#26135F',
    accent2: '#E36BAE',
    accent2Soft: '#FBE3F1',
    skyTop: '#D8CAF6',
    skyBottom: '#F6ECF9',
    sheet: '#FAF6FE',
    cloudPuff: '#FCE8F4',
    cardBorder: '#E5DAF6',
    tint: '#EFE8FC',
    tintStrong: '#E0D3F8',
    shadow: '#5B3CC4',
    ink: '#21174A',
    inkMuted: '#635D86',
    onSurface: '#1C1340',
    onSurfaceVariant: '#484266',
    outline: '#7A7494',
    outlineVariant: '#CCC4E0',
    surfaceContainerLow: '#F5F0FE',
    surfaceContainer: '#EDE6FC',
    surfaceContainerHigh: '#E4DBF9',
    navIdle: '#79739A',
    skylineFar: '#D1C1F0',
    skylineNear: '#9A82DC',
    skylineWindow: '#F5EEFF',
    foliage: '#F1B9DA',
    foliageDeep: '#D3A0E6',
    water: '#E9DCF8',
    waterDeep: '#D6C2F2',
    cloudGlyph: '#9C8CE3',
    rainGlyph: '#6B55D6',
    moonGlyph: '#6A4FC9',
  }),
  // Teal / cyan, a civic skyline with the city hall, trees, river and rain.
  city_official: light({
    scene: 'civic',
    markIcon: 'account_balance',
    primary: '#0E7C86',
    primaryContainer: '#085E66',
    primaryFixed: '#CDEDEE',
    onPrimaryFixed: '#033A3F',
    accent2: '#26B5C9',
    accent2Soft: '#DAF3F6',
    skyTop: '#C5E9EB',
    skyBottom: '#E8F6F6',
    sheet: '#F3FAFA',
    cardBorder: '#CFE8E8',
    tint: '#E0F2F2',
    tintStrong: '#C6E8E9',
    shadow: '#0E7C86',
    ink: '#0C2E32',
    inkMuted: '#4F6E6F',
    onSurface: '#09272B',
    onSurfaceVariant: '#385356',
    outline: '#678385',
    outlineVariant: '#BAD5D6',
    surfaceContainerLow: '#ECF7F7',
    surfaceContainer: '#DFF1F1',
    surfaceContainerHigh: '#D3EBEB',
    navIdle: '#65807F',
    skylineFar: '#ADD6DD',
    skylineNear: '#5AA6B8',
    skylineWindow: '#E1F4F6',
    foliage: '#7CC17F',
    foliageDeep: '#3F8F5A',
    water: '#A6DAE3',
    waterDeep: '#6ABCCB',
    cloudGlyph: '#70B2C8',
    rainGlyph: '#1E86B8',
    moonGlyph: '#4D6BB5',
  }),
};

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

function parseHex(hex: string): [number, number, number] {
  const n = parseInt(hex.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex(r: number, g: number, b: number) {
  const c = (v: number) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0');
  return `#${c(r)}${c(g)}${c(b)}`.toUpperCase();
}

/** `rgba()` of a hex colour at alpha `a`. */
export function alpha(hex: string, a: number) {
  const [r, g, b] = parseHex(hex);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/** Linear blend of two hex colours (Flutter's Color.lerp). */
export function mix(a: string, b: string, t: number) {
  const [r1, g1, b1] = parseHex(a);
  const [r2, g2, b2] = parseHex(b);
  return toHex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t);
}

function hueOf(hex: string) {
  const [r, g, b] = parseHex(hex).map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  if (d === 0) return 0;
  let h: number;
  if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  h *= 60;
  return h < 0 ? h + 360 : h;
}

function fromHsl(h: number, s: number, l: number) {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const [r, g, b] =
    h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return toHex((r + m) * 255, (g + m) * 255, (b + m) * 255);
}

/** Night twin of a light palette: the same hues on deep tinted surfaces,
 *  light accents with dark text on them, dimmed scenery with lit windows. */
function darkOf(l: PersonaTheme): PersonaTheme {
  const h = hueOf(l.primary);
  const c = (sat: number, lig: number, hue?: number) => fromHsl(hue ?? h, sat, lig);
  const hA = hueOf(l.accent2);
  return {
    brightness: 'dark',
    scene: l.scene,
    markIcon: l.markIcon,
    primary: c(0.78, 0.74),
    onPrimary: c(0.6, 0.12),
    primaryContainer: c(0.55, 0.56),
    primaryFixed: c(0.4, 0.25),
    onPrimaryFixed: c(0.6, 0.88),
    accent2: c(0.75, 0.72, hA),
    accent2Soft: c(0.35, 0.2, hA),
    skyTop: c(0.42, 0.15),
    skyBottom: c(0.4, 0.09),
    sheet: c(0.34, 0.11),
    cloudPuff: c(0.22, 0.3),
    card: c(0.28, 0.155),
    cardBorder: c(0.26, 0.24),
    tint: c(0.36, 0.19),
    tintStrong: c(0.4, 0.25),
    shadow: '#000000',
    ink: c(0.3, 0.92),
    inkMuted: c(0.16, 0.7),
    onSurface: c(0.25, 0.93),
    onSurfaceVariant: c(0.16, 0.78),
    outline: c(0.12, 0.55),
    outlineVariant: c(0.2, 0.28),
    surfaceContainerLowest: c(0.28, 0.155),
    surfaceContainerLow: c(0.3, 0.13),
    surfaceContainer: c(0.3, 0.17),
    surfaceContainerHigh: c(0.3, 0.21),
    navBar: c(0.32, 0.12),
    navIdle: c(0.14, 0.62),
    skylineFar: c(0.3, 0.2),
    skylineNear: c(0.36, 0.3),
    skylineWindow: '#FFD27A',
    foliage: c(0.32, 0.26, hueOf(l.foliage)),
    foliageDeep: c(0.32, 0.18, hueOf(l.foliageDeep)),
    water: c(0.42, 0.26, hueOf(l.water)),
    waterDeep: c(0.42, 0.18, hueOf(l.waterDeep)),
    cloudGlyph: c(0.55, 0.72, hueOf(l.cloudGlyph)),
    rainGlyph: c(0.8, 0.68, hueOf(l.rainGlyph)),
    moonGlyph: '#D9DEFF',
  };
}

/** Dark palettes, same keys as PERSONA_THEMES. */
export const PERSONA_THEMES_DARK: Record<string, PersonaTheme> = Object.fromEntries(
  Object.entries(PERSONA_THEMES).map(([id, t]) => [id, darkOf(t)]),
);

/** The palette for a persona id; unknown ids get General Citizen's. */
export function personaThemeFor(id: string, brightness: Brightness = 'light'): PersonaTheme {
  const map = brightness === 'dark' ? PERSONA_THEMES_DARK : PERSONA_THEMES;
  return map[id] ?? map.general;
}

// ---------------------------------------------------------------------------
// CSS custom properties
// ---------------------------------------------------------------------------

const triplet = (hex: string) => parseHex(hex).join(' ');

/** Every themed colour name tailwind.config.js exposes, with its value for
 *  palette `t` (the Material slot mapping of mobile's appColorScheme). */
export function themeVars(t: PersonaTheme): Record<string, string> {
  const dark = t.brightness === 'dark';
  const colours: Record<string, string> = {
    primary: t.primary,
    'on-primary': t.onPrimary,
    'primary-container': t.primaryContainer,
    'on-primary-container': t.onPrimary,
    'primary-fixed': t.primaryFixed,
    'primary-fixed-dim': t.tintStrong,
    'on-primary-fixed': t.onPrimaryFixed,
    'on-primary-fixed-variant': t.primaryContainer,
    'inverse-primary': t.primaryFixed,
    'surface-tint': t.primary,
    surface: t.sheet,
    'surface-bright': t.sheet,
    background: t.sheet,
    'on-surface': t.onSurface,
    'on-background': t.onSurface,
    'on-surface-variant': t.onSurfaceVariant,
    'surface-dim': t.tintStrong,
    'surface-variant': t.tintStrong,
    'surface-container-lowest': t.surfaceContainerLowest,
    'surface-container-low': t.surfaceContainerLow,
    'surface-container': t.surfaceContainer,
    'surface-container-high': t.surfaceContainerHigh,
    'surface-container-highest': t.tintStrong,
    outline: t.outline,
    'outline-variant': t.outlineVariant,
    'inverse-surface': dark ? t.ink : '#1D3052',
    'inverse-on-surface': dark ? t.sheet : '#EDF0FF',
    error: dark ? '#FFB4AB' : '#BA1A1A',
    'on-error': dark ? '#690005' : '#FFFFFF',
    'error-container': dark ? '#93000A' : '#FFDAD6',
    'on-error-container': dark ? '#FFDAD6' : '#93000A',
    // Persona tokens beyond the Material slots.
    'accent-2': t.accent2,
    'accent-2-soft': t.accent2Soft,
    'accent-end': mix(t.primary, t.primaryContainer, 0.55),
    'sky-top': t.skyTop,
    'sky-bottom': t.skyBottom,
    sheet: t.sheet,
    'cloud-puff': t.cloudPuff,
    card: t.card,
    'card-border': t.cardBorder,
    tint: t.tint,
    'tint-strong': t.tintStrong,
    shadow: t.shadow,
    ink: t.ink,
    'ink-muted': t.inkMuted,
    'nav-bar': t.navBar,
    'nav-idle': t.navIdle,
  };
  const vars: Record<string, string> = {};
  for (const [name, hex] of Object.entries(colours)) vars[`--c-${name}`] = triplet(hex);
  vars['--shadow-a'] = dark ? '0.35' : '0.08';
  return vars;
}

/** Installs palette `t` app-wide. With `animate`, colours cross-fade for a
 *  moment (mobile's AnimatedTheme) instead of snapping. */
export function applyTheme(t: PersonaTheme, animate = false) {
  const root = document.documentElement;
  if (animate) {
    root.classList.add('theme-anim');
    window.clearTimeout(Number(root.dataset.themeAnim));
    root.dataset.themeAnim = String(window.setTimeout(() => root.classList.remove('theme-anim'), 450));
  }
  for (const [k, v] of Object.entries(themeVars(t))) root.style.setProperty(k, v);
  root.style.colorScheme = t.brightness;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t.skyTop);
}
