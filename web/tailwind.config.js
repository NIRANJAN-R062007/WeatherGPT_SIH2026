/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: '#F3F5F2',
          dim: '#E8ECE8',
          hi: '#FFFFFF',
        },
        ink: {
          DEFAULT: '#14202B',
          dim: '#4A5866',
          faint: '#7C8A97',
        },
        line: {
          DEFAULT: '#D3DAD6',
          dim: '#B9C3BE',
        },
        monsoon: {
          DEFAULT: '#0F5C7A',
          dim: '#0B4459',
          tint: '#D6E9F0',
        },
        turmeric: {
          DEFAULT: '#B5690F',
          tint: '#F6E7CF',
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
