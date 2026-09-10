import { ROUTE_DEFS } from './routes';

/**
 * The in-app landing path for an authenticated user's role. Used by the
 * catch-all route so an authenticated user who hits an unknown URL (e.g. an
 * employee opening /hr/assignments) is kept inside the app on their own
 * dashboard instead of being dumped on the public marketing homepage. (AIQ-980)
 *
 * Unknown / unauthenticated roles fall back to the public landing ('/') —
 * the pre-existing catch-all behaviour for anonymous visitors is preserved.
 */
export function roleHomePath(role?: string | null): string {
  switch ((role || '').toUpperCase()) {
    case 'EMPLOYEE':
      return ROUTE_DEFS.employeeDashboard.path;
    case 'HR':
      return ROUTE_DEFS.hrDashboard.path;
    case 'ADMIN':
      return ROUTE_DEFS.adminConsole.path;
    default:
      return ROUTE_DEFS.landing.path;
  }
}

/**
 * Home for a session whose active role may disagree with membership.
 * Login can persist users.role as HR while roles[] is only EMPLOYEE; redirecting
 * to the HR home then hits RequireHrRoute, which bounced back to HR home — a blank loop.
 */
export function heldHomeRole(roles: string[], active?: string | null): string {
  const held = roles.map((r) => (r || '').trim().toUpperCase()).filter(Boolean);
  const act = (active || '').trim().toUpperCase();
  if (act && held.includes(act)) return act;
  if (held.includes('EMPLOYEE')) return 'EMPLOYEE';
  if (held.includes('HR')) return 'HR';
  if (held.includes('ADMIN')) return 'ADMIN';
  return act;
}

export function roleHomePathForHeldRoles(roles: string[], active?: string | null): string {
  return roleHomePath(heldHomeRole(roles, active));
}
