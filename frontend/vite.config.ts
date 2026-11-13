/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Read VITE_* vars from the repo-root .env (one env file for backend + frontend,
  // same as backend/app/config.py). src/lib/api.ts has a default, so no .env is needed.
  envDir: '..',
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    // Also reset vi.mock()ed module fns: restoreMocks clears call counts but
    // keeps queued mockResolvedValueOnce values, which leak between tests.
    mockReset: true,
    unstubGlobals: true,
  },
})
