import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAuthItem } from '../../utils/demo';

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
  const role = (getAuthItem('relopass_role') || '').toUpperCase();
  const location = useLocation();

  if (role === 'ADMIN' || role === 'HR') {
    return <>{children}</>;
  }

  if (role === 'EMPLOYEE' && allowEmployee) {
    return <>{children}</>;
  }

  // EMPLOYEE (without opt-in) and any unrecognised role → redirect to their landing.
  const redirectTo = role === 'EMPLOYEE' ? '/employee/dashboard' : '/';
  return <Navigate to={redirectTo} state={{ from: location }} replace />;
};
