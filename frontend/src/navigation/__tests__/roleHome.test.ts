import { describe, it, expect } from 'vitest';
import { roleHomePath, roleHomePathForHeldRoles } from '../roleHome';

/**
 * AIQ-980: an authenticated user who hits an unmatched URL (e.g. an employee
 * opening /hr/assignments) must be routed to their own dashboard, not the
 * public marketing homepage. Anonymous users still fall back to landing.
 */
describe('roleHomePath', () => {
  it('routes EMPLOYEE to the employee dashboard', () => {
    expect(roleHomePath('EMPLOYEE')).toBe('/employee/dashboard');
  });

  it('routes HR to the HR dashboard', () => {
    expect(roleHomePath('HR')).toBe('/hr/dashboard');
  });

  it('routes ADMIN to the admin overview', () => {
    expect(roleHomePath('ADMIN')).toBe('/admin');
  });

  it('is case-insensitive', () => {
    expect(roleHomePath('employee')).toBe('/employee/dashboard');
  });

  it('falls back to the public landing for anonymous / unknown roles', () => {
    expect(roleHomePath(null)).toBe('/');
    expect(roleHomePath(undefined)).toBe('/');
    expect(roleHomePath('')).toBe('/');
    expect(roleHomePath('SOMETHING_ELSE')).toBe('/');
  });
});

describe('roleHomePathForHeldRoles', () => {
  it('uses the active role when it is held', () => {
    expect(roleHomePathForHeldRoles(['HR', 'EMPLOYEE'], 'HR')).toBe('/hr/dashboard');
  });

  it('sends an EMPLOYEE-only session to the employee home even if active role is HR', () => {
    expect(roleHomePathForHeldRoles(['EMPLOYEE'], 'HR')).toBe('/employee/dashboard');
  });
});
