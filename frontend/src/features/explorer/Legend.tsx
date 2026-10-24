const item = 'flex items-center gap-2';

/** Above the chart, left-aligned (DESIGN.md §3.2). Colour is never the only cue: each entry is named. */
export function Legend() {
  return (
    <ul
      className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-ui text-ink"
      aria-label="Legend"
    >
      <li className={item}>
        <span className="inline-block h-[2px] w-5 bg-ink" aria-hidden /> Actual
      </li>
      <li className={item}>
        <span className="inline-block h-[2px] w-5 bg-forecast" aria-hidden /> Forecast at cutoff
      </li>
      <li className={item}>
        <span className="inline-block h-3 w-4 bg-over/22" aria-hidden /> Over-forecast
      </li>
      <li className={item}>
        <span className="inline-block h-3 w-4 bg-under/22" aria-hidden /> Under-forecast
      </li>
      <li className={item}>
        <span className="hatch inline-block h-3 w-4 opacity-50" aria-hidden /> No data
      </li>
    </ul>
  );
}
