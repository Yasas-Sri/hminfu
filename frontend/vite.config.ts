/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    // Docker sets API_PROXY_TARGET=http://api:8000; locally the API runs on :8000.
    proxy: { '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000' },
  },
  // globals: true lets Testing Library register its automatic DOM cleanup after each test.
  test: { environment: 'jsdom', globals: true },
});
