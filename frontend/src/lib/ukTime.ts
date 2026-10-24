// All UI times are shown in UK time (DESIGN.md §7). The API speaks UTC.

const LONDON = 'Europe/London';
const partsFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON,
  hourCycle: 'h23',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});

function londonParts(t: number) {
  const p = Object.fromEntries(partsFmt.formatToParts(t).map((x) => [x.type, x.value]));
  return {
    y: Number(p.year),
    m: Number(p.month),
    d: Number(p.day),
    h: Number(p.hour),
    min: Number(p.minute),
  };
}

/** Minutes London is ahead of UTC at instant t (0 in GMT, 60 in BST). */
function londonOffsetMinutes(t: number): number {
  const p = londonParts(t);
  return (Date.UTC(p.y, p.m - 1, p.d, p.h, p.min) - Math.floor(t / 60000) * 60000) / 60000;
}

/** UK calendar date ("2026-01-10") of an ISO instant. */
export function ukDate(iso: string): string {
  const p = londonParts(Date.parse(iso));
  return `${p.y}-${String(p.m).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`;
}

/** UTC ISO instant of UK midnight starting `date` ("2026-01-10"). */
export function ukMidnightIso(date: string): string {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  const guess = Date.UTC(y, m - 1, d);
  const t = guess - londonOffsetMinutes(guess) * 60000;
  return new Date(t).toISOString().replace('.000Z', 'Z');
}

/** Next calendar day of "2026-01-31" → "2026-02-01" (pure date maths, no time zone). */
export function nextDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  return new Date(Date.UTC(y, m - 1, d + 1)).toISOString().slice(0, 10);
}

export function ukHourOfDay(iso: string): number {
  return londonParts(Date.parse(iso)).h;
}
