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
