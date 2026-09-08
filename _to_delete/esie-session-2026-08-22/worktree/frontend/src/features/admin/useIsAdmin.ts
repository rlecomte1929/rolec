import { getAuthItem, normalizeStoredRole } from '../../utils/demo';

/**
 * Centralized admin access check.
 * Use for route guards and conditional rendering of admin-only UI.
 *
 * SECURITY (SEC-FE-4): COSMETIC UX hint only. `relopass_role` lives in localStorage
 * (user-editable in devtools) and must NEVER gate access to data. Every /api/admin/**
 * endpoint independently enforces admin server-side via require_admin (see
 * docs/security/SEC-FE-4_authz_coverage.md); a spoofed client role gets 403/404.
 *
 * AIQ-1678: read `relopass_role` FRESH on every render — do NOT memoize on []. A
 * consumer like ConsentBanner mounts once at the app root (App.tsx) and never remounts,
 * so a `useMemo(..., [])` cached the pre-login value ('' → false) for the whole session;
 * an admin who logged in during the same page load kept seeing admin-hidden UI. A plain
 * read (matching how AppShell etc. read the role) reflects the current role each render.
 */
export function useIsAdmin(): boolean {
  // Backend may also allowlist certain emails; the frontend relies on the role the login
  // response wrote here (normalized to upper-case in useAuth via normalizeStoredRole).
  return normalizeStoredRole(getAuthItem('relopass_role')) === 'ADMIN';
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
