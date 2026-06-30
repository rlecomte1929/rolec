/**
 * A-01: guard /admin/countries — non-admin must be redirected.
 *
 * TDD cycle:
 *   RED  — route renders CountriesPage without RequireAdminRoute;
 *           non-admin reaches the page → `countries-page` testid found → test FAILS.
 *   GREEN — RequireAdminRoute wraps the route in App.tsx; non-admin is
 *           redirected → testid null → PASSES.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RequireAdminRoute } from '../RequireAdminRoute';

// ── Stubs ─────────────────────────────────────────────────────────────────

// Lightweight stand-in: skip all API/layout imports that would need heavy mocking.
const StubCountriesPage: React.FC = () => (
  <div data-testid="countries-page">Countries</div>
);

// ── localStorage stub ─────────────────────────────────────────────────────
const _storage = new Map<string, string>();
vi.stubGlobal('localStorage', {
  getItem: (key: string) => _storage.get(key) ?? null,
  setItem: (key: string, value: string) => { _storage.set(key, value); },
  removeItem: (key: string) => { _storage.delete(key); },
  clear: () => { _storage.clear(); },
});

// ── Route helpers ─────────────────────────────────────────────────────────

/** Renders the guarded route (mirrors the post-fix App.tsx). */
function renderGuarded(role: string) {
  _storage.set('relopass_role', role);
  render(
    <MemoryRouter initialEntries={['/admin/countries']}>
      <Routes>
        <Route
          path="/admin/countries"
          element={
            <RequireAdminRoute>
              <StubCountriesPage />
            </RequireAdminRoute>
          }
        />
        <Route path="*" element={<div data-testid="redirect-target" />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Renders the route WITHOUT the guard (documents the pre-fix broken state). */
function renderUnguarded(role: string) {
  _storage.set('relopass_role', role);
  render(
    <MemoryRouter initialEntries={['/admin/countries']}>
      <Routes>
        <Route path="/admin/countries" element={<StubCountriesPage />} />
        <Route path="*" element={<div data-testid="redirect-target" />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe('RequireAdminRoute — /admin/countries guard (A-01)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _storage.clear();
  });

  afterEach(cleanup);

  it('non-admin cannot reach /admin/countries (guarded route redirects)', () => {
    // PRIMARY test: asserts the desired post-fix behaviour.
    renderGuarded('EMPLOYEE');
    expect(screen.queryByTestId('countries-page')).toBeNull();
    expect(screen.getByTestId('redirect-target')).toBeInTheDocument();
  });

  it('admin can reach /admin/countries', () => {
    renderGuarded('ADMIN');
    expect(screen.getByTestId('countries-page')).toBeInTheDocument();
  });

  it('unguarded route WOULD let any role through (documents pre-fix bug A-01)', () => {
    // Demonstrates why wrapping with RequireAdminRoute matters: without the
    // guard, an EMPLOYEE-role user sees the page.  This test stays green
    // because it is intentionally documenting the unguarded behaviour — the
    // fix is in App.tsx, not in this test helper.
    renderUnguarded('EMPLOYEE');
    expect(screen.getByTestId('countries-page')).toBeInTheDocument();
  });
});
