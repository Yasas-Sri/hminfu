// ECharts styling from docs/DESIGN.md §4. Charts use only these tokens.
import { formatMW } from './format';

export const C = {
  overcast: '#E6EAEA',
  sheet: '#F7F8F6',
  ink: '#1B2830',
  inkSoft: '#4A5961',
  rule: '#C5CDCE',
  forecast: '#13707B',
  over: '#93560C',
  under: '#5B4E9E',
  hindsight: '#8E999C',
} as const;

/** Colour at 22% opacity, for error fills (DESIGN.md §2). */
export const fill22 = (hex: string) => `${hex}38`;

const FONT = '"Public Sans Variable", "IBM Plex Sans", system-ui, sans-serif';

export const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Nothing animates on load; the one motion moment is a 400 ms update (DESIGN.md §6). */
export const motion = () => ({
  animation: !reducedMotion(),
  animationDuration: 0,
  animationDurationUpdate: reducedMotion() ? 0 : 400,
  animationEasingUpdate: 'cubicOut' as const,
});

export const textStyle = { fontFamily: FONT, color: C.inkSoft, fontSize: 12 };

export const axisLabel = { ...textStyle, fontSize: 12, color: C.inkSoft };

/** y axis in MW: unit once above the axis, thousands separators, gridlines in `rule`. */
export const mwAxis = (startAtZero = true) => ({
  type: 'value' as const,
  name: 'MW',
  nameLocation: 'end' as const,
  nameTextStyle: { ...axisLabel, align: 'right' as const, padding: [0, 6, 0, 0] },
  min: startAtZero ? 0 : undefined,
  axisLabel: { ...axisLabel, formatter: (v: number) => formatMW(v).replace(' MW', '') },
  splitLine: { lineStyle: { color: C.rule, width: 1 } },
  axisLine: { show: false },
  axisTick: { show: false },
});

export const tooltipStyle = {
  backgroundColor: C.sheet,
  borderColor: C.rule,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { fontFamily: FONT, color: C.ink, fontSize: 14 },
  extraCssText:
    'border-radius:4px; box-shadow:0 2px 8px rgb(27 40 48 / 0.12); font-variant-numeric:tabular-nums;',
};

let hatch: HTMLCanvasElement | undefined;
/** The hatch texture as an ECharts pattern fill; same geometry as the CSS `.hatch`. */
export function hatchPattern(): { image: HTMLCanvasElement; repeat: 'repeat' } | string {
  if (!hatch) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 6;
    const ctx = canvas.getContext('2d');
    if (!ctx) return 'transparent'; // no canvas (tests)
    ctx.strokeStyle = C.hindsight;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, 6);
    ctx.lineTo(6, 0);
    ctx.stroke();
    hatch = canvas;
  }
  return { image: hatch, repeat: 'repeat' };
}
