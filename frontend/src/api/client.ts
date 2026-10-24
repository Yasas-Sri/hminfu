import type { components } from './schema';

type Schemas = components['schemas'];
export type MetaResponse = Schemas['MetaResponse'];
export type SeriesResponse = Schemas['SeriesResponse'];
export type SeriesPoint = Schemas['SeriesPoint'];
export type MetricsResponse = Schemas['MetricsResponse'];
export type ByHourResponse = Schemas['ByHourResponse'];
export type ByHorizonResponse = Schemas['ByHorizonResponse'];
export type ByForecastLevelResponse = Schemas['ByForecastLevelResponse'];

/** Query params shared by the analytical endpoints; undefined = server default. */
export interface AnalysisParams {
  from?: string;
  to?: string;
  cutoff?: string;
  lag_minutes?: number;
  aggregation?: 'point' | 'hourly_mean';
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

interface ValidationBody {
  detail?: { msg?: string }[] | string;
}

async function getJson<T>(path: string, params: object = {}): Promise<T> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
  const url = q.size ? `${path}?${q}` : path;
  const res = await fetch(url);
  if (!res.ok) {
    // 422s carry a human-readable message; show it as-is (DESIGN.md §5).
    const body = (await res.json().catch(() => ({}))) as ValidationBody;
    const msg = Array.isArray(body.detail) ? body.detail[0]?.msg : undefined;
    throw new ApiError(res.status, msg ?? `server returned ${res.status}`);
  }
  return (await res.json()) as T;
}

const API = '/api/v1';
export const getMeta = () => getJson<MetaResponse>(`${API}/meta`);
export const getSeries = (p: AnalysisParams) => getJson<SeriesResponse>(`${API}/series`, p);
export const getMetrics = (p: AnalysisParams) => getJson<MetricsResponse>(`${API}/metrics`, p);
export const getByHour = (p: AnalysisParams) =>
  getJson<ByHourResponse>(`${API}/metrics/by-hour`, p);
export const getByHorizon = (p: AnalysisParams) =>
  getJson<ByHorizonResponse>(`${API}/metrics/by-horizon`, p);
export const getByForecastLevel = (p: AnalysisParams) =>
  getJson<ByForecastLevelResponse>(`${API}/metrics/by-forecast-level`, p);
