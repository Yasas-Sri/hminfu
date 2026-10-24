import type { Config } from 'tailwindcss';

// Loaded via `@config` in src/index.css (Tailwind v4). Design tokens from docs/DESIGN.md §2 land in M4.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
} satisfies Config;
