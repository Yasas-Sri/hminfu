import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  type AnalysisParams,
  getByForecastLevel,
  getByHorizon,
  getByHour,
  getMeta,
  getMetrics,
  getSeries,
} from '../api/client';
import type { UrlState } from './useUrlState';

export const toParams = (s: UrlState): AnalysisParams => ({
  from: s.from,
  to: s.to,
  cutoff: s.cutoff,
  lag_minutes: s.lag,
  aggregation: s.agg,
});

// The data is a fixed snapshot: never refetch on focus, keep old data visible while new data loads.
const analysis = <T>(name: string, fn: (p: AnalysisParams) => Promise<T>, p: AnalysisParams) => ({
  queryKey: [name, p],
  queryFn: () => fn(p),
  placeholderData: keepPreviousData,
  staleTime: Infinity,
});

export const useMeta = () =>
  useQuery({ queryKey: ['meta'], queryFn: getMeta, staleTime: Infinity });
export const useSeries = (p: AnalysisParams) => useQuery(analysis('series', getSeries, p));
export const useMetrics = (p: AnalysisParams) => useQuery(analysis('metrics', getMetrics, p));
export const useByHour = (p: AnalysisParams) => useQuery(analysis('by-hour', getByHour, p));
export const useByHorizon = (p: AnalysisParams) =>
  useQuery(analysis('by-horizon', getByHorizon, p));
export const useByForecastLevel = (p: AnalysisParams) =>
  useQuery(analysis('by-forecast-level', getByForecastLevel, p));
