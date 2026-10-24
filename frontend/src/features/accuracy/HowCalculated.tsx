/** Inline disclosure with the ANALYSIS.md definitions in plain language. */
export function HowCalculated() {
  return (
    <details className="text-body">
      <summary className="cursor-pointer text-ui text-forecast">How these are calculated</summary>
      <ul className="mt-2 max-w-[68ch] text-ink-soft">
        <li>
          Error for an hour = forecast at cutoff − actual, in MW. Positive is an over-forecast (less
          wind than forecast).
        </li>
        <li>
          Typical miss = the average size of the error, ignoring its sign (mean absolute error).
        </li>
        <li>Average error (bias) = the average of the signed errors.</li>
        <li>
          Historical P90 over-forecast = the error that 90% of hours in this sample stayed at or
          below (zero if most hours were under-forecasts).
        </li>
        <li>
          Only hours with both a forecast at cutoff and an actual are counted. Missing hours are
          shown, never filled in.
        </li>
        <li>These describe this sample only. They are not a guarantee for other periods.</li>
      </ul>
    </details>
  );
}
