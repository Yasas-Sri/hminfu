import type { MetricsResponse } from '../../api/client';
import { formatMW, formatSignedMW } from '../../lib/format';

interface Row {
  figure: string;
  label: string;
  note: string;
}

export function ledgerRows(m: MetricsResponse): Row[] {
  const cov = m.meta.coverage;
  const rows: Row[] = [];
  if (m.mae_mw !== null)
    rows.push({
      figure: formatMW(m.mae_mw),
      label: 'Typical miss',
      note: 'Mean absolute error. Half the story: see the spread below.',
    });
  if (m.bias_mw !== null)
    rows.push({
      figure: formatSignedMW(m.bias_mw),
      label: 'Average error (bias)',
      note: `${Math.round(m.bias_mw) > 0 ? 'Positive: forecasts ran high.' : Math.round(m.bias_mw) < 0 ? 'Negative: forecasts ran low.' : 'Close to zero: no consistent direction.'} A persistent bias may be correctable, but only after checking it on other months.`,
    });
  if (m.p90_over_forecast_mw !== null)
    rows.push({
      figure: formatMW(m.p90_over_forecast_mw),
      label: 'Historical P90 over-forecast',
      note: 'In 9 of 10 hours in this sample, wind came in no more than this far below the forecast. A starting point for cover, not a guarantee.',
    });
  if (cov)
    rows.push({
      figure: `${cov.ok}/${cov.target_hours}`,
      label: 'Hours with both a forecast and an actual',
      note: '',
    });
  return rows;
}

/** The figures as a ledger, not a card grid (DESIGN.md §3.3, §9). Valid <dl>: each group is dt then dd(s). */
export function Ledger({ metrics }: { metrics: MetricsResponse }) {
  return (
    <dl className="m-0 flex flex-col gap-4">
      {ledgerRows(metrics).map((r) => (
        <div
          key={r.label}
          className="grid grid-cols-[180px_1fr] content-start gap-x-6 max-lg:grid-cols-[140px_1fr] max-sm:grid-cols-1"
        >
          <dt className="col-start-2 row-start-1 self-end text-section max-sm:col-start-1 max-sm:row-start-2">
            {r.label}
          </dt>
          <dd className="col-start-1 row-span-2 row-start-1 m-0 whitespace-nowrap text-right text-figure max-sm:row-span-1 max-sm:text-left">
            {r.figure.replace(/ MW$/, '')}
            {r.figure.endsWith(' MW') && <span className="text-section"> MW</span>}
          </dd>
          {r.note && (
            <dd className="col-start-2 row-start-2 m-0 max-w-[68ch] text-body text-ink-soft max-sm:col-start-1 max-sm:row-start-3">
              {r.note}
            </dd>
          )}
        </div>
      ))}
    </dl>
  );
}
