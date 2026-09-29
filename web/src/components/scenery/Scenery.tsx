// The active persona's painted scene in each place it appears (mobile
// scenery.dart's PersonaScenery): the page header band, the sheet's foot (a
// full landscape or its quieter "soft" form), Home's illustration panel and
// a persona card's vignette. Canvases are layered exactly like mobile's
// Stack of Positioned painters.
import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { useUiPrefs } from '../../state/UiPrefsContext';
import { alpha, SUN, SUN_CORE, type PersonaTheme } from '../../theme/personaTheme';
import { Icon } from '../ui';
import {
  airport,
  birds,
  capitol,
  civic,
  clouds,
  farmhouse,
  fields,
  leaves,
  lighthouse,
  rain,
  skyline,
  trawler,
  waves,
  type Painter,
} from './painters';

export type SceneSlot = 'header' | 'footer' | 'soft' | 'panel' | 'card';

/** A canvas filling its box, redrawn at device resolution whenever the box
 *  resizes or the painter changes. */
export function PaintCanvas({ paint }: { paint: Painter }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const paintRef = useRef(paint);

  useEffect(() => {
    paintRef.current = paint;
    const canvas = ref.current;
    if (!canvas) return;
    const draw = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w === 0 || h === 0) return;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      paintRef.current(ctx, w, h);
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [paint]);

  return <canvas ref={ref} className="block w-full h-full" aria-hidden="true" />;
}

type Box = { left?: number; right?: number; top?: number; bottom?: number; width?: number; height?: number };

/** A painter at a fixed spot (mobile's `_at`). */
function At({ paint, ...box }: Box & { paint: Painter }) {
  return (
    <div className="absolute" style={box}>
      <PaintCanvas paint={paint} />
    </div>
  );
}

/** A painter across the bottom (mobile's `_band`). */
function Band({ height, paint }: { height: number; paint: Painter }) {
  return (
    <div className="absolute inset-x-0 bottom-0" style={{ height }}>
      <PaintCanvas paint={paint} />
    </div>
  );
}

function Fill({ paint }: { paint: Painter }) {
  return (
    <div className="absolute inset-0">
      <PaintCanvas paint={paint} />
    </div>
  );
}

function Place({ children, ...box }: Box & { children: ReactNode }) {
  return (
    <div className="absolute leading-none" style={box}>
      {children}
    </div>
  );
}

/** The sun by day; a crescent moon on dark palettes. */
function Sun({ t, size = 24 }: { t: PersonaTheme; size?: number }) {
  if (t.brightness === 'dark') {
    return <Icon name="nightlight" fill size={size} style={{ color: t.moonGlyph }} />;
  }
  return (
    <span
      className="block rounded-full"
      style={{
        width: size,
        height: size,
        background: SUN_CORE,
        boxShadow: `0 0 ${size * 0.7}px 2px ${alpha(SUN, 0.45)}`,
      }}
    />
  );
}

/** A jet climbing to the upper right, trailing a pink contrail. */
function Jet({ t, size = 30 }: { t: PersonaTheme; size?: number }) {
  return (
    <span className="relative block" style={{ width: size * 2.2, height: size }}>
      <span
        className="absolute left-0 rounded-sm"
        style={{
          bottom: size * 0.3,
          width: size * 1.35,
          height: 2.2,
          transformOrigin: 'right center',
          transform: 'rotate(-0.32rad)',
          background: `linear-gradient(to right, ${alpha(t.accent2, 0)}, ${alpha(t.accent2, 0.7)})`,
        }}
      />
      <span className="absolute right-0 top-0" style={{ transform: `rotate(${Math.PI / 2.6}rad)` }}>
        <Icon name="flight" fill size={size} style={{ color: t.primary }} />
      </span>
    </span>
  );
}

function Tractor({ t, size = 30 }: { t: PersonaTheme; size?: number }) {
  return <Icon name="agriculture" fill size={size} style={{ color: t.primaryContainer }} />;
}

function header(t: PersonaTheme) {
  const puffs = <Fill paint={clouds(t.cloudPuff)} />;
  const dark = t.brightness === 'dark';
  const gulls = alpha(t.ink, dark ? 0.5 : 0.4);
  switch (t.scene) {
    case 'city':
      return (
        <>
          {puffs}
          {dark && (
            <Place right={26} top={40}>
              <Sun t={t} size={22} />
            </Place>
          )}
          <Band height={86} paint={skyline(t, { seed: 11 })} />
        </>
      );
    case 'civic':
      return (
        <>
          {puffs}
          {dark && (
            <Place left={26} top={44}>
              <Sun t={t} size={20} />
            </Place>
          )}
          <Band height={80} paint={skyline(t, { seed: 29 })} />
          <At paint={capitol(t)} right={14} bottom={8} width={96} height={74} />
        </>
      );
    case 'fields':
      return (
        <>
          {puffs}
          <Place right={34} top={40}>
            <Sun t={t} />
          </Place>
          <Band height={70} paint={fields(t)} />
          <At paint={farmhouse(t)} left={120} bottom={34} width={26} height={20} />
          <Place right={58} bottom={6}>
            <Tractor t={t} />
          </Place>
          <At paint={leaves(t)} left={-6} bottom={-4} width={70} height={74} />
          <At paint={leaves(t, { mirror: true })} right={-6} bottom={-4} width={56} height={62} />
        </>
      );
    case 'sea':
      return (
        <>
          {puffs}
          {dark && (
            <Place left={30} top={42}>
              <Sun t={t} size={20} />
            </Place>
          )}
          <At paint={birds(gulls)} left={14} top={46} width={56} height={22} />
          <At paint={birds(gulls)} right={20} top={2} width={60} height={24} />
          <Band height={58} paint={waves(t, { islands: true, foam: true })} />
          <At paint={trawler(t)} right={30} bottom={2} width={62} height={60} />
        </>
      );
    case 'airport':
      return (
        <>
          {puffs}
          {dark && (
            <Place left={26} top={44}>
              <Sun t={t} size={20} />
            </Place>
          )}
          <Place right={40} top={0}>
            <Jet t={t} size={36} />
          </Place>
          <Band height={70} paint={airport(t)} />
        </>
      );
  }
}

