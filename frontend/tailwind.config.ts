import type { Config } from 'tailwindcss';

// Tokens from docs/DESIGN.md §2. Colours, radii and type sizes REPLACE Tailwind's defaults, so a stray
// `bg-blue-500` or `rounded-lg` simply doesn't exist. Loaded via `@config` in src/index.css (Tailwind v4).
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      overcast: '#E6EAEA',
      sheet: '#F7F8F6',
      ink: { DEFAULT: '#1B2830', soft: '#4A5961' },
      rule: '#C5CDCE',
      forecast: '#13707B',
      over: '#93560C',
      under: '#5B4E9E',
      hindsight: '#8E999C',
    },
    fontFamily: { sans: ['"Public Sans Variable"', '"IBM Plex Sans"', 'system-ui', 'sans-serif'] },
    borderRadius: { none: '0', input: '4px', sheet: '6px', chip: '999px' },
    boxShadow: {},
    fontSize: {
      figure: ['36px', { lineHeight: '40px', fontWeight: '600' }],
      title: ['21px', { lineHeight: '28px', fontWeight: '600' }],
      section: ['16px', { lineHeight: '24px', fontWeight: '600' }],
      body: ['16px', { lineHeight: '24px' }],
      ui: ['14px', { lineHeight: '20px' }],
      small: ['12px', { lineHeight: '16px' }],
    },
    fontWeight: { normal: '400', medium: '500', semibold: '600' },
  },
} satisfies Config;
