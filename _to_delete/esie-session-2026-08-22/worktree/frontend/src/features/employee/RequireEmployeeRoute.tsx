import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getStoredRoles, getActiveRole } from '../../utils/demo';
import { roleHomePath } from '../../navigation/roleHome';

interface RequireEmployeeRouteProps {
  children: React.ReactNode;
  /** When true, HR users are also allowed through (e.g. HR viewing employee checklist). */
  allowHR?: boolean;
}

/**
 * Wraps employee-only routes. HR users are redirected to /hr/dashboard,
 * admin users are allowed through, unauthenticated users are sent to /.
 *
 * This fixes B15: HR navigating to /employee/* used to see an empty employee
 * portal instead of being redirected back to their own dashboard.
 *
 * Pass allowHR={true} to permit HR on specific cross-role pages (e.g. MVG-6B checklist).
 *
 * SECURITY (SEC-FE-4): this guard is a COSMETIC UX hint only. `relopass_role` is read
 * from localStorage, which is user-editable in devtools, so it must NEVER be the access
 * boundary. The real control is server-side: every privileged API independently enforces
 * role + company-scope from the session token (see docs/security/SEC-FE-4_authz_coverage.md).
 * The cached role is derived from the server login response (useAuth.ts → setSession).
 */
export const RequireEmployeeRoute: React.FC<RequireEmployeeRouteProps> = ({ children, allowHR = false }) => {
  // AIQ-1364: decide by ROLE MEMBERSHIP (multi-role). Single-role users have
  // roles === [their role], so a single-role HR is still redirected out of the
  // employee tree (B15/B20 preserved). Redirect honours the active role's home.
  const roles = getStoredRoles();
  const location = useLocation();

  if (roles.includes('ADMIN')) {
    // Admins can view employee-facing pages for support/debug purposes.
    return <>{children}</>;
  }

  if (roles.includes('HR') && allowHR) {
    // Explicitly opted-in HR access (e.g. HR reviewing employee immigration checklist).
    return <>{children}</>;
  }

  if (!roles.includes('EMPLOYEE')) {
    return <Navigate to={roleHomePath(getActiveRole())} state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