/** Home's illustration panel between the forecast and Quick Actions. */
function panel(t: PersonaTheme) {
  const puffs = <Fill paint={clouds(t.cloudPuff)} />;
  const gulls = alpha(t.ink, t.brightness === 'dark' ? 0.5 : 0.4);
  switch (t.scene) {
    case 'city':
      return (
        <>
          {puffs}
          <Place right={30} top={16}>
            <Sun t={t} size={22} />
          </Place>
          <Band height={118} paint={civic(t, { seed: 5 })} />
        </>
      );
    case 'civic':
      return (
        <>
          {puffs}
          <Place left={28} top={14}>
            <Sun t={t} size={20} />
          </Place>
          <Band height={90} paint={skyline(t, { seed: 41 })} />
          <At paint={capitol(t)} right={22} bottom={14} width={104} height={80} />
          <Band height={22} paint={waves(t)} />
        </>
      );
    case 'fields':
      return (
        <>
          {puffs}
          <Place right={70} top={12}>
            <Sun t={t} />
          </Place>
          <Band height={110} paint={fields(t)} />
          <At paint={farmhouse(t)} left={150} bottom={58} width={38} height={30} />
          <At paint={farmhouse(t)} left={206} bottom={62} width={28} height={22} />
          <At paint={leaves(t)} left={-8} bottom={-6} width={86} height={104} />
          <At paint={leaves(t, { mirror: true })} right={-8} bottom={-6} width={80} height={96} />
        </>
      );
    case 'sea':
      return (
        <>
          {puffs}
          <Place left={26} top={14}>
            <Sun t={t} size={20} />
          </Place>
          <At paint={birds(gulls)} left={150} top={18} width={70} height={26} />
          <Band height={88} paint={waves(t, { islands: true, foam: true })} />
          <At paint={lighthouse(t)} right={40} bottom={34} width={26} height={78} />
          <At paint={trawler(t)} left={120} bottom={4} width={70} height={66} />
          <Place left={36} bottom={26}>
            <Icon name="sailing" fill size={22} style={{ color: t.primaryContainer }} />
          </Place>
        </>
      );
    case 'airport':
      return (
        <>
          {puffs}
          <Place right={76} top={8}>
            <Jet t={t} size={40} />
          </Place>
          <Band height={96} paint={airport(t)} />
        </>
      );
  }
}

function card(t: PersonaTheme) {
  const gulls = alpha(t.ink, 0.45);
  switch (t.scene) {
    case 'city':
      return (
        <>
          <Place right={56} top={26}>
            <Sun t={t} size={22} />
          </Place>
          <Band height={70} paint={skyline(t, { seed: 5 })} />
        </>
      );
    case 'fields':
      return (
        <>
          <Place right={64} top={22}>
            <Sun t={t} size={20} />
          </Place>
          <Band height={72} paint={fields(t)} />
          <Place right={26} bottom={14}>
            <Tractor t={t} />
          </Place>
          <At paint={leaves(t, { mirror: true })} right={-6} bottom={-6} width={44} height={56} />
        </>
      );
    case 'sea':
      return (
        <>
          <At paint={birds(gulls)} left={30} top={18} width={60} height={22} />
          <Band height={60} paint={waves(t, { foam: true })} />
          <At paint={trawler(t)} right={26} bottom={6} width={54} height={54} />
        </>
      );
    case 'airport':
      return (
        <>
          <Band height={60} paint={airport(t)} />
          <Place right={46} top={30}>
            <Jet t={t} size={34} />
          </Place>
        </>
      );
    case 'civic':
      return (
        <>
          <At paint={rain(alpha(t.rainGlyph, 0.35))} right={0} top={6} width={120} height={40} />
          <Band height={80} paint={civic(t, { seed: 17 })} />
        </>
      );
  }
}

function footerPainter(t: PersonaTheme, soft: boolean): Painter {
  if (soft) return t.scene === 'fields' ? fields(t, { crops: false, opacity: 0.8 }) : waves(t, { opacity: 0.9 });
  switch (t.scene) {
    case 'city':
      return skyline(t, { seed: 23, opacity: 0.85 });
    case 'fields':
      return fields(t, { opacity: 0.9 });
    case 'sea':
      return waves(t, { opacity: 0.95, islands: true, foam: true });
    case 'airport':
      return airport(t, { opacity: 0.85 });
    case 'civic':
      return civic(t, { seed: 23, opacity: 0.85 });
  }
}

/** The active persona's scene for one slot; `theme` overrides the active
 *  persona (the persona cards each show their own). Decorative. */
export function PersonaScenery({ slot, theme, style }: { slot: SceneSlot; theme?: PersonaTheme; style?: CSSProperties }) {
  const active = useUiPrefs().theme;
  const t = theme ?? active;
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true" style={style}>
      {slot === 'header' && header(t)}
      {slot === 'panel' && panel(t)}
      {slot === 'card' && card(t)}
      {(slot === 'footer' || slot === 'soft') && <Fill paint={footerPainter(t, slot === 'soft')} />}
    </div>
  );
}
