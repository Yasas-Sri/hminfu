import { useCallback, useSyncExternalStore } from 'react';

// View state lives in the URL so any view can be shared as a link (AGENTS.md §7).
// Absent keys mean "server default" (from GET /meta), so a plain link stays short.

export type Tab = 'explorer' | 'accuracy';
export type Aggregation = 'point' | 'hourly_mean';

export interface UrlState {
  from?: string;
  to?: string;
  cutoff?: string;
  lag?: number;
  agg?: Aggregation;
  tab: Tab;
}

const EVENT = 'urlstatechange';

function subscribe(onChange: () => void) {
  window.addEventListener('popstate', onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener('popstate', onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

export function parseUrlState(search: string): UrlState {
  const q = new URLSearchParams(search);
  const lag = q.get('lag');
  const agg = q.get('agg');
  return {
    from: q.get('from') ?? undefined,
    to: q.get('to') ?? undefined,
    cutoff: q.get('cutoff') ?? undefined,
    lag: lag !== null && /^\d+$/.test(lag) ? Number(lag) : undefined,
    agg: agg === 'point' || agg === 'hourly_mean' ? agg : undefined,
    tab: q.get('tab') === 'accuracy' ? 'accuracy' : 'explorer',
  };
}

export function serializeUrlState(s: UrlState): string {
  const q = new URLSearchParams();
  for (const key of ['from', 'to', 'cutoff', 'lag', 'agg'] as const) {
    const v = s[key];
    if (v !== undefined) q.set(key, String(v));
  }
  if (s.tab !== 'explorer') q.set('tab', s.tab);
  const out = q.toString();
  return out ? `?${out}` : '';
}

/** [state, update]. `update` merges a patch; `undefined` values remove a key (back to default). */
export function useUrlState(): [UrlState, (patch: Partial<UrlState>) => void] {
  const search = useSyncExternalStore(subscribe, () => window.location.search);
  const state = parseUrlState(search);
  const update = useCallback((patch: Partial<UrlState>) => {
    const next = { ...parseUrlState(window.location.search), ...patch };
    window.history.replaceState(null, '', `${window.location.pathname}${serializeUrlState(next)}`);
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [state, update];
}
