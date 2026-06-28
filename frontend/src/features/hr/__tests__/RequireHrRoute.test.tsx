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

const getStoredRoles = vi.fn<() => string[]>();
const getActiveRole = vi.fn<() => string>();
vi.mock('../../../utils/demo', () => ({
  getStoredRoles: (): string[] => getStoredRoles(),
  getActiveRole: (): string => getActiveRole(),
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
    getStoredRoles.mockReset();
    getActiveRole.mockReset();
    getActiveRole.mockReturnValue('');
  });

  it('renders children for ADMIN', () => {
    getStoredRoles.mockReturnValue(['ADMIN']);
    renderGuarded();
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('renders children for HR', () => {
    getStoredRoles.mockReturnValue(['HR']);
    renderGuarded();
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('redirects single-role EMPLOYEE to their dashboard (B15/B20)', () => {
    getStoredRoles.mockReturnValue(['EMPLOYEE']);
    getActiveRole.mockReturnValue('EMPLOYEE');
    renderGuarded();
    expect(screen.queryByText('HR CONTENT')).not.toBeInTheDocument();
    expect(screen.getByText('EMPLOYEE HOME')).toBeInTheDocument();
  });

  it('allows EMPLOYEE through when allowEmployee is set', () => {
    getStoredRoles.mockReturnValue(['EMPLOYEE']);
    renderGuarded(true);
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('allows a dual HR+EMPLOYEE user even when active role is EMPLOYEE', () => {
    getStoredRoles.mockReturnValue(['EMPLOYEE', 'HR']);
    getActiveRole.mockReturnValue('EMPLOYEE');
    renderGuarded();
    expect(screen.getByText('HR CONTENT')).toBeInTheDocument();
  });

  it('redirects unauthenticated users to landing', () => {
    getStoredRoles.mockReturnValue([]);
    getActiveRole.mockReturnValue('');
    renderGuarded();
    expect(screen.queryByText('HR CONTENT')).not.toBeInTheDocument();
    expect(screen.getByText('LANDING')).toBeInTheDocument();
  });
});
