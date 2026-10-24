import { expect, test } from 'vitest';
import type { SeriesPoint, SeriesResponse } from '../../api/client';
import { actualLine, largestErrorHour, missingRuns } from './explorerOption';

const point = (h: number, status: SeriesPoint['status'], error: number | null): SeriesPoint => ({
  target_time: `2026-01-10T${String(h).padStart(2, '0')}:00:00Z`,
  status,
  actual_mw: status === 'ok' || status === 'missing_forecast' ? 100 : null,
  forecast_mw: status === 'ok' || status === 'missing_actual' ? 100 + (error ?? 0) : null,
  forecast_publish_time: null,
  horizon_hours: null,
  error_mw: error,
});

test('default selection is the largest absolute error; 0 is a real value, null is skipped', () => {
  expect(
    largestErrorHour([
      point(0, 'ok', 0),
      point(1, 'ok', -900),
      point(2, 'ok', 800),
      point(3, 'missing_actual', null),
    ]),
  ).toBe('2026-01-10T01:00:00Z');
  expect(largestErrorHour([point(0, 'ok', 0)])).toBe('2026-01-10T00:00:00Z');
  expect(largestErrorHour([point(0, 'missing_both', null)])).toBeNull();
});

test('missing hours merge into contiguous bands', () => {
  const runs = missingRuns([
    point(0, 'ok', 1),
    point(1, 'missing_actual', null),
    point(2, 'missing_both', null),
    point(3, 'ok', 1),
  ]);
  expect(runs).toEqual([[Date.parse('2026-01-10T01:00:00Z'), Date.parse('2026-01-10T03:00:00Z')]]);
});

test('a missing actual half-hour breaks the actual line instead of being bridged', () => {
  const data = {
    meta: { from: '2026-01-10T00:00:00Z', to: '2026-01-10T02:00:00Z' },
    actuals_halfhourly: [
      { start_time: '2026-01-10T00:00:00Z', actual_mw: 0 },
      { start_time: '2026-01-10T00:30:00Z', actual_mw: 10 },
      { start_time: '2026-01-10T01:30:00Z', actual_mw: 30 }, // 01:00 missing
    ],
  } as unknown as SeriesResponse;
  expect(actualLine(data).map(([, v]) => v)).toEqual([0, 10, null, 30]);
});
