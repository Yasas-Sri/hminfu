import { formatMW } from './format';

/** Plain-English meaning of a signed error (forecast − actual), always shown beside the sign. */
export function errorLabel(errorMw: number): string {
  const size = formatMW(Math.abs(errorMw));
  if (Math.round(errorMw) > 0) return `Over-forecast: ${size} less wind than forecast`;
  if (Math.round(errorMw) < 0) return `Under-forecast: ${size} more wind than forecast`;
  return 'Exact: no difference';
}
