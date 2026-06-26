import { useMemo } from 'react';
import { getAuthItem } from '../../utils/demo';

/**
 * Centralized admin access check.
 * Use for route guards and conditional rendering of admin-only UI.
 *
 * SECURITY (SEC-FE-4): COSMETIC UX hint only. `relopass_role` lives in localStorage
 * (user-editable in devtools) and must NEVER gate access to data. Every /api/admin/**
 * endpoint independently enforces admin server-side via require_admin (see
 * docs/security/SEC-FE-4_authz_coverage.md); a spoofed client role gets 403/404.
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
