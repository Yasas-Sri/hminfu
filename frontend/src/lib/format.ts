// Number and time formatting per DESIGN.md §7: comma thousands, a space before units, true minus
// signs (U+2212), explicit + on positives, 24-hour UK times.
import { ukDate } from './ukTime';

export const MINUS = '−';
const whole = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const oneDp = new Intl.NumberFormat('en-GB', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function sign(v: number, plus: boolean): string {
  if (Math.round(v) < 0) return MINUS;
  return plus && Math.round(v) > 0 ? '+' : '';
}

/** "1,696 MW"; negatives keep a true minus. */
export const formatMW = (v: number) => `${sign(v, false)}${whole.format(Math.abs(v))} MW`;

/** "+168 MW" / "−1,696 MW" / "0 MW". */
export const formatSignedMW = (v: number) => `${sign(v, true)}${whole.format(Math.abs(v))} MW`;

/** Narrative only: "1.7 GW". */
export const formatGW = (v: number) => `${oneDp.format(v / 1000)} GW`;

/** Raw API ratio → "84%". */
export const formatPct = (ratio: number) => `${Math.round(ratio * 100)}%`;

export const formatHoursAhead = (h: number) =>
  `${Number.isInteger(h) ? h : oneDp.format(h)} hours ahead`;

const dayMonthYear = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/London',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});
const dayMonth = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/London',
  day: 'numeric',
  month: 'short',
});
const hhmm = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/London',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

/** "10 Jan 2026, 16:00 UK". */
export const formatUkDateTime = (iso: string) =>
  `${dayMonthYear.format(Date.parse(iso))}, ${hhmm.format(Date.parse(iso))} UK`;

/** "9 Jan 09:30" (UK). */
export const formatUkShort = (iso: string) =>
  `${dayMonth.format(Date.parse(iso))} ${hhmm.format(Date.parse(iso))}`;

/** Delivery days covered by [from, to): "2 Jan – 1 Feb 2026". `to` is exclusive. */
export function formatDeliveryRange(from: string, to: string): string {
  const last = new Date(Date.parse(to) - 3600_000).toISOString();
  const [a, b] = [Date.parse(`${ukDate(from)}T12:00Z`), Date.parse(`${ukDate(last)}T12:00Z`)];
  const sameYear = new Date(a).getUTCFullYear() === new Date(b).getUTCFullYear();
  const start = sameYear ? dayMonth.format(a) : dayMonthYear.format(a);
  return a === b ? dayMonthYear.format(b) : `${start} – ${dayMonthYear.format(b)}`;
}
