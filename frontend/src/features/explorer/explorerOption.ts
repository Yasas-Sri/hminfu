import type { SeriesPoint, SeriesResponse } from '../../api/client';
import {
  C,
  axisLabel,
  fill22,
  hatchPattern,
  motion,
  mwAxis,
  tooltipStyle,
} from '../../lib/chartTheme';
import type { EChartsOption } from '../../lib/echarts';
import { errorLabel } from '../../lib/errorLabel';
import { formatMW, formatSignedMW, formatUkDateTime, formatUkShort } from '../../lib/format';
import { ukHourOfDay } from '../../lib/ukTime';

const HOUR = 3600_000;
const t = (iso: string) => Date.parse(iso);

/** Contiguous runs of hours without both values: drawn as hatched "No data" bands, never interpolated. */
export function missingRuns(points: SeriesPoint[]): [number, number][] {
  const runs: [number, number][] = [];
  for (const p of points) {
    if (p.status === 'ok') continue;
    const start = t(p.target_time);
    const last = runs[runs.length - 1];
    if (last && last[1] === start) last[1] = start + HOUR;
    else runs.push([start, start + HOUR]);
  }
  return runs;
}

/** Actual half-hours on an independent grid [from, to): absent rows become null, so the line breaks. */
export function actualLine(data: SeriesResponse): [number, number | null][] {
  const byTime = new Map(data.actuals_halfhourly.map((a) => [t(a.start_time), a.actual_mw]));
  const out: [number, number | null][] = [];
  for (let s = t(data.meta.from); s < t(data.meta.to); s += HOUR / 2)
    out.push([s, byTime.get(s) ?? null]);
  return out;
}

/** Hour with the largest absolute error, so the panel tells a story on load (DESIGN.md §3.2). */
export function largestErrorHour(points: SeriesPoint[]): string | null {
  let best: SeriesPoint | null = null;
  for (const p of points) {
    if (p.error_mw === null) continue;
    if (best === null || Math.abs(p.error_mw) > Math.abs(best.error_mw ?? 0)) best = p;
  }
  return best?.target_time ?? null;
}

function tooltipHtml(p: SeriesPoint | undefined): string {
  if (!p) return '';
  const row = (k: string, v: string, note = '') =>
    `<div style="display:flex;gap:12px"><span style="color:${C.inkSoft};min-width:120px">${k}</span><b style="font-weight:600">${v}</b><span style="color:${C.inkSoft}">${note}</span></div>`;
  const rows = [`<div style="margin-bottom:4px">${formatUkDateTime(p.target_time)}</div>`];
  rows.push(
    p.forecast_mw === null
      ? row('Forecast at cutoff', 'No forecast before cutoff')
      : row(
          'Forecast at cutoff',
          formatMW(p.forecast_mw),
          p.forecast_publish_time ? `made ${formatUkShort(p.forecast_publish_time)}` : '',
        ),
  );
  rows.push(row('Actual', p.actual_mw === null ? 'No actual recorded' : formatMW(p.actual_mw)));
  if (p.error_mw !== null)
    rows.push(row('Error', formatSignedMW(p.error_mw), errorLabel(p.error_mw)));
  return rows.join('');
}

export function explorerOption(
  data: SeriesResponse,
  selected: string | null,
  compact: boolean,
): EChartsOption {
  const points = data.points;
  const byHour = new Map(points.map((p) => [t(p.target_time), p]));
  const fill = (fn: (f: number, a: number) => number) =>
    points.map((p) => [
      t(p.target_time),
      p.status === 'ok' && p.forecast_mw !== null && p.actual_mw !== null
        ? fn(p.forecast_mw, p.actual_mw)
        : null,
    ]);
  const base = fill((f, a) => Math.min(f, a));
  const hidden = {
    type: 'line' as const,
    symbol: 'none',
    silent: true,
    lineStyle: { opacity: 0 },
    connectNulls: false,
  };
  return {
    ...motion(),
    // Ticks on UTC midnights = UK midnights in GMT (the January window); labels are formatted in UK time.
    useUTC: true,
    grid: { left: 56, right: 16, top: 28, bottom: compact ? 28 : 84 },
    xAxis: {
      type: 'time',
      axisLabel: {
        ...axisLabel,
        hideOverlap: true,
        formatter: (v: number) => {
          const iso = new Date(v).toISOString();
          return ukHourOfDay(iso) === 0
            ? formatUkShort(iso).split(' ').slice(0, 2).join(' ')
            : (formatUkShort(iso).split(' ')[2] ?? '');
        },
      },
      axisLine: { lineStyle: { color: C.rule } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: mwAxis(),
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: C.inkSoft, width: 1 } },
      formatter: (params: unknown) => {
        const first = (params as { axisValue: number }[])[0];
        return first ? tooltipHtml(byHour.get(Math.floor(first.axisValue / HOUR) * HOUR)) : '';
      },
    },
    dataZoom: compact
      ? [{ type: 'inside' }]
      : [
          { type: 'inside' },
          {
            type: 'slider',
            height: 48,
            bottom: 8,
            borderColor: C.rule,
            backgroundColor: 'transparent',
            fillerColor: fill22(C.rule),
            handleStyle: { color: C.forecast, borderColor: C.forecast },
            moveHandleStyle: { color: C.forecast },
            dataBackground: { lineStyle: { color: C.rule }, areaStyle: { color: C.rule } },
            textStyle: axisLabel,
            labelFormatter: (v: number) => formatUkShort(new Date(v).toISOString()),
          },
        ],
    series: [
      { ...hidden, name: 'base-over', stack: 'over', data: base },
      {
        ...hidden,
        name: 'Over-forecast',
        stack: 'over',
        data: fill((f, a) => Math.max(f - a, 0)),
        areaStyle: { color: fill22(C.over), opacity: 1 },
      },
      { ...hidden, name: 'base-under', stack: 'under', data: base },
      {
        ...hidden,
        name: 'Under-forecast',
        stack: 'under',
        data: fill((f, a) => Math.max(a - f, 0)),
        areaStyle: { color: fill22(C.under), opacity: 1 },
      },
      {
        type: 'line',
        name: 'Actual',
        data: actualLine(data),
        showSymbol: false,
        sampling: 'lttb',
        lineStyle: { color: C.ink, width: 1.5 },
        itemStyle: { color: C.ink },
        connectNulls: false,
      },
      {
        type: 'line',
        name: 'Forecast at cutoff',
        data: points.map((p) => [t(p.target_time), p.forecast_mw]),
        showSymbol: false,
        lineStyle: { color: C.forecast, width: 2 },
        itemStyle: { color: C.forecast },
        connectNulls: false,
        markArea: {
          silent: true,
          // ECharts accepts a pattern object here; its colour type only declares strings.
          itemStyle: { color: hatchPattern() as unknown as string, opacity: 0.5 },
          data: missingRuns(points).map(([a, b]) => [{ xAxis: a }, { xAxis: b }]),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: C.inkSoft, width: 1, type: 'solid' },
          data: selected ? [{ xAxis: t(selected) }] : [],
        },
      },
    ],
  };
}
