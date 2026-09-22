import { useEffect } from 'react';
import type { SkyKey } from './sky';
import './sky.css';

const THEME_COLOR_DEFAULT = '#F3F5F2'; // index.html's <meta name="theme-color">

function themeColorMeta(): HTMLMetaElement | null {
  return document.querySelector('meta[name="theme-color"]');
}

function apply(sky: SkyKey | null): void {
  const root = document.documentElement;
  if (sky) root.dataset.sky = sky;
  else delete root.dataset.sky;

  // Android Chrome paints the status bar in theme-color; keep it in step
  // with the top of the gradient so a night sky doesn't sit under a pale bar.
  const meta = themeColorMeta();
  if (!meta) return;
  const top = sky ? getComputedStyle(root).getPropertyValue('--sky-top').trim() : '';
  meta.content = top ? `rgb(${top})` : THEME_COLOR_DEFAULT;
}

/**
 * Paints the page in `sky` for as long as the calling page is mounted: sets
 * `data-sky` on <html> (which sky.css turns into colours) and clears it on
 * unmount so the other routes stay on plain paper. A change of sky crossfades
 * through the View Transitions API when the browser has it and the viewer
 * hasn't asked for reduced motion; otherwise it snaps.
 */
export function useSky(sky: SkyKey | null): void {
  useEffect(() => {
    const root = document.documentElement;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const changed = (root.dataset.sky ?? null) !== sky;

    if (changed && !reduceMotion && typeof document.startViewTransition === 'function') {
      document.startViewTransition(() => apply(sky));
    } else {
      apply(sky);
    }
  }, [sky]);

  useEffect(() => () => apply(null), []);
}
