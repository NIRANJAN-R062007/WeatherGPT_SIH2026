import type { ReactElement } from 'react';

type Ratio = '3/1' | '4/3' | '1/1';
type Glyph = 'skyline' | 'cloud' | 'sun' | 'rain' | 'thunder' | 'wind' | 'flag';

interface Props {
  ratio: Ratio;
  glyph: Glyph;
  label: string;
  className?: string;
}

const RATIO_CLASSES: Record<Ratio, string> = {
  '3/1': 'aspect-[3/1]',
  '4/3': 'aspect-[4/3]',
  '1/1': 'aspect-square',
};

// Stroke-only line glyphs, no fill, no colour beyond ink-faint — decorative
// placeholders that don't pretend to be real photography or icons.
const GLYPHS: Record<Glyph, ReactElement> = {
  skyline: (
    <svg viewBox="0 0 64 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 28h56M8 28V14h6v14M18 28V8h8v20M30 28V16h7v12M41 28V10h6v18M51 28V18h9v10" strokeLinejoin="round" />
    </svg>
  ),
  cloud: (
    <svg viewBox="0 0 32 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 22a5 5 0 0 1 .3-9.98A7 7 0 0 1 23 13a4.5 4.5 0 0 1-1 9H9Z" strokeLinejoin="round" />
    </svg>
  ),
  sun: (
    <svg viewBox="0 0 32 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="16" cy="16" r="6" />
      <path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.5 6.5l2.8 2.8M22.7 22.7l2.8 2.8M6.5 25.5l2.8-2.8M22.7 9.3l2.8-2.8" strokeLinecap="round" />
    </svg>
  ),
  rain: (
    <svg viewBox="0 0 32 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 18a5 5 0 0 1 .3-9.98A7 7 0 0 1 23 9a4.5 4.5 0 0 1-1 9H9Z" strokeLinejoin="round" />
      <path d="M11 23l-1.5 3M17 23l-1.5 3M23 23l-1.5 3" strokeLinecap="round" />
    </svg>
  ),
  thunder: (
    <svg viewBox="0 0 32 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 16a5 5 0 0 1 .3-9.98A7 7 0 0 1 23 7a4.5 4.5 0 0 1-1 9H9Z" strokeLinejoin="round" />
      <path d="M17 18l-4 7h4l-3 6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  ),
  wind: (
    <svg viewBox="0 0 32 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 12h17a3.5 3.5 0 1 0-3-5.3M4 18h21a3.5 3.5 0 1 1-3 5.3M4 24h13" strokeLinecap="round" />
    </svg>
  ),
  flag: (
    <svg viewBox="0 0 32 32" className="h-1/2 w-1/2" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 28V5" strokeLinecap="round" />
      <path d="M9 6h16l-4 5 4 5H9" strokeLinejoin="round" />
    </svg>
  ),
};

/** Decorative image slot for where a real photo/illustration would go. */
export function Placeholder({ ratio, glyph, label, className = '' }: Props) {
  return (
    <div
      role="img"
      aria-label={label}
      className={`grid place-items-center rounded-sm border border-line bg-paper-dim text-ink-faint ${RATIO_CLASSES[ratio]} ${className}`}
    >
      {GLYPHS[glyph]}
    </div>
  );
}
