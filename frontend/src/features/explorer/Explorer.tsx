import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import type { SeriesPoint } from '../../api/client';
import { ChartFrame } from '../../components/ChartFrame';
import { EmptyRange, ErrorNotice, ProgressBar } from '../../components/States';
import { toParams, useMetrics, useSeries } from '../../hooks/queries';
import { useMedia } from '../../hooks/useMedia';
import type { UrlState } from '../../hooks/useUrlState';
import { type echarts, ReactEChartsCore } from '../../lib/echarts';
import { echarts as ec } from '../../lib/echarts';
import { formatDeliveryRange, formatMW, formatSignedMW, formatUkDateTime } from '../../lib/format';
import { explorerOption, largestErrorHour } from './explorerOption';
import { Legend } from './Legend';
import { SelectedHour } from './SelectedHour';

const HOUR = 3600_000;

export function Explorer({ state, onReset }: { state: UrlState; onReset: () => void }) {
  const q = useSeries(toParams(state));
  const metrics = useMetrics(toParams(state)); // memoised server-side; only feeds the chart's aria-label
  const compact = useMedia('(max-width: 639px)');
  const [picked, setPicked] = useState<string | null>(null);
  const points = useMemo(() => q.data?.points ?? [], [q.data]);
  const index = useMemo(() => new Map(points.map((p, i) => [p.target_time, i])), [points]);
  const selected = picked !== null && index.has(picked) ? picked : largestErrorHour(points);
  const pointsRef = useRef<SeriesPoint[]>(points);
  useEffect(() => {
    pointsRef.current = points; // read by the chart's click handler
  }, [points]);

  const option = useMemo(
    () => (q.data ? explorerOption(q.data, selected, compact) : undefined),
    [q.data, selected, compact],
  );

  const onChartReady = (chart: echarts.ECharts) => {
    chart.getZr().on('click', (e: { offsetX: number; offsetY: number }) => {
      if (!chart.containPixel('grid', [e.offsetX, e.offsetY])) return; // ignore the overview strip
      const [x] = chart.convertFromPixel({ gridIndex: 0 }, [e.offsetX, e.offsetY]) as number[];
      if (x === undefined) return;
      const iso = new Date(Math.floor(x / HOUR) * HOUR).toISOString().replace('.000Z', 'Z');
      if (pointsRef.current.some((p) => p.target_time === iso)) setPicked(iso);
    });
  };

  const onKey = (e: KeyboardEvent) => {
    if (selected === null || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
    const i = (index.get(selected) ?? 0) + (e.key === 'ArrowRight' ? 1 : -1);
    const next = points[Math.max(0, Math.min(points.length - 1, i))];
    if (next) setPicked(next.target_time);
    e.preventDefault();
  };

  if (q.isError) return <ErrorNotice message={q.error.message} onRetry={() => void q.refetch()} />;
  const meta = q.data?.meta;
  const okCount = meta?.coverage?.ok ?? 0;
  const point = selected === null ? undefined : points[index.get(selected) ?? -1];
  const mae = metrics.data?.mae_mw;
  const label = meta
    ? `Forecast at cutoff vs actual, ${formatDeliveryRange(meta.from, meta.to)}${mae != null ? `, typical miss ${formatMW(mae)}` : ''}`
    : 'Forecast at cutoff vs actual, loading';

  return (
    <div className="flex flex-col gap-6">
      <ProgressBar active={q.isFetching} />
      <Legend />
      {meta && okCount === 0 && <EmptyRange onReset={onReset} />}
      <div className={q.isPlaceholderData ? 'opacity-60' : ''}>
        <ChartFrame
          label={label}
          table={{
            head: ['Hour (UK)', 'Forecast at cutoff', 'Actual', 'Error'],
            rows: points.map((p) => [
              formatUkDateTime(p.target_time),
              p.forecast_mw === null ? 'No forecast before cutoff' : formatMW(p.forecast_mw),
              p.actual_mw === null ? 'No actual recorded' : formatMW(p.actual_mw),
              p.error_mw === null ? 'No data' : formatSignedMW(p.error_mw),
            ]),
          }}
        >
          <div
            tabIndex={0}
            onKeyDown={onKey}
            aria-label="Chart. Left and right arrows move the selected hour."
            className="relative"
          >
            {option ? (
              <ReactEChartsCore
                echarts={ec}
                option={option}
                notMerge={false}
                lazyUpdate
                onChartReady={onChartReady}
                style={{ height: compact ? 300 : 440 }}
              />
            ) : (
              <div
                className="flex items-center justify-center border-b border-l border-rule text-ui text-ink-soft"
                style={{ height: compact ? 300 : 440 }}
              >
                Loading January data
              </div>
            )}
          </div>
        </ChartFrame>
      </div>
      {point && <SelectedHour point={point} />}
    </div>
  );
}
