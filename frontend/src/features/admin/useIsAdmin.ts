import { useMemo } from 'react';
import { getAuthItem } from '../../utils/demo';

/**
 * Centralized admin access check.
 * Use for route guards and conditional rendering of admin-only UI.
 */
export function useIsAdmin(): boolean {
  return useMemo(() => {
    const role = (getAuthItem('relopass_role') || '').toUpperCase();
    if (role === 'ADMIN') return true;
    // Backend may allowlist certain emails; frontend relies on role from JWT
    return false;
  }, []);
}

/**
 * Redirect to appropriate landing when non-admin tries to access admin routes.
 */
export function getAdminRedirectPath(): string {
  const role = (getAuthItem('relopass_role') || '').toUpperCase();
  if (role === 'HR') return '/hr/dashboard';
  if (role === 'EMPLOYEE') return '/employee/dashboard';
  return '/';
}
