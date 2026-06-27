/**
 * AIQ-760 — RequireHrRoute guard.
 *
 * Verifies /hr/* routes are gated: ADMIN + HR pass through, EMPLOYEE is
 * redirected (unless allowEmployee), and unauthenticated users land on /.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { RequireHrRoute } from '../RequireHrRoute';

const getAuthItem = vi.fn();
vi.mock('../../../utils/demo', () => ({
  getAuthItem: (key: string): unknown => getAuthItem(key),
}));

function renderGuarded(allowEmployee = false) {
  return render(
    <MemoryRouter initialEntries={['/hr/employees']}>
      <Routes>
        <Route
          path="/hr/employees"
          element={
            <RequireHrRoute allowEmployee={allowEmployee}>
              <div>HR CONTENT</div>
            </RequireHrRoute>
          }
        />
        <Route path="/" element={<div>LANDING</div>} />
        <Route path="/employee/dashboard" element={<div>EMPLOYEE HOME</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RequireHrRoute', () => {
  beforeEach(() => {
    getAuthItem.mockReset();
  });

  it('renders children for ADMIN', () => {
    getAuthItem.mockReturnValue('ADMIN');
    renderGuarded();
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('renders children for HR', () => {
    getAuthItem.mockReturnValue('HR');
    renderGuarded();
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('redirects EMPLOYEE to their dashboard', () => {
    getAuthItem.mockReturnValue('EMPLOYEE');
    renderGuarded();
    expect(screen.queryByText('HR CONTENT')).not.toBeInTheDocument();
    expect(screen.getByText('EMPLOYEE HOME')).toBeInTheDocument();
  });

  it('allows EMPLOYEE through when allowEmployee is set', () => {
    getAuthItem.mockReturnValue('EMPLOYEE');
    renderGuarded(true);
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('redirects unauthenticated users to landing', () => {
    getAuthItem.mockReturnValue(null);
    renderGuarded();
    expect(screen.queryByText('HR CONTENT')).not.toBeInTheDocument();
    expect(screen.getByText('LANDING')).toBeInTheDocument();
  });
});
