import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    passWithNoTests: true,
    // TEST-2: load jest-dom matchers once for every test (was imported ad-hoc
    // in ~69/128 files and relied on transitive load in the rest).
    setupFiles: ['./src/test/setup.ts'],
    // QG-6 (AIQ-1179): coverage ratchet. Thresholds sit just below the current
    // floor (measured 2026-06-26: ~16% lines/statements, 67% branches, 32%
    // functions over src/**) so CI FAILS if coverage regresses, without forcing
    // a big test-writing push now. Raise these as suites are added. Enforced in
    // CI via `npm run test:coverage`.
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      reporter: ['text-summary'],
      thresholds: {
        statements: 15,
        branches: 60,
        functions: 28,
        lines: 15,
      },
    },
  },
  resolve: {
    dedupe: ['react', 'react-dom', 'react-router-dom'],
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'supabase-vendor': ['@supabase/supabase-js'],
          'axios-vendor': ['axios'],
        },
      },
    },
  },
  server: {
    port: 3000,
    allowedHosts: ['relopass.relopass.com'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
