import type { components } from './schema';

export type HealthResponse = components['schemas']['HealthResponse'];

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`server returned ${res.status}`);
  return (await res.json()) as T;
}

export const getHealth = () => getJson<HealthResponse>('/api/v1/health');
