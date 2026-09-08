/**
 * AIQ-1364 — RequireEmployeeRoute membership guard.
 *
 * B15/B20: a single-role HR user is still redirected out of /employee/*; a
 * dual HR+EMPLOYEE user can reach it. Decisions are by roles[] membership.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { RequireEmployeeRoute } from '../RequireEmployeeRoute';

const getStoredRoles = vi.fn<() => string[]>();
const getActiveRole = vi.fn<() => string>();
vi.mock('../../../utils/demo', () => ({
  getStoredRoles: (): string[] => getStoredRoles(),
  getActiveRole: (): string => getActiveRole(),
}));

function renderGuarded(allowHR = false) {
  return render(
    <MemoryRouter initialEntries={['/employee/dashboard']}>
      <Routes>
        <Route
          path="/employee/dashboard"
          element={
            <RequireEmployeeRoute allowHR={allowHR}>
              <div>EMPLOYEE CONTENT</div>
            </RequireEmployeeRoute>
          }
        />
        <Route path="/" element={<div>LANDING</div>} />
        <Route path="/hr/dashboard" element={<div>HR HOME</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RequireEmployeeRoute', () => {
  beforeEach(() => {
    getStoredRoles.mockReset();
    getActiveRole.mockReset();
    getActiveRole.mockReturnValue('');
  });

  it('allows single-role EMPLOYEE', () => {
    getStoredRoles.mockReturnValue(['EMPLOYEE']);
    renderGuarded();
    expect(screen.getByText('EMPLOYEE CONTENT')).toBeInTheDocument();
  });

  it('redirects single-role HR to /hr/dashboard (B15/B20)', () => {
    getStoredRoles.mockReturnValue(['HR']);
    getActiveRole.mockReturnValue('HR');
    renderGuarded();
    expect(screen.queryByText('EMPLOYEE CONTENT')).not.toBeInTheDocument();
    expect(screen.getByText('HR HOME')).toBeInTheDocument();
  });

  it('allows a dual HR+EMPLOYEE user', () => {
    getStoredRoles.mockReturnValue(['HR', 'EMPLOYEE']);
    getActiveRole.mockReturnValue('HR');
    renderGuarded();
    expect(screen.getByText('EMPLOYEE CONTENT')).toBeInTheDocument();
  });

  it('allows ADMIN', () => {
    getStoredRoles.mockReturnValue(['ADMIN']);
    renderGuarded();
    expect(screen.getByText('EMPLOYEE CONTENT')).toBeInTheDocument();
  });
});
