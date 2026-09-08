import { describe, it, expect } from 'vitest';
import { homeRouteKeyForRole, buildRoute } from '../routes';

/**
 * AIQ-988: the /login page (rendered by Auth.tsx) redirects an already
 * authenticated user to their role's home via homeRouteKeyForRole(). The
 * redirect guard has existed since #173 (2026-05-29) but the mapping it
 * depends on had no test — this locks it so the redirect can't silently
 * regress (e.g. a role landing on '/' = the marketing homepage).
 */
describe('homeRouteKeyForRole', () => {
  it('maps EMPLOYEE to the employee dashboard', () => {
    expect(homeRouteKeyForRole('EMPLOYEE')).toBe('employeeDashboard');
    expect(buildRoute(homeRouteKeyForRole('EMPLOYEE'))).toBe('/employee/dashboard');
  });

  it('maps HR to the HR dashboard (the canonical HR home; /hr/assignments is not a route)', () => {
    expect(homeRouteKeyForRole('HR')).toBe('hrDashboard');
    expect(buildRoute(homeRouteKeyForRole('HR'))).toBe('/hr/dashboard');
  });

  it('maps ADMIN to the admin console', () => {
    expect(homeRouteKeyForRole('ADMIN')).toBe('adminConsole');
    expect(buildRoute(homeRouteKeyForRole('ADMIN'))).toBe('/admin');
  });

  it('is case- and whitespace-insensitive', () => {
    expect(homeRouteKeyForRole('  employee ')).toBe('employeeDashboard');
    expect(homeRouteKeyForRole('Hr')).toBe('hrDashboard');
  });

  it('falls back to landing for missing / unknown roles (no redirect off /login)', () => {
    expect(homeRouteKeyForRole(null)).toBe('landing');
    expect(homeRouteKeyForRole(undefined)).toBe('landing');
    expect(homeRouteKeyForRole('')).toBe('landing');
    expect(homeRouteKeyForRole('GUEST')).toBe('landing');
  });
});
