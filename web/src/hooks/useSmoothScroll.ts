import { useEffect } from 'react';
import Lenis from 'lenis';

/**
 * Smooth scroll for the whole page.
 *
 * Lenis still drives the real window scroll position, so framer-motion's
 * `useScroll` picks up scroll-linked effects without any extra wiring.
 *
 * Touch is deliberately left on the browser's native scrolling — syncing it
 * through Lenis feels heavy on mid-range Android, this app's main audience.
 */
export function useSmoothScroll(enabled = true): void {
  useEffect(() => {
    if (!enabled) return;

    const lenis = new Lenis({
      duration: 1.1,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
    });

    let frame = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(frame);
      lenis.destroy();
    };
  }, [enabled]);
}
