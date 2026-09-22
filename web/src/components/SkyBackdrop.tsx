/**
 * Full-viewport weather backdrop for a page that has called `useSky`: the
 * gradient plus one ambient layer (sun, moon and stars, drifting clouds,
 * rain, a storm flash). Which layers show is decided in CSS from the
 * `data-sky` attribute on <html>, so the markup is the same for every sky
 * — see src/theme/sky.css. Purely decorative: hidden from assistive tech,
 * lets pointer events through, sits behind everything.
 */
export function SkyBackdrop() {
  return (
    <div aria-hidden className="sky-backdrop">
      <div className="sky-layer sky-stars" />
      <div className="sky-layer sky-sun" />
      <div className="sky-layer sky-moon" />
      <div className="sky-layer sky-clouds">
        <span />
        <span />
        <span />
      </div>
      <div className="sky-layer sky-rain" />
      <div className="sky-layer sky-flash" />
    </div>
  );
}
