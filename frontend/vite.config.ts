import { defineConfig } from 'vitest/config';

// ATPM_UI_PORT must match the port the backend allowlists; ATPM_API_PORT is where uvicorn listens.
const uiPort = Number(process.env.ATPM_UI_PORT || 5173);
const apiPort = Number(process.env.ATPM_API_PORT || 8010);

export default defineConfig({
  // strictPort: falling back to another port would silently break the backend origin check.
  server: {port: uiPort, strictPort: true, proxy: {'/api': `http://127.0.0.1:${apiPort}`}},
  preview: {port: uiPort, strictPort: true},
  test: {environment: 'jsdom', globals: true, setupFiles: ['./src/setupTests.ts'], include: ['src/**/*.test.tsx']},
});
