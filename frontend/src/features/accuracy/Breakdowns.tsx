import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ChartFrame } from '../../components/ChartFrame';
import { ErrorNotice } from '../../components/States';
import {
  toParams,
  useByForecastLevel,
  useByHorizon,
  useByHour,
  useSeries,
} from '../../hooks/queries';
import type { UrlState } from '../../hooks/useUrlState';
import { ReactEChartsCore, echarts } from '../../lib/echarts';
import { formatMW, formatSignedMW } from '../../lib/format';
import { byHorizonOption, byHourOption, byLevelOption } from './breakdownOptions';

const mw = (v: number | null) => (v === null ? 'No hours' : formatMW(v));
const signed = (v: number | null) => (v === null ? 'No hours' : formatSignedMW(v));
const chart = (option: object) => (
  <ReactEChartsCore echarts={echarts} option={option} style={{ height: 280 }} />
);

function Panel({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col gap-2">
      <h3 className="m-0 text-section">{title}</h3>
      {caption && <div className="m-0 max-w-[68ch] text-ui text-ink-soft">{caption}</div>}
      {children}
    </section>
  );
}

/** Loading, error and "previous data, dimmed" states for one breakdown (DESIGN.md §5). */
function Loaded<T>({ q, children }: { q: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  if (q.isError) return <ErrorNotice message={q.error.message} onRetry={() => void q.refetch()} />;
  if (!q.data) return <p className="m-0 text-ui text-ink-soft">Loading January data</p>;
  return <div className={q.isPlaceholderData ? 'opacity-60' : ''}>{children(q.data)}</div>;
}

export function Breakdowns({ state }: { state: UrlState }) {
  const p = toParams(state);
  const hour = useByHour(p);
  const horizon = useByHorizon(p);
  const level = useByForecastLevel(p);
  const series = useSeries(p); // shared cache with the Explorer; gives the decision horizon range
  const hs = (series.data?.points ?? []).flatMap((x) =>
    x.horizon_hours === null ? [] : [x.horizon_hours],
  );
  const range: [number, number] | null = hs.length ? [Math.min(...hs), Math.max(...hs)] : null;

  return (
    <div className="grid grid-cols-1 gap-8 min-[960px]:grid-cols-2">
      <Panel
        title="Error by hour of day (UK)"
        caption="Bars: typical miss. Ticks: average error, brown for over-forecast, purple for under-forecast."
      >
        <Loaded q={hour}>
          {(d) => (
            <ChartFrame
              label="Typical miss and average error by UK hour of day"
              table={{
                head: ['Hour (UK)', 'Hours', 'Typical miss', 'Average error'],
                rows: d.rows.map((r) => [
                  `${String(r.hour_local).padStart(2, '0')}:00`,
                  r.n,
                  mw(r.mae_mw),
                  signed(r.bias_mw),
                ]),
              }}
            >
              {chart(byHourOption(d))}
            </ChartFrame>
          )}
        </Loaded>
      </Panel>
      <Panel
        title="Error by forecast age"
        caption={
          horizon.data?.meta.cutoff_applied === false
            ? 'Uses every forecast published for these hours, not only the forecast at cutoff.'
            : undefined
        }
      >
        <Loaded q={horizon}>
          {(d) => (
            <ChartFrame
              label="Typical miss by hours ahead"
              table={{
                head: ['Hours ahead', 'Forecasts', 'Typical miss', 'Average error'],
                rows: d.rows.map((r) => [
                  `${r.horizon_from_h}–${r.horizon_to_h}`,
                  r.n,
                  mw(r.mae_mw),
                  signed(r.bias_mw),
                ]),
              }}
            >
              {chart(byHorizonOption(d, range))}
            </ChartFrame>
          )}
        </Loaded>
      </Panel>
      <Panel
        title="Error by forecast level"
        caption={
          <>
            <p className="m-0">
              Larger forecasts missed by more, and almost always on the high side. Why isn&apos;t
              established from these two datasets alone.
            </p>
            <p className="m-0 mt-1">
              Bars: average error, brown for over-forecast, purple for under-forecast. Line: typical
              miss.
            </p>
          </>
        }
      >
        <Loaded q={level}>
          {(d) => (
            <ChartFrame
              label="Average error and typical miss by forecast level"
              table={{
                head: ['Forecast at cutoff', 'Hours', 'Typical miss', 'Average error'],
                rows: d.rows.map((r) => [
                  `${r.level_from_mw / 1000}–${r.level_to_mw / 1000} GW`,
                  r.n,
                  mw(r.mae_mw),
                  signed(r.bias_mw),
                ]),
              }}
            >
              {chart(byLevelOption(d))}
            </ChartFrame>
          )}
        </Loaded>
      </Panel>
    </div>
  );
}
