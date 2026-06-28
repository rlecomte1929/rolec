import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getStoredRoles, getActiveRole } from '../../utils/demo';
import { roleHomePath } from '../../navigation/roleHome';

interface RequireHrRouteProps {
  children: React.ReactNode;
  /** When true, EMPLOYEE users are also allowed through (e.g. shared /hr/policy view). */
  allowEmployee?: boolean;
}

/**
 * Wraps HR-only routes. ADMIN and HR users are allowed through; EMPLOYEE users
 * are redirected to their own dashboard, unauthenticated users are sent to /.
 *
 * This fixes AIQ-760: /hr/* routes had no role guard, so an authenticated
 * EMPLOYEE could open HR-only surfaces (e.g. /hr/employees, /hr/analytics).
 * Mirrors the RequireAdminRoute / RequireEmployeeRoute pattern.
 *
 * Pass allowEmployee={true} for routes that ROUTE_DEFS marks as EMPLOYEE-accessible
 * (e.g. /hr/policy, roles: ['HR','EMPLOYEE','ADMIN']).
 *
 * SECURITY (SEC-FE-4): this guard is a COSMETIC UX hint only. `relopass_role` is read
 * from localStorage, which is user-editable in devtools, so it must NEVER be the access
 * boundary. The real control is server-side: every /api/hr/** endpoint independently
 * enforces HR/Admin role + company-scope from the session token (see
 * docs/security/SEC-FE-4_authz_coverage.md).
 */
export const RequireHrRoute: React.FC<RequireHrRouteProps> = ({ children, allowEmployee = false }) => {
  // AIQ-1364: decide by ROLE MEMBERSHIP (multi-role) — a user passes if they HOLD
  // HR/ADMIN, not only if it's their single legacy role. Single-role users have
  // roles === [their role], so this is identical to the old behaviour for them
  // (B15/B20 separation preserved). Redirect honours the active role's home.
  const roles = getStoredRoles();
  const location = useLocation();

  if (roles.includes('ADMIN') || roles.includes('HR')) {
    return <>{children}</>;
  }

  if (roles.includes('EMPLOYEE') && allowEmployee) {
    return <>{children}</>;
  }

  return <Navigate to={roleHomePath(getActiveRole())} state={{ from: location }} replace />;
};
