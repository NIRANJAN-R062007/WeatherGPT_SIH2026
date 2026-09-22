// The paper/ink/line/monsoon roles are CSS variables (R G B triplets, defined
// on :root in src/index.css and re-pointed per weather in src/theme/sky.css)
// so a page can re-theme the whole shell without touching any component.
// Everything the sky must never recolour — the IMD warning colours and the
// turmeric "fixture" accent — stays literal.
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: token('paper'),
          dim: token('paper-dim'),
          hi: token('paper-hi'),
        },
        ink: {
          DEFAULT: token('ink'),
          dim: token('ink-dim'),
          faint: token('ink-faint'),
        },
        line: {
          DEFAULT: token('line'),
          dim: token('line-dim'),
        },
        monsoon: {
          DEFAULT: token('monsoon'),
          dim: token('monsoon-dim'),
          tint: token('monsoon-tint'),
        },
        turmeric: {
          DEFAULT: '#B5690F',
          // Pale by default; a dark sky swaps it for a deep amber so the
          // fixture badge's ink-coloured text stays readable.
          tint: token('turmeric-tint'),
        },
        'imd-green': {
          DEFAULT: '#1E7F3C',
          tint: '#DCF2E2',
        },
        'imd-yellow': {
          DEFAULT: '#C99A00',
          tint: '#FFF1BF',
        },
        'imd-orange': {
          DEFAULT: '#D96A0B',
          tint: '#FFE0C2',
        },
        'imd-red': {
          DEFAULT: '#B3261E',
          tint: '#F9D8D5',
        },
      },
      fontFamily: {
        sans: ['var(--font-ui)'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
