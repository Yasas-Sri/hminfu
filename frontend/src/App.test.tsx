import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { App } from './App';

afterEach(() => vi.unstubAllGlobals());

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

test('shows the API health status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ status: 'ok' })));
  renderApp();
  expect(await screen.findByText('API status: ok')).toBeTruthy();
  expect(fetch).toHaveBeenCalledWith('/api/v1/health');
});

test('shows the cause when the API fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })));
  renderApp();
  expect(await screen.findByText(/server returned 500/)).toBeTruthy();
});
