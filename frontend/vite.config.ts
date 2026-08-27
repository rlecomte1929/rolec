import { execFileSync } from 'node:child_process'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Build SHA exposed to the app as __APP_VERSION__ (used by the feedback diagnostics
// snapshot). Render sets RENDER_GIT_COMMIT at build; fall back to the local git SHA.
// execFileSync with an argument array (no shell) — command is a static literal anyway.
function appVersion(): string {
  const fromRender = process.env.RENDER_GIT_COMMIT
  if (fromRender) return fromRender.slice(0, 7)
  try {
    return (
      execFileSync('git', ['rev-parse', '--short', 'HEAD'], { stdio: ['ignore', 'pipe', 'ignore'] })
        .toString()
        .trim() || 'dev'
    )
  } catch {
    return 'dev'
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion()),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    // eslint-rules/ is included so the custom lint rules have real automated
    // coverage. no-low-contrast-text auto-fixes ~890 sites in one sweep, so its
    // fixer has to be verified, not eyeballed against a fixture.
    include: ['src/**/*.test.{ts,tsx}', 'eslint-rules/**/*.test.{ts,tsx}'],
    passWithNoTests: true,
    // TEST-2: load jest-dom matchers once for every test (was imported ad-hoc
    // in ~69/128 files and relied on transitive load in the rest).
    setupFiles: ['./src/test/setup.ts'],
    // Dummy Supabase creds so the singleton client (createClient in api/supabase.ts
    // and lib/supabase.ts) never throws "supabaseUrl is required" during tests. CI
    // has no VITE_SUPABASE_* env, so config/env.ts falls back to '' and any lazily
    // evaluated supabase module — e.g. the fire-and-forget dynamic import()s in
    // NotificationsBell / RelocationTimeline / policy-builder — would reject with
    // that error. The rejection floats and vitest mis-attributes it to whatever
    // test file is active, producing an intermittent, unrelated red (it flaked the
    // AIQ-1535 PR on BudgetSummaryTable). Fake non-empty values let createClient
    // construct without connecting; no test asserts against a real Supabase.
    env: {
      VITE_SUPABASE_URL: 'http://localhost:54321',
      VITE_SUPABASE_ANON_KEY: 'test-anon-key-not-a-real-secret',
    },
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
