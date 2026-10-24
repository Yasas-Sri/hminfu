import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import type { MetricsResponse } from '../../api/client';
import { Ledger, ledgerRows } from './Ledger';
import { biasNote, summarySentence } from './summary';

const metrics = (over: Partial<MetricsResponse> = {}): MetricsResponse => ({
  meta: {
    from: '2026-01-02T00:00:00Z',
    to: '2026-02-02T00:00:00Z',
    cutoff_local: '09:50',
    cutoff_timezone: 'Europe/London',
    publish_lag_minutes: 0,
    aggregation: 'point',
    cutoff_applied: true,
    data_as_of: '2026-10-24T11:42:08Z',
    coverage: {
      target_hours: 744,
      ok: 744,
      missing_actual: 0,
      missing_forecast: 0,
      missing_both: 0,
    },
  },
  n: 744,
  mae_mw: 1995.6,
  rmse_mw: 2498.8,
  bias_mw: 1728,
  nmae: 0.177,
  error_quantiles_mw: { p10: -500, p50: 1500, p90: 4183.9 },
  p90_over_forecast_mw: 4183.9,
  over_forecast_share: 0.8427,
  largest_over_forecast: null,
  largest_under_forecast: null,
  ...over,
});

test('summary sentence flips with the sign of the bias', () => {
  expect(summarySentence(metrics())).toBe(
    'Across 744 hours, the forecast at cutoff missed by 1,996 MW in a typical hour, and ran high on average: less wind arrived than forecast.',
  );
  expect(summarySentence(metrics({ bias_mw: -956 }))).toMatch(
    /ran low on average: more wind arrived than forecast\.$/,
  );
  // |bias| < 2% of mean actual (mean actual = mae / nmae ≈ 11,275 MW)
  expect(summarySentence(metrics({ bias_mw: 100 }))).toMatch(
    /and showed no consistent direction\.$/,
  );
  expect(summarySentence(metrics({ n: 0, mae_mw: null, bias_mw: null }))).toBeNull();
});

test('bias note states the share, never a cause', () => {
  expect(biasNote(metrics())).toBe(
    "In this sample the forecast was above the reported actual in 84% of hours. Why isn't established from these two datasets alone.",
  );
  expect(biasNote(metrics({ over_forecast_share: null }))).toBeNull();
});

test('ledger rows: figures with units, signs and the P90 caveat', () => {
  const rows = ledgerRows(metrics());
  expect(rows.map((r) => [r.figure, r.label])).toEqual([
    ['1,996 MW', 'Typical miss'],
    ['+1,728 MW', 'Average error (bias)'],
    ['4,184 MW', 'Historical P90 over-forecast'],
    ['744/744', 'Hours with both a forecast and an actual'],
  ]);
  expect(rows[1]?.note).toMatch(/^Positive: forecasts ran high\./);
  expect(rows[2]?.note).toMatch(/not a guarantee/);
});

test('ledger renders as a definition list, not cards', () => {
  render(<Ledger metrics={metrics({ bias_mw: -956 })} />);
  const figures = [...document.querySelectorAll('dd')].map((d) => d.textContent);
  expect(figures).toContain('−956 MW'); // unit on the same line as the figure
  expect(screen.getByText(/Negative: forecasts ran low/)).toBeTruthy();
  expect(document.querySelector('dl')).not.toBeNull();
});
