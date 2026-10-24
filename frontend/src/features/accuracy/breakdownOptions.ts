import type { ByForecastLevelResponse, ByHorizonResponse, ByHourResponse } from '../../api/client';
import { C, axisLabel, motion, mwAxis, tooltipStyle } from '../../lib/chartTheme';
import type { EChartsOption } from '../../lib/echarts';
import { errorLabel } from '../../lib/errorLabel';
import { formatMW, formatSignedMW } from '../../lib/format';

const grid = { left: 56, right: 16, top: 28, bottom: 40 };
const categoryAxis = (data: string[], name: string) => ({
  type: 'category' as const,
  data,
  name,
  nameLocation: 'middle' as const,
  nameGap: 26,
  nameTextStyle: axisLabel,
  axisLabel,
  axisLine: { lineStyle: { color: C.rule } },
  axisTick: { show: false },
});
const signColour = (v: number) => (v >= 0 ? C.over : C.under);
const tip = (title: string, mae: number | null, bias: number | null) =>
  `<div style="margin-bottom:4px">${title}</div>` +
  (mae === null || bias === null
    ? 'No hours'
    : `Typical miss <b>${formatMW(mae)}</b><br/>Average error <b>${formatSignedMW(bias)}</b><br/>${errorLabel(bias)} on average`);

export function byHourOption(d: ByHourResponse): EChartsOption {
  const hours = d.rows.map((r) => String(r.hour_local).padStart(2, '0'));
  return {
    ...motion(),
    grid,
    xAxis: categoryAxis(hours, 'Hour of day (UK)'),
    yAxis: mwAxis(false),
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      formatter: (p: unknown) => {
        const r = d.rows[(p as { dataIndex: number }[])[0]?.dataIndex ?? 0];
        return r
          ? tip(`${String(r.hour_local).padStart(2, '0')}:00 UK, ${r.n} hours`, r.mae_mw, r.bias_mw)
          : '';
      },
    },
    series: [
      {
        type: 'bar',
        name: 'Typical miss',
        data: d.rows.map((r) => r.mae_mw),
        itemStyle: { color: C.inkSoft, opacity: 0.4 },
        barWidth: '60%',
      },
      {
        type: 'scatter',
        name: 'Bias',
        symbol: 'rect',
        symbolSize: [14, 3],
        data: d.rows.map((r) =>
          r.bias_mw === null
            ? null
            : { value: r.bias_mw, itemStyle: { color: signColour(r.bias_mw) } },
        ),
      },
    ],
  };
}

export function byHorizonOption(
  d: ByHorizonResponse,
  decisionRange: [number, number] | null,
): EChartsOption {
  return {
    ...motion(),
    grid,
    xAxis: {
      type: 'value',
      name: 'Hours ahead',
      nameLocation: 'middle',
      nameGap: 26,
      nameTextStyle: axisLabel,
      axisLabel,
      min: 0,
      splitLine: { show: false },
      axisLine: { lineStyle: { color: C.rule } },
    },
    yAxis: mwAxis(),
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      formatter: (p: unknown) => {
        const r = d.rows[(p as { dataIndex: number }[])[0]?.dataIndex ?? 0];
        return r
          ? tip(
              `${r.horizon_from_h}–${r.horizon_to_h} hours ahead, ${r.n} forecasts`,
              r.mae_mw,
              r.bias_mw,
            )
          : '';
      },
    },
    series: [
      {
        type: 'line',
        name: 'Typical miss',
        data: d.rows.map((r) => [(r.horizon_from_h + r.horizon_to_h) / 2, r.mae_mw]),
        lineStyle: { color: C.forecast, width: 2 },
        itemStyle: { color: C.forecast },
        symbolSize: 6,
        markArea: decisionRange
          ? {
              silent: true,
              itemStyle: { color: C.rule, opacity: 0.35 },
              label: {
                show: true,
                position: 'insideBottom',
                ...axisLabel,
                formatter: 'Forecasts used for decisions sit in this range',
              },
              data: [[{ xAxis: decisionRange[0] }, { xAxis: decisionRange[1] }]],
            }
          : undefined,
      },
    ],
  };
}

export function byLevelOption(d: ByForecastLevelResponse): EChartsOption {
  const labels = d.rows.map((r) => `${r.level_from_mw / 1000}–${r.level_to_mw / 1000} GW`);
  return {
    ...motion(),
    grid,
    xAxis: categoryAxis(labels, 'Forecast at cutoff'),
    yAxis: mwAxis(false),
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      formatter: (p: unknown) => {
        const r = d.rows[(p as { dataIndex: number }[])[0]?.dataIndex ?? 0];
        return r
          ? tip(`Forecast ${labels[d.rows.indexOf(r)]}, ${r.n} hours`, r.mae_mw, r.bias_mw)
          : '';
      },
    },
    series: [
      {
        type: 'bar',
        name: 'Bias',
        data: d.rows.map((r) => ({
          value: r.bias_mw,
          itemStyle: { color: signColour(r.bias_mw) },
        })),
        barWidth: '45%',
      },
      {
        type: 'line',
        name: 'Typical miss',
        data: d.rows.map((r) => r.mae_mw),
        lineStyle: { color: C.ink, width: 1.5 },
        itemStyle: { color: C.ink },
        symbolSize: 6,
      },
    ],
  };
}
