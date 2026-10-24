import type { SeriesPoint } from '../../api/client';
import { errorLabel } from '../../lib/errorLabel';
import {
  formatHoursAhead,
  formatMW,
  formatSignedMW,
  formatUkDateTime,
  formatUkShort,
} from '../../lib/format';

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="grid grid-cols-[9rem_7rem_1fr] items-baseline gap-x-4 max-sm:grid-cols-[8rem_1fr]">
      <dt className="text-ui text-ink-soft">{label}</dt>
      <dd className="m-0 text-right text-ui font-semibold">{value}</dd>
      {note && <dd className="m-0 text-ui text-ink-soft max-sm:col-span-2">{note}</dd>}
    </div>
  );
}

export function SelectedHour({ point }: { point: SeriesPoint }) {
  const f = point.forecast_mw;
  const a = point.actual_mw;
  const e = point.error_mw;
  const made =
    point.forecast_publish_time && point.horizon_hours !== null
      ? `made ${formatUkShort(point.forecast_publish_time)}, ${formatHoursAhead(point.horizon_hours)}`
      : undefined;
  return (
    <section
      aria-labelledby="selected-hour"
      aria-live="polite"
      className="border-t border-rule pt-6"
    >
      <h2 id="selected-hour" className="m-0 text-section">
        Selected hour
      </h2>
      <p className="mb-3 mt-0 text-body">{formatUkDateTime(point.target_time)}</p>
      <dl className="m-0 flex flex-col gap-2">
        <Row
          label="Forecast at cutoff"
          value={f === null ? 'No forecast before cutoff' : formatMW(f)}
          note={made}
        />
        <Row label="Actual" value={a === null ? 'No actual recorded' : formatMW(a)} />
        {e !== null && <Row label="Error" value={formatSignedMW(e)} note={errorLabel(e)} />}
      </dl>
    </section>
  );
}
