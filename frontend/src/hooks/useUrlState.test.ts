import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, test } from 'vitest';
import { parseUrlState, serializeUrlState, useUrlState } from './useUrlState';

afterEach(() => window.history.replaceState(null, '', '/'));

test('parse ignores invalid values and defaults the tab', () => {
  expect(parseUrlState('?lag=abc&agg=mean&tab=nope')).toEqual({
    from: undefined,
    to: undefined,
    cutoff: undefined,
    lag: undefined,
    agg: undefined,
    tab: 'explorer',
  });
  expect(parseUrlState('?lag=0&agg=hourly_mean&tab=accuracy').lag).toBe(0); // 0 is a value
});

test('serialize round-trips and omits defaults', () => {
  const s = {
    from: '2026-01-10T00:00:00Z',
    lag: 60,
    agg: 'hourly_mean' as const,
    tab: 'accuracy' as const,
  };
  expect(parseUrlState(serializeUrlState(s))).toMatchObject(s);
  expect(serializeUrlState({ tab: 'explorer' })).toBe('');
});

test('update merges into the URL, and undefined removes a key', () => {
  const { result } = renderHook(() => useUrlState());
  act(() => result.current[1]({ cutoff: '08:00', tab: 'accuracy' }));
  expect(window.location.search).toBe('?cutoff=08%3A00&tab=accuracy');
  expect(result.current[0].cutoff).toBe('08:00');
  act(() => result.current[1]({ cutoff: undefined }));
  expect(result.current[0]).toMatchObject({ cutoff: undefined, tab: 'accuracy' });
});
