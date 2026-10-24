import type { MetricsResponse } from '../../api/client';
import { formatMW, formatPct } from '../../lib/format';

const count = new Intl.NumberFormat('en-GB');

/** Opening sentence of the Accuracy view (DESIGN.md §7 template). Null when there is nothing to say. */
export function summarySentence(m: MetricsResponse): string | null {
  if (m.n === 0 || m.mae_mw === null || m.bias_mw === null) return null;
  const meanActual = m.nmae !== null && m.nmae > 0 ? m.mae_mw / m.nmae : null; // nmae = mae / mean(actual)
  const flat = meanActual !== null && Math.abs(m.bias_mw) < 0.02 * meanActual;
  const direction = flat
    ? 'and showed no consistent direction.'
    : m.bias_mw > 0
      ? 'and ran high on average: less wind arrived than forecast.'
      : 'and ran low on average: more wind arrived than forecast.';
  return `Across ${count.format(m.n)} hours, the forecast at cutoff missed by ${formatMW(m.mae_mw)} in a typical hour, ${direction}`;
}

/** Bias-direction note (DESIGN.md §7). States the share, never a cause. */
export function biasNote(m: MetricsResponse): string | null {
  if (m.over_forecast_share === null) return null;
  return `In this sample the forecast was above the reported actual in ${formatPct(m.over_forecast_share)} of hours. Why isn't established from these two datasets alone.`;
}
