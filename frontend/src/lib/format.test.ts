import { expect, test } from 'vitest';
import { errorLabel } from './errorLabel';
import {
  MINUS,
  formatDeliveryRange,
  formatGW,
  formatHoursAhead,
  formatMW,
  formatPct,
  formatSignedMW,
  formatUkDateTime,
  formatUkShort,
} from './format';
import { nextDate, ukDate, ukMidnightIso } from './ukTime';

test('MW uses comma thousands, a space before the unit and a true minus', () => {
  expect(formatMW(8222)).toBe('8,222 MW');
  expect(formatMW(0)).toBe('0 MW');
  expect(formatMW(-1696)).toBe(`${MINUS}1,696 MW`);
  expect(formatSignedMW(168)).toBe('+168 MW');
  expect(formatSignedMW(-1696)).toBe('−1,696 MW');
  expect(formatSignedMW(0.2)).toBe('0 MW'); // rounds to zero: no sign
  expect(formatGW(1696)).toBe('1.7 GW');
  expect(formatPct(0.8427)).toBe('84%');
  expect(formatHoursAhead(30.5)).toBe('30.5 hours ahead');
});

test('times are UK local, 24-hour', () => {
  expect(formatUkDateTime('2026-01-10T16:00:00Z')).toBe('10 Jan 2026, 16:00 UK');
  expect(formatUkShort('2026-01-09T09:30:00Z')).toBe('9 Jan 09:30');
  expect(formatUkDateTime('2026-06-01T12:00:00Z')).toBe('1 Jun 2026, 13:00 UK'); // BST
});

test('delivery range treats `to` as exclusive', () => {
  expect(formatDeliveryRange('2026-01-02T00:00:00Z', '2026-02-02T00:00:00Z')).toBe(
    '2 Jan – 1 Feb 2026',
  );
  expect(formatDeliveryRange('2026-01-10T00:00:00Z', '2026-01-11T00:00:00Z')).toBe('10 Jan 2026');
  expect(formatDeliveryRange('2025-12-30T00:00:00Z', '2026-01-03T00:00:00Z')).toBe(
    '30 Dec 2025 – 2 Jan 2026',
  );
});

test('UK dates and midnights respect BST', () => {
  expect(ukMidnightIso('2026-01-10')).toBe('2026-01-10T00:00:00Z');
  expect(ukMidnightIso('2026-06-01')).toBe('2026-05-31T23:00:00Z');
  expect(ukDate('2026-05-31T23:30:00Z')).toBe('2026-06-01');
  expect(nextDate('2026-01-31')).toBe('2026-02-01');
});

test('error labels say the direction in words', () => {
  expect(errorLabel(-1696)).toBe('Under-forecast: 1,696 MW more wind than forecast');
  expect(errorLabel(168)).toBe('Over-forecast: 168 MW less wind than forecast');
  expect(errorLabel(0)).toBe('Exact: no difference');
});
