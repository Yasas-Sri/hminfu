import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import type { MetaResponse } from './api/client';
import { App } from './App';

afterEach(() => vi.unstubAllGlobals());

const META: MetaResponse = {
  supported_target_range: { from: '2026-01-02T00:00:00Z', to: '2026-02-02T00:00:00Z' },
  default_window: { from: '2026-01-02T00:00:00Z', to: '2026-02-02T00:00:00Z' },
  defaults: { cutoff_local: '09:50', publish_lag_minutes: 0, aggregation: 'point' },
  data_as_of: '2026-10-24T11:42:08Z',
  publications_per_day: { min: 8, median: 8, max: 8 },
  sign_convention: 'error = forecast − actual (MW)',
};

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

test('the assumption sentence reads the defaults from /meta', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith('/api/v1/meta') ? Response.json(META) : new Response(null, { status: 500 }),
      ),
    ),
  );
  renderApp();
  expect(await screen.findByRole('button', { name: '2 Jan – 1 Feb 2026' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '09:50' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'as soon as published' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'the actual half-hour on the hour' })).toBeTruthy();
  expect(screen.getByText(/fetched 24 Oct 2026/)).toBeTruthy();
});

test('a failed /meta shows the cause and a retry', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })));
  renderApp();
  expect(await screen.findByText(/server returned 500/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
});
